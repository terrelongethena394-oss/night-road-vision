"""Matched12epoch RAW/ENH global experts;original RAWdetail model stays frozen."""
import copy,sys,math,random,time,shutil
import cv2,numpy as np
from road_enhanced_detection_common import *
def main():
    import torch,yaml
    sys.path.insert(0,str(BASE/'road_detection_20261026/yolov5'))
    from utils.loss import ComputeLoss
    from utils.torch_utils import ModelEMA
    assert (ROOT/'hard_training_selection.json').exists() and not (ROOT/'training_complete.json').exists()
    assert sha(INITIAL)==read(ROOT/'protocol.json')['initial_sha256']
    shutil.copy2(__file__,ROOT/'source'/Path(__file__).name)
    torch.set_num_threads(4);cv2.setNumThreads(1);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
    rows=read(ROOT/'training_manifest.json');index={r['name']:i for i,r in enumerate(rows)};extra=[index[r['name']] for r in read(ROOT/'hard_training_selection.json')['chosen']]
    # Cache each unique PNG once in host RAM;do not create anotherGBdiskcopy.
    raw=[];enh=[];begin=time.monotonic()
    for i,r in enumerate(rows):
        p=Path(r['views'][0]['image']);assert sha(p)==r['views'][0]['image_sha256'];im=cv2.imread(str(p))[:,:,::-1].copy();raw.append(im)
        if r['enhanced_global']:
            e=r['enhanced_global'];assert sha(e['image'])==e['sha256'];enh.append(cv2.imread(e['image'])[:,:,::-1].copy())
        else:enh.append(im)
        if (i+1)%600==0:print('MATCHED_TRAIN_CACHE',i+1,len(rows),flush=True)
    hyp=yaml.safe_load((BASE/'road_detection_20261026/road_hyp.yaml').read_text());hyp['cls']*=4/80;hyp['obj']*=.25;hyp['label_smoothing']=0.
    write(ROOT/'training_config.json',dict(status='MATCHED_CONFIG_FROZEN_BEFORE_GRADIENTS',epochs=EPOCHS,checkpoints=CHECKPOINTS,batch32=True,FP32=True,BN_updated=True,hyp=hyp,extra_names=[rows[i]['name'] for i in extra],enhancer_sha256=sha(ENHANCER)))
    history=[]
    for branch,images in [('raw',raw),('enh',enh)]:
        random.seed(SEED);np.random.seed(SEED);torch.manual_seed(SEED);torch.cuda.manual_seed_all(SEED)
        model=torch.load(INITIAL,map_location='cpu',weights_only=False)['model'].float().cuda().train().requires_grad_(True);model.hyp=hyp;model.nc=4;model.gr=1.
        initial={k:v.detach().cpu().clone() for k,v in model.state_dict().items()};anchors={k:v.detach().cpu().clone() for k,v in model.named_buffers() if k.endswith('anchors')}
        optimizer=torch.optim.AdamW(model.parameters(),lr=1e-4,betas=(.9,.999),weight_decay=1e-4);loss_fn=ComputeLoss(model);ema=ModelEMA(model)
        for epoch in range(1,EPOCHS+1):
            model.train();rng=np.random.default_rng(SEED+epoch);order=np.concatenate([np.arange(2400),extra]);rng.shuffle(order)
            lr=1e-5+9e-5*(1+math.cos(math.pi*(epoch-1)/(EPOCHS-1)))/2
            for g in optimizer.param_groups:g['lr']=lr
            sums=np.zeros(3);start=time.monotonic()
            for at in range(0,len(order),32):
                ids=order[at:at+32];xx=[];labels=[]
                for bi,i in enumerate(ids):
                    im=images[i];gt=np.asarray(rows[i]['views'][0]['labels'],np.float32).reshape(-1,5).copy()
                    if rng.random()<.5:im=im[:,::-1];gt[:,1]=1-gt[:,1]
                    xx.append(im.transpose(2,0,1));t=np.zeros((len(gt),6),np.float32);t[:,0]=bi;t[:,1:]=gt;labels.append(t)
                x=torch.from_numpy(np.ascontiguousarray(np.stack(xx))).cuda().float()/255;target=torch.from_numpy(np.concatenate(labels)).cuda()
                pred=model(x);loss,items=loss_fn(pred,target);assert torch.isfinite(loss)
                optimizer.zero_grad(set_to_none=True);loss.backward();norm=torch.nn.utils.clip_grad_norm_(model.parameters(),10.);assert torch.isfinite(norm);optimizer.step();ema.update(model);sums+=items.detach().cpu().numpy()
                if (at//32+1)%30==0:print('MATCHED_DETECTOR_TRAIN',branch,epoch,at//32+1,90,'loss',round(float(loss.detach()),5),'seconds',round(time.monotonic()-begin),flush=True)
            for k,v in model.named_buffers():
                if k in anchors:assert torch.equal(v.detach().cpu(),anchors[k])
            record=dict(branch=branch,epoch=epoch,lr=lr,loss_components=(sums/90).tolist(),seconds=time.monotonic()-start);history.append(record);write(ROOT/'history.json',history)
            if epoch in CHECKPOINTS:
                folder=ROOT/'frozen'/f'{branch}{epoch}';folder.mkdir();saved=copy.deepcopy(ema.ema).cpu().float().eval();buffers=dict(model.named_buffers())
                for k,v in saved.named_buffers():v.copy_(buffers[k].detach().cpu())
                changed=sum(not torch.equal(v,initial[k]) for k,v in saved.state_dict().items() if v.is_floating_point());assert changed>0
                torch.save(dict(model=saved,epoch=epoch,ema=None,optimizer=None,branch=branch,protocol_sha256=sha(ROOT/'protocol.json')),folder/'model.pt')
                write(folder/'frozen.json',dict(**record,sha256=sha(folder/'model.pt'),changed_float_tensors=changed,BN_updated=True,anchors_unchanged=True,source_train_manifest_sha256=sha(ROOT/'training_manifest.json')))
                print('MATCHED_DETECTOR_CHECKPOINT',branch,epoch,changed,flush=True)
        del model,ema;torch.cuda.empty_cache()
    write(ROOT/'training_complete.json',dict(status='BOTH_MATCHED_GLOBAL_DETECTORS_TRAINED',history=history,seconds=time.monotonic()-begin,hardware_access=False,sd_written=False))
    print('MATCHED_DETECTOR_TRAINING_COMPLETE',flush=True)
if __name__=='__main__':main()
