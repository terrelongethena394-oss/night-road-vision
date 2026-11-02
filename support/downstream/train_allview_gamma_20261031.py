"""Matched RAW/gamma all-view training; original train split only, no new holdout."""
import copy,math,random,sys,time,shutil,concurrent.futures as cf
import cv2,numpy as np
from road_enhanced_detection_common import BASE,INITIAL,read,write,sha
import road_accuracy_common as ac
from prove_car_zoom_c import ZoomC
from study_car_zoom_20261030 import XS
from prepare_road_viewadapt import labels_for_view
ROOT=BASE/'road_allview_gammafit_20261031_r1'
SEED=2026103161
EPOCHS=12
CHECKPOINTS=[4,8,12]

def view_labels(gt,x,y,w,h):
    g=gt.copy();g[:,[1,3]]-=x;g[:,[2,4]]-=y
    g[:,[1,3]]=np.clip(g[:,[1,3]],0,w);g[:,[2,4]]=np.clip(g[:,[2,4]],0,h)
    g=g[(g[:,3]-g[:,1]>=2)&(g[:,4]-g[:,2]>=2)]
    out=np.empty((len(g),5),np.float32);out[:,0]=g[:,0]
    out[:,1]=(g[:,1]+g[:,3])/(2*w);out[:,2]=((g[:,2]+g[:,4])*(192/(2*h))+64)/320
    out[:,3]=(g[:,3]-g[:,1])/w;out[:,4]=(g[:,4]-g[:,2])*(192/h)/320
    return out

