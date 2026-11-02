"""Frozen detector directly supervises153parameter spatial enhancement strength."""
import sys,shutil,threading,concurrent.futures as cf,time,math
import numpy as np,cv2
from road_task_gate_common import *
from prove_student_fusion_20261031 import Engine
from road_retinex_project import illumination
import road_accuracy_common as ac

def main():
    import torch,yaml
    assert not ROOT.exists();ROOT.mkdir();(ROOT/'source').mkdir();(ROOT/'frozen').mkdir()
    prior=BASE/'road_enhanced_detection_20261031_r1';assert read(prior/'selected.json')['qualified'] is False
    rows=read(prior/'training_manifest.json');rows=[r for r in rows if r['mean_raw']<=48];assert len(rows)==1060
    rows=sorted(rows,key=lambda r:sha_text(str(SEED)+r['name']))
    for i,r in enumerate(rows):r['gate_split']='fit' if i<848 else 'internal_val'
    write(ROOT/'training_manifest.json',rows)
    write(ROOT/'protocol.json',dict(status='TASK_GATE_FROZEN_BEFORE_GRADIENTS_AND_EVALUATION',seed=SEED,
      reason='Matched12epochglobalRAW/ENH detector fine-tuning failed to beat acceptedRAW7;failure preserved. New hypothesis changes enhancement spatially using frozen detector loss instead of further adapting detector.',
      architecture='153parameter7to8pointwiseReLU,depthwise3x3zero-pad8ReLU,head8to1. InputrawRGB,ABI29brightRGB,paperillumination. mask=.1+.9sigmoid;out=raw+mask*(bright-raw). No image overlays/GT/detection boxes at inference.',
      train='Original1060dark train sources;848fit/212internal_val by frozenhash. Same originalGT.480earlier TRAINhardframes intersect fit only are repeated. Internal sources get no gradients. OriginalRAWdetector allweights/BNfrozen.',
      objective='YOLOComputeLoss/batch +.02L1(out,bright)+.01TV(mask)+.5relu(.35-meanmask)^2.12epochs,batch8,AdamW.002cosine.0002wd1e-5,clip5,flip.5. Checkpoints4/8/12. Exactinteger400to320 forward with straight-through gradients.',
      development='Same exposed480low development,helpers/refiner unchanged,main detector originalcb. Compare3gatecheckpoints and uniform enhancement mixes.1/.35/.55/1 (same RAWdetector).Fixed.25confidence/.5match/.6NMS;no threshold search.',
      gates='Same as preceding matched study vs BOTH acceptedRAW7 and strongest matched-trainedRAWcontrol:AP+.5pp,P no lower,R+.5pp,FP no higher,F1+.5pp.Choose highestAP passing candidate,preferuniform lowercompute on ties. Show uniformcontrols and failures.',
      fresh_policy='Only one frozen candidate after actualC development proof,unused240low+64bright excluding ALL recordedgroups/hashes. Same gates +99%pairedAPgain lower>0 versus BOTH RAWcontrols;no fresh-driven reselection.',
      interface='Actualdisplay and global detector receive SAME task-enhanced400pixels;6RAWdetail views unchanged. Meanraw>48 andallblack bypass. No claim everydetail input enhanced.',
      previous_failed_study_sha256=sha(prior/'selected.json'),hardware_access=False,sd_written=False))
    for n in [Path(__file__).name,'road_task_gate_common.py']:shutil.copy2(Path(__file__).with_name(n),ROOT/'source'/n)
    begin=time.monotonic();local=threading.local();cv2.setNumThreads(1)
    def prepare(r):
        if not hasattr(local,'engine'):local.engine=Engine()
        ip=BASE/'road_detection_20261026/dataset/images/train'/r['name'];assert sha(ip)==r['image_sha256'];_,a=ac.sensor400(ip)
        return a,local.engine.run(a),illumination(a).astype(np.float16)
    cache=[]
    with cf.ThreadPoolExecutor(4) as pool:
        for i,v in enumerate(pool.map(prepare,rows),1):
            cache.append(v)
            if i%160==0:print('TASK_GATE_TRAIN_PIXELS',i,len(rows),round(time.monotonic()-begin),flush=True)
    write(ROOT/'prepared.json',dict(images=1060,fit=848,internal_val=212,RAM_cache_only=True,source_manifest_sha256=sha(ROOT/'training_manifest.json')))
    sys.path.insert(0,str(BASE/'road_detection_20261026/yolov5'));from utils.loss import ComputeLoss
    torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
    detector=torch.load(INITIAL,map_location='cpu',weights_only=False)['model'].float().cuda().eval().requires_grad_(False)
    hyp=yaml.safe_load((BASE/'road_detection_20261026/road_hyp.yaml').read_text());hyp['cls']*=4/80;hyp['obj']*=.25;hyp['label_smoothing']=0.;detector.hyp=hyp;detector.nc=4;detector.gr=1.;loss_fn=ComputeLoss(detector)
    before={k:v.detach().cpu().clone() for k,v in detector.state_dict().items()}
    # Verify exact resize numerically before the first gradient.
    probe=np.random.default_rng(SEED).integers(0,256,(240,400,3),np.uint8);x=torch.from_numpy(probe.transpose(2,0,1).copy()).cuda().float()[None]/255
    got=np.floor(preprocess_exact(x)[0].permute(1,2,0).cpu().numpy()*255+.5).astype(np.uint8);assert np.array_equal(got,ac.preprocess400(probe))
    torch.manual_seed(SEED);torch.cuda.manual_seed_all(SEED);model=make_model().cuda();assert sum(p.numel() for p in model.parameters())==153
    optimizer=torch.optim.AdamW(model.parameters(),lr=.002,weight_decay=1e-5)
    index={r['name']:i for i,r in enumerate(rows)};extra=[index[r['name']] for r in read(prior/'hard_training_selection.json')['chosen'] if r['name'] in index and index[r['name']]<848]
    write(ROOT/'training_config.json',dict(status='FROZEN_BEFORE_FIRST_TASK_GATE_GRADIENT',extra_names=[rows[i]['name'] for i in extra],fixed_detector_sha256=sha(INITIAL),resize_exact_probe_passed=True))
    def batch(ids,flip_rng=None):
        aa=[];bb=[];ff=[];targets=[]
        for bi,i in enumerate(ids):
            a,b,f=cache[int(i)];gt=np.asarray(rows[int(i)]['views'][0]['labels'],np.float32).reshape(-1,5).copy()
            if flip_rng is not None and flip_rng.random()<.5:a=a[:,::-1];b=b[:,::-1];f=f[:,::-1];gt[:,1]=1-gt[:,1]
            aa.append(a.transpose(2,0,1));bb.append(b.transpose(2,0,1));ff.append(f);t=np.zeros((len(gt),6),np.float32);t[:,0]=bi;t[:,1:]=gt;targets.append(t)
        return torch.from_numpy(np.ascontiguousarray(np.stack(aa))).cuda().float()/255,torch.from_numpy(np.ascontiguousarray(np.stack(bb))).cuda().float()/255,torch.from_numpy(np.asarray(ff,np.float32).copy()).cuda()[:,None],torch.from_numpy(np.concatenate(targets)).cuda()
    history=[]
    for epoch in range(1,13):
        model.train();rng=np.random.default_rng(SEED+epoch);order=np.concatenate([np.arange(848),extra]);rng.shuffle(order);losses=[]
        lr=.0002+.0018*(1+math.cos(math.pi*(epoch-1)/11))*.5
        for g in optimizer.param_groups:g['lr']=lr
        for at in range(0,len(order),8):
            a,b,f,t=batch(order[at:at+8],rng);z,mask=model(a,b,f);p=detector(preprocess_exact(z))[1];task=loss_fn(p,t)[0]/len(a)
            tv=(mask[:,:,:,1:]-mask[:,:,:,:-1]).abs().mean()+(mask[:,:,1:,:]-mask[:,:,:-1,:]).abs().mean()
            priorloss=torch.relu(.35-mask.mean()).square();loss=task+.02*(z-b).abs().mean()+.01*tv+.5*priorloss
            assert torch.isfinite(loss);optimizer.zero_grad(set_to_none=True);loss.backward();norm=torch.nn.utils.clip_grad_norm_(model.parameters(),5.);assert torch.isfinite(norm);optimizer.step();losses.append([float(task.detach()),float(mask.mean().detach())])
            if (at//8+1)%60==0:print('TASK_GATE_TRAIN_STEP',epoch,at//8+1,(len(order)+7)//8,round(time.monotonic()-begin),flush=True)
        rec=dict(epoch=epoch,lr=lr,task_loss=float(np.mean(losses,axis=0)[0]),mean_mask=float(np.mean(losses,axis=0)[1]),seconds=time.monotonic()-begin);history.append(rec);write(ROOT/'history.json',history)
        if epoch in [4,8,12]:
            folder=ROOT/'frozen'/f'epoch{epoch}';folder.mkdir();torch.save({k:v.detach().cpu() for k,v in model.state_dict().items()},folder/'model.pt');write(folder/'frozen.json',dict(**rec,sha256=sha(folder/'model.pt'),parameters=153,protocol_sha256=sha(ROOT/'protocol.json')))
        print('TASK_GATE_TRAIN_EPOCH',rec,flush=True)
    assert all(torch.equal(v.detach().cpu(),before[k]) for k,v in detector.state_dict().items())
    write(ROOT/'training_complete.json',dict(status='ACTUAL_TASK_GATE_TRAINING_COMPLETE',frozen_detector_unchanged=True,history=history,seconds=time.monotonic()-begin,hardware_access=False,sd_written=False));print('TASK_GATE_TRAIN_COMPLETE',flush=True)
def sha_text(s):return __import__('hashlib').sha256(s.encode()).hexdigest()
if __name__=='__main__':main()
