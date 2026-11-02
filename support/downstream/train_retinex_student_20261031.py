"""Paper reference as identity initialization;paired plus road-teacher learning."""
import shutil,random,time,math
import cv2,numpy as np
from road_retinex_student_common import *
from road_retinex_project import illumination

def main():
    import torch
    assert not ROOT.exists();ROOT.mkdir();(ROOT/'source').mkdir();(ROOT/'frozen').mkdir()
    split=read(BASE/'model_upgrade_20261023/student_training_split.json')
    write(ROOT/'protocol.json',dict(status='FROZEN_BEFORE_NEW_TRAINING',seed=SEED,
      reason='Previous raw-skip411student failed quality/recognition;keep its failed record. Folded teacher illumination alone lacks required restoration and creates highlight artifacts;rejected. New hypothesis:paper-initialized residual correction with real paired normal-exposure training covers severe darkness missing from road-only targets.',
      architecture='411parameters;pointwise7to12,depthwise3x3zero-pad12,pointwise12to12,head12to3 with ReLU between. Features rawRGB,paperenhancedRGB,illumination. Output paperbase+learnedresidual*highlightgate(.65,.98). Exact meanraw>48 or allblack scene bypass. No training on evaluation images.',
      data='Existing96LOL-v1 real low/normal fit pairs,12 heldout internal validation; originaltrain road512teacher fit/128teacher internal_val from previous train-only640. Exclude any exact normal-image hash overlap between fit and internal validation. No paired20/eval15/development80 examples for gradients.',
      road_target='0.8*original-author Retinexformer output+0.2*raw;no GT mean. Synthetic exposure augmentation input gain .125/.25/.5/1 while target stays fixed,identified as synthetic,not real-dark evidence.',
      optimization='One model32epochs,384images/epoch:192replacement paired draws,192road draws with frozen random seed and scale. Batch8,AdamWlr.002cosine.0002,wd1e-5,clip5. L1target+.1gradientL1target. Checkpoints8/16/32;select highest internal paired PSNR+3SSIM. No detector training.',
      acceptance='Display restoration only:require existing20 paired diagnosticPSNR andSSIM above current,known-road visual review,Cnumerical proof,then temporary JTAG.20paired previously used,not independent. Detection ALWAYS originalRAW path and existing weights/views/refiner;no enhanced-detection accuracy claim.',
      no_new_independent_accuracy_claim=True,hardware_access=False,sd_written=False))
    for n in [Path(__file__).name,'road_retinex_student_common.py','road_retinex_project.py']:shutil.copy2(Path(__file__).with_name(n),ROOT/'source'/n)
    from study_road_local_enhance_v2 import resize400,rgb,metric
    old=BASE/'model_upgrade_20261023/dataset/our485'
    pairs={s:[(resize400(rgb(old/'low'/n)),resize400(rgb(old/'high'/n))) for n in split[k]] for s,k in [('fit','train'),('internal','validation')]}
    assert not {sha(old/'high'/n) for n in split['train']}&{sha(old/'high'/n) for n in split['validation']}
    for s,v in pairs.items():
        (ROOT/s).mkdir();np.asarray([a for a,g in v],np.uint8).tofile(ROOT/s/'raw.u8');np.asarray([g for a,g in v],np.uint8).tofile(ROOT/s/'normal.u8')
    write(ROOT/'training_selection.json',dict(paired_fit=split['train'],paired_internal=split['validation'],paired_source_manifest_sha256=sha(BASE/'model_upgrade_20261023/student_training_split.json'),road_sources=read(BASE/'road_tiny_restore_20261031_r1/training_selection.json')))
    src=BASE/'road_tiny_restore_20261031_r1'
    rraw=np.memmap(src/'raw.u8',mode='r',dtype='u1',shape=(640,240,400,3));rtarget=np.memmap(src/'target.u8',mode='r',dtype='u1',shape=(640,240,400,3))
    # Derive source features once for each finite,predeclared exposure level.
    raw=[];goals=[];ils=[];begin=time.monotonic()
    for a,g in pairs['fit']:
        raw.append(a);goals.append(g);ils.append(illumination(a))
    for i in range(512):
        a=rraw[i];g=np.floor(.8*rtarget[i].astype(np.float32)+.2*a+.5).astype(np.uint8)
        for scale in [.125,.25,.5,1.]:
            aa=np.floor(a.astype(np.float32)*scale+.5).astype(np.uint8)
            raw.append(aa);goals.append(g);ils.append(illumination(aa))
        if (i+1)%128==0:print('RETINEX_STUDENT_FEATURES',i+1,512,round(time.monotonic()-begin),flush=True)
    raw=np.asarray(raw,np.uint8);goals=np.asarray(goals,np.uint8);ils=np.asarray(ils,np.float16)
    torch.set_num_threads(4);cv2.setNumThreads(1);torch.manual_seed(SEED);torch.cuda.manual_seed_all(SEED)
    torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True;torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    net=make_model().cuda();assert sum(p.numel() for p in net.parameters())==411
    opt=torch.optim.AdamW(net.parameters(),lr=.002,weight_decay=1e-5);history=[]
    for epoch in range(1,33):
        rng=np.random.default_rng(SEED+epoch);order=np.concatenate([rng.integers(0,96,192),96+rng.integers(0,512*4,192)]);rng.shuffle(order)
        lr=.0002+.0018*(1+math.cos(math.pi*(epoch-1)/31))*.5
        for group in opt.param_groups:group['lr']=lr
        net.train();losses=[]
        for at in range(0,len(order),8):
            ix=order[at:at+8];a=torch.from_numpy(raw[ix].transpose(0,3,1,2).copy()).cuda().float()/255;g=torch.from_numpy(goals[ix].transpose(0,3,1,2).copy()).cuda().float()/255;f=torch.from_numpy(ils[ix].astype(np.float32)).cuda()[:,None]
            z=net(a,f);l1=(z-g).abs().mean();edge=((z[:,:,:,1:]-z[:,:,:,:-1]-(g[:,:,:,1:]-g[:,:,:,:-1])).abs().mean()+(z[:,:,1:,:]-z[:,:,:-1,:]-(g[:,:,1:,:]-g[:,:,:-1,:])).abs().mean())*.5
            loss=l1+.1*edge;assert torch.isfinite(loss);opt.zero_grad(set_to_none=True);loss.backward();torch.nn.utils.clip_grad_norm_(net.parameters(),5.);opt.step();losses.append(float(loss.detach()))
        rec=dict(epoch=epoch,loss=float(np.mean(losses)),lr=lr,seconds=time.monotonic()-begin)
        if epoch in [8,16,32]:
            net.eval();mm=[]
            for a,g in pairs['internal']:
                z=infer(net,a,torch);mm.append(metric(z,g))
            rec.update(psnr=float(np.mean([m['psnr'] for m in mm])),ssim=float(np.mean([m['ssim'] for m in mm])))
            rec['score']=rec['psnr']+3*rec['ssim'];folder=ROOT/'frozen'/f'epoch{epoch}';folder.mkdir()
            torch.save({k:v.detach().cpu() for k,v in net.state_dict().items()},folder/'model.pt');write(folder/'frozen.json',dict(**rec,sha256=sha(folder/'model.pt'),protocol_sha256=sha(ROOT/'protocol.json')))
        history.append(rec);write(ROOT/'history.json',history)
        if epoch%4==0:print('RETINEX_STUDENT_TRAIN',rec,flush=True)
    selected=max([r for r in history if 'score' in r],key=lambda r:r['score'])
    write(ROOT/'selected.json',dict(status='INTERNAL_QUALITY_SELECTION_FROZEN_BEFORE_PAIRED20_AND_ROAD80',chosen=f'epoch{selected["epoch"]}',record=selected,raw_detection_unchanged=True,hardware_access=False,sd_written=False))
    print('RETINEX_STUDENT_TRAIN_COMPLETE',selected,flush=True)
if __name__=='__main__':main()
