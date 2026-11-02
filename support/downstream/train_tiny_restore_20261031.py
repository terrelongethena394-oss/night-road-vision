"""Actual teacher distillation and detector-guided restoration,411parameters."""
import sys,random,time,math,shutil
import cv2,numpy as np
from road_tiny_restore_common import *

def main():
    import torch,yaml
    import torch.nn.functional as F
    assert (ROOT/'prepared.json').exists() and not (ROOT/'training_complete.json').exists()
    sys.path.insert(0,str(BASE/'road_detection_20261026/yolov5'))
    from utils.loss import ComputeLoss
    torch.set_num_threads(4);cv2.setNumThreads(1)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
    random.seed(SEED);np.random.seed(SEED);torch.manual_seed(SEED);torch.cuda.manual_seed_all(SEED)
    shutil.copy2(__file__,ROOT/'source'/Path(__file__).name)
    rows=read(ROOT/'training_selection.json');n=len(rows)
    arrays=[np.memmap(ROOT/name,mode='r',dtype=dtype,shape=shape) for name,dtype,shape in [('raw.u8','u1',(n,240,400,3)),('target.u8','u1',(n,240,400,3)),('illum.f16','<f2',(n,240,400))]]
    raw,target,illum=arrays
    detector=torch.load(DETECTOR,map_location='cpu',weights_only=False)['model'].float().cuda().eval().requires_grad_(False)
    hyp=yaml.safe_load((BASE/'road_detection_20261026/road_hyp.yaml').read_text());hyp['cls']*=4/80;hyp['obj']*=.25;hyp['label_smoothing']=0.
    detector.hyp=hyp;detector.nc=4;detector.gr=1.;loss_fn=ComputeLoss(detector)
    detector_before={k:v.detach().cpu().clone() for k,v in detector.state_dict().items()}
    initial=make_model().cuda();assert sum(p.numel() for p in initial.parameters())==411
    initial_state={k:v.detach().cpu().clone() for k,v in initial.state_dict().items()}
    torch.save(initial_state,ROOT/'initial_state.pt')
    def batch(indices):
        a=torch.from_numpy(np.asarray(raw[indices]).transpose(0,3,1,2).copy()).cuda().float()/255
        z=torch.from_numpy(np.asarray(target[indices]).transpose(0,3,1,2).copy()).cuda().float()/255
        f=torch.from_numpy(np.asarray(illum[indices],np.float32).copy()).cuda().unsqueeze(1)
        local=F.avg_pool2d(F.pad(a,(1,1,1,1),mode='reflect'),3,stride=1)
        y=(54*local[:,0:1]+183*local[:,1:2]+19*local[:,2:3])/256
        u=((a.amax(1,keepdim=True)-.65)/.33).clamp(0,1);gate=y/(y+.02)*(1-u*u*(3-2*u))
        goal=(a+gate*(z-a)).clamp(0,1)
        targets=[]
        for bi,i in enumerate(indices):
            g=torch.tensor(rows[int(i)]['views'][0]['labels'],dtype=torch.float32).reshape(-1,5)
            t=torch.zeros((len(g),6));t[:,0]=bi;t[:,1:]=g;targets.append(t)
        return a,f,goal,torch.cat(targets).cuda()
    def gradloss(z,g):
        return ((z[:,:,:,1:]-z[:,:,:,:-1]-(g[:,:,:,1:]-g[:,:,:,:-1])).abs().mean()+(z[:,:,1:,:]-z[:,:,:-1,:]-(g[:,:,1:,:]-g[:,:,:-1,:])).abs().mean())*.5
    history=[];begin=time.monotonic()
    for branch in ['distill','joint']:
        net=make_model().cuda();net.load_state_dict(initial_state)
        opt=torch.optim.AdamW(net.parameters(),lr=.002,weight_decay=1e-5)
        for epoch in range(1,9):
            rng=np.random.default_rng(SEED+epoch);order=rng.permutation(512)
            lr=.0002+.0018*(1+math.cos(math.pi*(epoch-1)/7))*.5
            for group in opt.param_groups:group['lr']=lr
            sums=np.zeros(3);net.train()
            for at in range(0,512,8):
                a,f,g,t=batch(order[at:at+8]);z=net(a,f)
                recon=(z-g).abs().mean();edge=gradloss(z,g);task=z.sum()*0
                if branch=='joint':
                    # Differentiable approximation to the fixed400->320 letterbox.
                    x=F.interpolate(z,size=(192,320),mode='bilinear',align_corners=False)
                    # Quantization straight-through preserves gradients while
                    # exposing the frozen detector to integer-valued images.
                    q=(x*255).round()/255;x=x+(q-x).detach();x=F.pad(x,(0,0,64,64),value=114/255)
                    pred=detector(x)[1];task=loss_fn(pred,t)[0]/len(a)
                loss=recon+.1*edge+.5*task
                assert torch.isfinite(loss);opt.zero_grad(set_to_none=True);loss.backward()
                norm=torch.nn.utils.clip_grad_norm_(net.parameters(),5.);assert torch.isfinite(norm);opt.step()
                sums+=[float(recon.detach()),float(edge.detach()),float(task.detach())]
            net.eval();val=[]
            with torch.inference_mode():
                for at in range(512,640,8):
                    a,f,g,t=batch(list(range(at,at+8)));val.append(float((net(a,f)-g).abs().mean()))
            record=dict(branch=branch,epoch=epoch,lr=lr,recon=float(sums[0]/64),edge=float(sums[1]/64),task=float(sums[2]/64),internal_val_l1=float(np.mean(val)),seconds=time.monotonic()-begin)
            history.append(record);write(ROOT/'history.json',history)
            print('TINY_RESTORE_TRAIN',json.dumps(record),flush=True)
            if epoch in [4,8]:
                folder=ROOT/'frozen'/f'{branch}{epoch}';folder.mkdir()
                state={k:v.detach().cpu().clone() for k,v in net.state_dict().items()}
                torch.save(state,folder/'model.pt');write(folder/'frozen.json',dict(**record,sha256=sha(folder/'model.pt'),parameters=411,changed_tensors=sum(not torch.equal(v,initial_state[k]) for k,v in state.items()),protocol_sha256=sha(ROOT/'protocol.json')))
        del net
    assert all(torch.equal(v.detach().cpu(),detector_before[k]) for k,v in detector.state_dict().items())
    write(ROOT/'training_complete.json',dict(status='ACTUAL_DISTILL_AND_JOINT_TRAINING_COMPLETE',epochs_per_branch=8,history=history,frozen_detector_unchanged=True,seconds=time.monotonic()-begin,hardware_access=False,sd_written=False))
    print('TINY_RESTORE_TRAINING_COMPLETE',flush=True)
if __name__=='__main__':main()