def main():
    import torch,yaml
    sys.path.insert(0,str(BASE/'road_detection_20261026/yolov5'))
    from utils.loss import ComputeLoss
    from utils.torch_utils import ModelEMA
    assert not ROOT.exists();ROOT.mkdir();(ROOT/'source').mkdir()
    for n in [Path(__file__).name,'road_accuracy_common.py']:
        shutil.copy2(Path(__file__).with_name(n),ROOT/'source'/n)
    prior=BASE/'road_allview_enhance_20261031_r1';assert read(prior/'selected.json')['qualified'] is False
    rows=read(BASE/'road_enhanced_detection_20261031_r1/training_manifest.json');assert len(rows)==2400
    dev=read(BASE/'road_enhanced_detection_20261031_r1/development_manifest.json')
    assert not {r['group'] for r in rows}&{r['group'] for r in dev}
    write(ROOT/'protocol.json',dict(status='FROZEN_BEFORE_ALLVIEW_GRADIENTS',seed=SEED,initial=str(INITIAL),initial_sha256=sha(INITIAL),
      training='Original2400 train sources only; same image order,flip,optimizer,epochs,labels and3views/source/epoch inbothbranches. Full400+rotatingnative400tile+rotating280x168zoom. Every3epochs visits all7views. Dark scene meanY<=48 and owncropmeanY<=48 usesfixed hue-preservinggamma0.8,cap3,linearhighlightfade.65..98;otherwise exactRAW. No extra mining/pseudo labels.',
      labels='Full/tile labels same original accepted viewport clipping>=2sensor pixels. Zoom groundtruth clipped to280x168,visible dimensions>=2sensor pixels;normalized exact192high input with64graypadding. No labels accessed for enhancement.',
      optimizer='FP32 AdamW3e-5 cosine5e-6,wd1e-4, batch8sources*3views=24, train weights, frozenBNstatistics/anchors,EMA. Same two branches RAW/gamma080.',epochs=EPOCHS,checkpoints=CHECKPOINTS,
      evaluation='Reused480 low development only, same7views, IoU.5/conf.25/NMS.6/refiner/helperweights unchanged. Strongest matchedRAW checkpoint first, then choose highestAPpassingENH checkpoint. Gates against currentRAW7 and matchedRAW7:AP+.5pp,P>=,R+.5pp,FP<=,F1+.5pp. Same ENH checkpoint ENH-vsRAW attribution AP+.2pp,TP>=,FP<=.',
      fresh_policy='Only after development and C verification, freeze once and use new untouched240low+64bright with exclusion ledger. Same gates plus paired99%APgainCI>0 vsbothRAWcontrols. No test-driven replacement.',
      bright_policy='Keep original accepted4RAWviews/weights for overall meanY>48; trained experts only low scenes.',
      prior_failed_study_sha256=sha(prior/'selected.json'),training_manifest_sha256=sha(BASE/'road_enhanced_detection_20261031_r1/training_manifest.json'),hardware_access=False,sd_written=False))
    write(ROOT/'training_manifest.json',rows);write(ROOT/'development_manifest.json',dev)
    torch.set_num_threads(4);cv2.setNumThreads(1);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
    hyp=yaml.safe_load((BASE/'road_detection_20261026/road_hyp.yaml').read_text());hyp['cls']*=4/80;hyp['obj']*=.25;hyp['label_smoothing']=0.
    # Small LRU avoids multi-GB RAM caches. Each task owns its ZoomC/workspace.
    import threading,functools
    local=threading.local()
    @functools.lru_cache(maxsize=128)
    def source(i):
        r=rows[i];p=BASE/'road_detection_20261026/dataset/images/train'/r['name'];lp=p.parent.parent.parent/'labels/train'/(p.stem+'.txt')
        assert sha(p)==r['image_sha256'];sensor,full=ac.sensor400(p);gt=ac.truth(lp);g800=gt.copy();g800[:,1:]*=2
        q=full.astype(np.uint32);on=float(((54*q[:,:,0]+183*q[:,:,1]+19*q[:,:,2])/256).mean())<=48
        return sensor,full,gt,g800,on
    def prepare(job):
        i,epoch,branch,flip=job
        if not hasattr(local,'zoom'):local.zoom=ZoomC()
        sensor,full,gt,g800,scene_on=source(int(i));j=(epoch-1+int(i))%3;x,y=ac.TILES[j]
        views=[full,sensor[y:y+240,x:x+400].copy(),local.zoom.image(sensor,XS[j],152)]
        labels=[labels_for_view(gt,0,0,400,240),labels_for_view(g800,x,y,400,240),view_labels(g800,XS[j],152,280,168)]
        xx=[]
        for a,g in zip(views,labels):
            q=a.astype(np.uint32);on=scene_on and float(((54*q[:,:,0]+183*q[:,:,1]+19*q[:,:,2])/256).mean())<=48
            im=ac.preprocess400(ac.gamma(a,'gamma080') if branch=='enh' and on else a)
            if flip:im=im[:,::-1];g[:,1]=1-g[:,1]
            xx.append(im.transpose(2,0,1))
        return xx,labels
    # Algebraic label mapping guard, independent corners and padded-coordinate checks.
    probe=np.array([[1,10,20,100,80]],np.float32)
    assert np.allclose(view_labels(probe,0,0,400,240),labels_for_view(probe,0,0,400,240))
    begin=time.monotonic();history=[]
    for branch in ['raw','enh']:
        random.seed(SEED);np.random.seed(SEED);torch.manual_seed(SEED);torch.cuda.manual_seed_all(SEED)
        model=torch.load(INITIAL,map_location='cpu',weights_only=False)['model'].float().cuda().train().requires_grad_(True);model.hyp=hyp;model.nc=4;model.gr=1.
        initial={k:v.detach().cpu().clone() for k,v in model.state_dict().items()};buffers={k:v.detach().cpu().clone() for k,v in model.named_buffers()}
        opt=torch.optim.AdamW(model.parameters(),lr=3e-5,betas=(.9,.999),weight_decay=1e-4);lossfn=ComputeLoss(model);ema=ModelEMA(model)
        with cf.ThreadPoolExecutor(4) as pool:
            for epoch in range(1,EPOCHS+1):
                model.train()
                for m in model.modules():
                    if isinstance(m,torch.nn.modules.batchnorm._BatchNorm):m.eval()
                rng=np.random.default_rng(SEED+epoch);order=rng.permutation(2400);flips=rng.random(2400)<.5
                jobs=[(i,epoch,branch,bool(flips[k])) for k,i in enumerate(order)]
                lr=5e-6+2.5e-5*(1+math.cos(math.pi*(epoch-1)/(EPOCHS-1)))/2
                for g in opt.param_groups:g['lr']=lr
                start=time.monotonic();sums=np.zeros(3)
                # executor.map is eager but128sourceLRU bounds image RAM; outputs~2.2GB
                # if unbounded, so explicitly hold at most4 batches of24views.
                futures={k:pool.submit(prepare,jobs[k]) for k in range(min(32,len(jobs)))}
                for at in range(0,len(jobs),8):
                    prepared=[futures.pop(k).result() for k in range(at,at+8)]
                    for k in range(at+32,min(at+40,len(jobs))):futures[k]=pool.submit(prepare,jobs[k])
                    xx=[];ll=[]
                    for ims,labs in prepared:
                        for im,g in zip(ims,labs):
                            t=np.zeros((len(g),6),np.float32);t[:,0]=len(xx);t[:,1:]=g;ll.append(t);xx.append(im)
                    x=torch.from_numpy(np.ascontiguousarray(np.stack(xx))).cuda().float()/255;target=torch.from_numpy(np.concatenate(ll)).cuda()
                    loss,items=lossfn(model(x),target);assert torch.isfinite(loss)
                    opt.zero_grad(set_to_none=True);loss.backward();norm=torch.nn.utils.clip_grad_norm_(model.parameters(),10);assert torch.isfinite(norm);opt.step();ema.update(model);sums+=items.detach().cpu().numpy()
                    if (at//8+1)%100==0:print('ALLVIEW_GAMMA_TRAIN',branch,epoch,at//8+1,300,'loss',round(float(loss.detach()),5),'total_seconds',round(time.monotonic()-begin),flush=True)
                for k,v in model.named_buffers():assert torch.equal(v.detach().cpu(),buffers[k]),k
                rec=dict(branch=branch,epoch=epoch,lr=lr,loss_components=(sums/300).tolist(),seconds=time.monotonic()-start);history.append(rec);write(ROOT/'history.json',history)
                if epoch in CHECKPOINTS:
                    folder=ROOT/'frozen'/f'{branch}{epoch}';folder.mkdir(parents=True);saved=copy.deepcopy(ema.ema).cpu().float().eval()
                    for k,v in saved.named_buffers():v.copy_(buffers[k])
                    changed=sum(not torch.equal(v,initial[k]) for k,v in saved.state_dict().items() if v.is_floating_point());assert changed>0
                    torch.save(dict(model=saved,epoch=epoch,ema=None,optimizer=None,branch=branch,protocol_sha256=sha(ROOT/'protocol.json')),folder/'model.pt')
                    write(folder/'frozen.json',dict(**rec,sha256=sha(folder/'model.pt'),changed_float_tensors=changed,BN_unchanged=True,anchors_unchanged=True));print('ALLVIEW_GAMMA_FROZEN',branch,epoch,flush=True)
        del model,ema;torch.cuda.empty_cache()
    write(ROOT/'training_complete.json',dict(status='MATCHED_ALLVIEW_RAW_AND_GAMMA_TRAINED',seconds=time.monotonic()-begin,history=history,hardware_access=False,sd_written=False));print('ALLVIEW_GAMMA_TRAIN_COMPLETE',flush=True)

from pathlib import Path
if __name__=='__main__':main()
