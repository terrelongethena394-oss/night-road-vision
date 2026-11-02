"""Matched paired-view supervised learning with frozen-BN and raw-teacher retention."""
from pathlib import Path
import collections,copy,hashlib,math,os,random,shutil,sys,time
import cv2,numpy as np
from road_twilight_r2_common import *
HERE=Path(__file__).resolve().parent
def main():
 wait_start=time.monotonic()
 while not (ROOT/'prepare_complete.json').exists():
  if time.monotonic()-wait_start>1800:raise TimeoutError('Paired new training data not ready')
  time.sleep(2)
 assert sha(TEACHER)==TEACHER_SHA
 os.environ.update(YOLOv5_AUTOINSTALL='false',WANDB_DISABLED='true',COMET_MODE='DISABLED',YOLOV5_CONFIG_DIR=str(ROOT/'config'))
 (ROOT/'config').mkdir(exist_ok=True);shutil.copy2(HERE/'train_road_twilight_r2.py',ROOT/'source/train_road_twilight_r2.py')
 os.chdir(ROOT/'yolov5');sys.path.insert(0,str(ROOT/'yolov5'))
 import torch,yaml
 import torch.nn.functional as F
 from utils.loss import ComputeLoss
 from utils.torch_utils import ModelEMA
 torch.set_num_threads(4);cv2.setNumThreads(1);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
 rows=sorted([r for r in read(ROOT/'dataset/manifest.json') if r['split']=='train'],key=lambda r:r['name']);assert len(rows)==3000
 class Pairs(torch.utils.data.Dataset):
  def __init__(self):
   self.order=list(range(len(rows)));self.epoch=0
   for r in rows:
    stem=Path(r['name']).stem
    for m,k in [('raw_control','raw320_sha256'),('enhance_adapt','enh320_sha256')]:assert sha(ROOT/'dataset'/m/'images/train'/(stem+'.png'))==r[k]
    assert sha(ROOT/'dataset/raw_control/labels/train'/(stem+'.txt'))==r.get('mapped_label_sha256',r['label_sha256'])
  def __len__(self):return len(self.order)
  def __getitem__(self,i):
   r=rows[self.order[i]];stem=Path(r['name']).stem;images=[cv2.imread(str(ROOT/'dataset'/m/'images/train'/(stem+'.png')))[:,:,::-1] for m in ['raw_control','enhance_adapt']]
   labels=np.array([[float(v) for v in line.split()] for line in (ROOT/'dataset/raw_control/labels/train'/(stem+'.txt')).read_text(encoding='ascii').splitlines() if line],np.float32).reshape(-1,5)
   if np.random.default_rng(SEED+self.epoch*10000+i).random()<.5:
    images=[a[:,::-1] for a in images];labels[:,1]=1-labels[:,1]
   tensors=[torch.from_numpy(np.ascontiguousarray(a.transpose(2,0,1))) for a in images]
   return tensors[0],tensors[1],torch.from_numpy(labels),r['name']
 def collate(batch):
  raw,enh,labels,names=zip(*batch);target=[]
  for i,l in enumerate(labels):
   t=torch.zeros((len(l),6));t[:,0]=i;t[:,1:]=l;target.append(t)
  return torch.stack(raw),torch.stack(enh),torch.cat(target),names
 hyp=yaml.safe_load((BASE/'road_hyp.yaml').read_text(encoding='utf-8'));hyp['cls']*=4/80;hyp['obj']*=.25;hyp['label_smoothing']=0.
 teacher=torch.load(TEACHER,map_location='cpu',weights_only=False)['model'].float().cuda().eval().requires_grad_(False);guide_feature={}
 teacher.model[4].register_forward_hook(lambda m,i,o:guide_feature.__setitem__('v',o))
 write(ROOT/'training_config.json',dict(status='R2_TRAIN_CONFIG_FROZEN_BEFORE_GRADIENTS',hyp=hyp,source_sha256=sha(HERE/'train_road_twilight_r2.py'),paired_views=2,unique_batch=8,view_batch=16,accumulation=4,anchor_buffers='Copied exactly from initialization into saved EMA; anchors are not optimized.',feature_layer=4,teacher_positive_obj=.2,teacher_gt_class=.4,lambda_positive_kd=.02,lambda_feature=.005,hardware_access=False))
 plans={};all_history={};begin=time.monotonic()
 for mode in ['raw_control','enhance_adapt']:
  random.seed(SEED);np.random.seed(SEED);torch.manual_seed(SEED);torch.cuda.manual_seed_all(SEED);folder=ROOT/'runs'/mode;folder.mkdir(parents=True,exist_ok=False)
  model=torch.load(TEACHER,map_location='cpu',weights_only=False)['model'].float().cuda().train().requires_grad_(True);model.hyp=hyp;model.nc=4;model.gr=1.
  static_buffers={n:b.detach().cpu().clone() for n,b in model.named_buffers() if n.endswith(('running_mean','running_var','num_batches_tracked','anchors'))}
  ema=ModelEMA(model);features={};hook=model.model[4].register_forward_hook(lambda m,i,o:features.__setitem__('v',o))
  dataset=Pairs();loader=torch.utils.data.DataLoader(dataset,batch_size=8,shuffle=False,num_workers=0,pin_memory=True,collate_fn=collate)
  optimizer=torch.optim.AdamW(model.parameters(),lr=5e-5,betas=(.9,.999),weight_decay=1e-5);loss_fn=ComputeLoss(model);history=[];micro=0;updates=0;selected_count=0
  by={p:np.array([i for i,r in enumerate(rows) if r['timeofday']==p]) for p in ['night','dawn/dusk','daytime']}
  for epoch in range(1,EPOCHS+1):
   random.seed(SEED+epoch);np.random.seed(SEED+epoch);torch.manual_seed(SEED+epoch);torch.cuda.manual_seed_all(SEED+epoch)
   rng=np.random.default_rng(SEED+epoch);periods=rng.choice(['night','dawn/dusk','daytime'],3072,p=[.4,.4,.2]);dataset.order=[int(rng.choice(by[p])) for p in periods];dataset.epoch=epoch
   plan=hashlib.sha256('|'.join(rows[i]['name'] for i in dataset.order).encode()).hexdigest()
   if mode=='raw_control':plans[epoch]=plan
   else:assert plan==plans[epoch]
   model.train()
   for m in model.modules():
    if isinstance(m,torch.nn.BatchNorm2d):m.eval()
   lr=1e-5+4e-5*(1+math.cos(math.pi*(epoch-1)/7))/2
   for group in optimizer.param_groups:group['lr']=lr
   optimizer.zero_grad(set_to_none=True);sums=np.zeros(5);batches=0;epoch_start=time.monotonic()
   for bi,(raw,enh,targets,names) in enumerate(loader):
    b=len(raw);x=raw.cuda().float()/255;e=enh.cuda().float()/255;targets=targets.cuda();both=torch.cat([x,e if mode=='enhance_adapt' else x]);alltargets=torch.cat([targets,targets+targets.new_tensor([b,0,0,0,0,0])])
    with torch.no_grad():guide=teacher(x)[1];gf=guide_feature['v'].detach()
    pred=model(both);base,items=loss_fn(pred,alltargets);classes,boxes,indices,anchors=loss_fn.build_targets([p[:b] for p in pred],targets);kd=base.new_zeros(());npos=0
    for hi,(ids,gtcls) in enumerate(zip(indices,classes)):
     ib,ia,gj,gi=ids
     if not len(ib):continue
     q=guide[hi][ib,ia,gj,gi].sigmoid();mask=(q[:,4]>.2)&(q[torch.arange(len(q),device=q.device),5+gtcls]>.4);n=int(mask.sum());npos+=n
     if not n:continue
     target=q[mask]
     for offset in [0,b]:
      s=pred[hi][ib+offset,ia,gj,gi][mask]
      kd+=.5*F.binary_cross_entropy_with_logits(s[:,4],target[:,4])+.5*F.binary_cross_entropy_with_logits(s[:,5:],target[:,5:])+.25*F.smooth_l1_loss(s[:,:4].sigmoid(),target[:,:4])
    kd=kd/6;scale=gf.abs().mean((0,2,3),keepdim=True).clamp_min(.05);feature=F.smooth_l1_loss(features['v']/scale,gf.repeat(2,1,1,1)/scale)
    loss=base+16*(.02*kd+.005*feature);assert torch.isfinite(loss);(loss/4).backward();micro+=1;batches+=1;selected_count+=npos
    if (bi+1)%4==0:
     norm=torch.nn.utils.clip_grad_norm_(model.parameters(),10.);assert torch.isfinite(norm);optimizer.step();optimizer.zero_grad(set_to_none=True);ema.update(model);updates+=1
    sums+=np.r_[items.detach().cpu().numpy(),float(kd.detach()),float(feature.detach())]
    if micro==4:write(folder/'gradient_smoke.json',dict(status='PAIRED_SUPERVISED_TEACHER_GUIDANCE_FIRST_UPDATE_FINITE',loss=float(loss.detach()),grad_norm=float(norm),positive_teacher_anchors=npos,feature_shape=list(features['v'].shape),microbatches=micro,optimizer_updates=updates))
    if micro%96==0:print('TWILIGHT_R2_TRAIN_PROGRESS',mode,epoch,micro,updates,round(float(loss.detach()),5),round(time.monotonic()-begin,1),flush=True)
   assert batches==384
   for n,v in model.named_buffers():
    if n in static_buffers:assert torch.equal(v.detach().cpu(),static_buffers[n]),('Frozen buffer changed',n)
   record=dict(epoch=epoch,microbatches=micro,optimizer_updates=updates,lr=lr,loss_component_means=(sums/batches).tolist(),teacher_positive_anchors_total=selected_count,sampled_period_counts=dict(collections.Counter(periods.tolist())),plan_sha256=plan,batchnorm_and_anchor_buffers_unchanged=True,seconds=time.monotonic()-epoch_start);history.append(record);write(folder/'history.json',history)
   if epoch in CHECKPOINTS:
    ck=ROOT/'frozen'/mode/f'epoch{epoch}';ck.mkdir(parents=True,exist_ok=False);saved=copy.deepcopy(ema.ema).cpu().float().eval()
    for n,v in saved.named_buffers():
     if n in static_buffers:v.copy_(static_buffers[n])
    assert not any(m._forward_hooks for m in saved.modules())
    torch.save(dict(model=saved,epoch=epoch,ema=None,optimizer=None,protocol_sha256=sha(ROOT/'protocol.json')),ck/'model.pt');write(ck/'frozen.json',dict(status='PAIRED_CONSISTENCY_EMA_FROZEN_BEFORE_VALIDATION',mode=mode,epoch=epoch,sha256=sha(ck/'model.pt'),protocol_sha256=sha(ROOT/'protocol.json'),new_test_inference=False));print('TWILIGHT_R2_CHECKPOINT_FROZEN',mode,epoch,flush=True)
   print('TWILIGHT_R2_EPOCH_DONE',mode,epoch,round(record['seconds'],1),flush=True)
  hook.remove();all_history[mode]=history;write(folder/'complete.json',dict(status='MATCHED_PAIRED_TRAINING_COMPLETE',mode=mode,history=history));del model,ema,optimizer,loss_fn,loader,dataset,features;torch.cuda.empty_cache()
 write(ROOT/'training_complete.json',dict(status='BOTH_R2_PAIRED_MODELS_TRAINED',history=all_history,seconds=time.monotonic()-begin,matched_sampler_plans=True,hardware_access=False,sd_written=False));print('TWILIGHT_R2_TRAINING_COMPLETE',flush=True)
if __name__=='__main__':main()
