"""Actual six-epoch mixed raw/enhanced FP32 adaptation, same deployable graph."""
import copy,hashlib,math,os,random,shutil,sys,time
import cv2,numpy as np
from road_enhanceadapt_common import *

def main():
 assert (ROOT/'prepared.json').exists() and not (ROOT/'training_config.json').exists()
 protocol=read(ROOT/'protocol.json');assert sha(INITIAL)==protocol['initial_checkpoint_sha256']
 assert sha(ROOT/'training_manifest.json')==read(ROOT/'prepared.json')['manifest_sha256']
 shutil.copy2(Path(__file__),ROOT/'source'/Path(__file__).name)
 os.environ.update(YOLOv5_AUTOINSTALL='false',WANDB_DISABLED='true',COMET_MODE='DISABLED',CUBLAS_WORKSPACE_CONFIG=':4096:8')
 os.chdir(DATA/'yolov5');sys.path.insert(0,str(DATA/'yolov5'))
 import torch,yaml
 from utils.loss import ComputeLoss
 from utils.torch_utils import ModelEMA
 torch.set_num_threads(4);cv2.setNumThreads(1)
 torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
 torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
 random.seed(SEED);np.random.seed(SEED);torch.manual_seed(SEED);torch.cuda.manual_seed_all(SEED)
 rows=read(ROOT/'training_manifest.json');assert len(rows)==2400
 for r in rows:
  if r['enhanced_full']:assert sha(r['enhanced_full']['image'])==r['enhanced_full']['sha256']
 class Views(torch.utils.data.Dataset):
  epoch=1
  def __len__(self):return len(rows)*2
  def __getitem__(self,i):
   r=rows[i//2];v=0 if i%2==0 else 1+(int(hashlib.sha256(r['name'].encode()).hexdigest()[:8],16)+self.epoch-1)%3
   rng=np.random.default_rng(SEED+self.epoch*10000+i)
   enhanced=v==0 and r['enhanced_full'] is not None and rng.random()<.5
   rec=r['enhanced_full'] if enhanced else r['views'][v]
   im=cv2.imread(rec['image'])[:,:,::-1];g=np.asarray(rec['labels'],np.float32).reshape(-1,5).copy()
   assert im.shape==(320,320,3) and np.all(im[:64]==114) and np.all(im[256:]==114)
   if rng.random()<.5:im=im[:,::-1];g[:,1]=1-g[:,1]
   return torch.from_numpy(np.ascontiguousarray(im.transpose(2,0,1))),torch.from_numpy(g),int(enhanced)
 def collate(batch):
  ims,labels,enhanced=zip(*batch);out=[]
  for i,l in enumerate(labels):
   a=torch.zeros((len(l),6));a[:,0]=i;a[:,1:]=l;out.append(a)
  return torch.stack(ims),torch.cat(out),sum(enhanced)
 hyp=yaml.safe_load((DATA/'road_hyp.yaml').read_text());hyp['cls']*=4/80;hyp['obj']*=.25;hyp['label_smoothing']=0.
 model=torch.load(INITIAL,map_location='cpu',weights_only=False)['model'].float().cuda().train().requires_grad_(True)
 model.hyp=hyp;model.nc=4;model.gr=1.
 buffers={n:b.detach().cpu().clone() for n,b in model.named_buffers() if n.endswith(('running_mean','running_var','num_batches_tracked','anchors'))}
 initial=[p.detach().cpu().clone() for p in model.parameters()]
 data=Views();loader=torch.utils.data.DataLoader(data,batch_size=16,shuffle=True,num_workers=0,pin_memory=True,collate_fn=collate)
 optimizer=torch.optim.AdamW(model.parameters(),lr=3e-5,betas=(.9,.999),weight_decay=1e-5)
 loss_fn=ComputeLoss(model);ema=ModelEMA(model)
 write(ROOT/'training_config.json',dict(status='MIXED_ENHANCEMENT_CONFIG_FROZEN_BEFORE_FIRST_GRADIENT',
  hyp=hyp,fp32=True,batch=16,accumulation=2,epochs=EPOCHS,checkpoints=CHECKPOINTS,
  BN_frozen=True,anchors_frozen=True,protocol_sha256=sha(ROOT/'protocol.json'),source_sha256=sha(Path(__file__))))
 begin=time.monotonic();history=[];updates=0
 for epoch in range(1,EPOCHS+1):
  data.epoch=epoch;random.seed(SEED+epoch);np.random.seed(SEED+epoch);torch.manual_seed(SEED+epoch);torch.cuda.manual_seed_all(SEED+epoch)
  lr=5e-6+2.5e-5*(1+math.cos(math.pi*(epoch-1)/(EPOCHS-1)))/2
  for group in optimizer.param_groups:group['lr']=lr
  model.train()
  for m in model.modules():
   if isinstance(m,torch.nn.BatchNorm2d):m.eval()
  optimizer.zero_grad(set_to_none=True);sums=np.zeros(3);n_enh=0;start=time.monotonic()
  for bi,(images,target,enhanced) in enumerate(loader,1):
   x=images.cuda().float()/255;target=target.cuda();pred=model(x);loss,items=loss_fn(pred,target)
   assert torch.isfinite(loss);(loss/2).backward();sums+=items.detach().cpu().numpy();n_enh+=enhanced
   if bi%2==0:
    norm=torch.nn.utils.clip_grad_norm_(model.parameters(),10.);assert torch.isfinite(norm)
    optimizer.step();optimizer.zero_grad(set_to_none=True);ema.update(model);updates+=1
    if updates==1:write(ROOT/'gradient_smoke.json',dict(status='ACTUAL_FIRST_GRADIENT_FINITE',loss=float(loss.detach()),grad_norm=float(norm),head_shapes=[list(p.shape) for p in pred]))
   if bi%75==0:print('ENHANCEADAPT_TRAIN',epoch,bi,len(loader),'loss',round(float(loss.detach()),5),'enhanced',n_enh,'seconds',round(time.monotonic()-begin),flush=True)
  assert bi==300
  for n,b in model.named_buffers():
   if n in buffers:assert torch.equal(b.detach().cpu(),buffers[n]),n
  record=dict(epoch=epoch,lr=lr,updates=updates,loss_components=(sums/300).tolist(),enhanced_samples=n_enh,raw_samples=4800-n_enh,seconds=time.monotonic()-start)
  history.append(record);write(ROOT/'history.json',history)
  if epoch in CHECKPOINTS:
   folder=ROOT/'frozen'/f'epoch{epoch}';folder.mkdir(parents=True)
   saved=copy.deepcopy(ema.ema).cpu().float().eval()
   for n,b in saved.named_buffers():
    if n in buffers:b.copy_(buffers[n])
   changed=sum(not torch.equal(a,b.detach().cpu()) for a,b in zip(initial,saved.parameters()));assert changed>0
   torch.save(dict(model=saved,epoch=epoch,ema=None,optimizer=None,protocol_sha256=sha(ROOT/'protocol.json')),folder/'model.pt')
   write(folder/'frozen.json',dict(status='ACTUAL_MIXED_ENHANCEMENT_CHECKPOINT_FROZEN',epoch=epoch,changed_parameter_tensors=changed,sha256=sha(folder/'model.pt'),BN_and_anchors_unchanged=True,fresh_test_inference=False))
   print('ENHANCEADAPT_CHECKPOINT',epoch,changed,flush=True)
 write(ROOT/'training_complete.json',dict(status='SIX_EPOCHS_MIXED_RAW_ENHANCED_TRAINING_COMPLETE',history=history,seconds=time.monotonic()-begin,hardware_access=False,sd_written=False))
 print('ENHANCEADAPT_TRAINING_COMPLETE',flush=True)

if __name__=='__main__':main()
