"""Small actual learned FP32 RGB+geometry verifier; frozen detector stays intact."""
import math,shutil,time
import numpy as np
from car_patch_verifier_common import *

def main():
 assert (ROOT/'prepared.json').exists() and not (ROOT/'training_config.json').exists()
 import torch
 torch.set_num_threads(4);torch.manual_seed(SEED);torch.cuda.manual_seed_all(SEED)
 torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
 prepared=read(ROOT/'prepared.json')
 for n,key in [('patches.u8','patches_sha256'),('metadata.f32','metadata_sha256'),('targets.u8','targets_sha256'),('patches.json','records_sha256')]:assert sha(ROOT/n)==prepared[key]
 n=prepared['shape'][0];pixels=np.memmap(ROOT/'patches.u8',mode='r',dtype=np.uint8,shape=(n,32,32,3))
 meta=np.fromfile(ROOT/'metadata.f32','<f4').reshape(n,6);target=np.fromfile(ROOT/'targets.u8',np.uint8);records=read(ROOT/'patches.json')
 fit=np.array([r['split']=='train' for r in records]);pos=np.flatnonzero(fit&(target==1));neg=np.flatnonzero(fit&(target==0));val=np.flatnonzero(~fit)
 model=make_model().cuda();parameters=sum(p.numel() for p in model.parameters());assert parameters==17417
 optimizer=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.0001);(ROOT/'frozen').mkdir()
 write(ROOT/'training_config.json',dict(status='FP32_PATCH_VERIFIER_CONFIG_FROZEN_BEFORE_GRADIENTS',parameters=parameters,
  protocol_sha256=sha(ROOT/'protocol.json'),source_sha256=sha(Path(__file__)),prepared_sha256=sha(ROOT/'prepared.json'),
  balanced_per_epoch=6000,batch=128,checkpoints=CHECKPOINTS,epochs=EPOCHS,seed=SEED,TF32=False))
 shutil.copy2(Path(__file__),ROOT/'source'/Path(__file__).name)
 def tensor(ids,flip=False):
  a=np.ascontiguousarray(np.asarray(pixels[ids]).transpose(0,3,1,2));x=torch.from_numpy(a).cuda().float()/255
  if flip:x=torch.flip(x,[-1])
  return x,torch.from_numpy(np.ascontiguousarray(meta[ids])).cuda()
 initial={k:v.detach().cpu().clone() for k,v in model.state_dict().items()};history=[];begin=time.monotonic()
 for epoch in range(1,EPOCHS+1):
  rng=np.random.default_rng(SEED+epoch);ids=np.r_[rng.choice(pos,3000),rng.choice(neg,3000)];rng.shuffle(ids)
  lr=.0001+.0009*(1+math.cos(math.pi*(epoch-1)/(EPOCHS-1)))/2
  for group in optimizer.param_groups:group['lr']=lr
  model.train();losses=[]
  for at in range(0,len(ids),128):
   ii=ids[at:at+128];x,m=tensor(ii,bool(rng.random()<.5));y=torch.from_numpy(target[ii].astype(np.float32)).cuda()
   optimizer.zero_grad(set_to_none=True);logits=model(x,m);loss=torch.nn.functional.binary_cross_entropy_with_logits(logits,y)
   assert torch.isfinite(loss);loss.backward();norm=torch.nn.utils.clip_grad_norm_(model.parameters(),5.);assert torch.isfinite(norm);optimizer.step();losses.append(float(loss.detach()))
   if epoch==1 and at==0:write(ROOT/'gradient_smoke.json',dict(status='FIRST_REAL_VERIFIER_GRADIENT_FINITE',loss=float(loss.detach()),norm=float(norm)))
  model.eval();ll=[]
  with torch.inference_mode():
   for at in range(0,len(val),256):
    x,m=tensor(val[at:at+256]);ll.extend(model(x,m).cpu().tolist())
  logits=np.asarray(ll);truth=target[val];p=1/(1+np.exp(-logits));
  order=np.argsort(p,kind='stable');ranks=np.empty(len(p),np.float64);ranks[order]=np.arange(1,len(p)+1)
  # Rank-AUC is a training diagnostic; final detector metrics use held-out boxes.
  np_=int(truth.sum());nn_=len(truth)-np_;auc=float((ranks[truth==1].sum()-np_*(np_+1)/2)/(np_*nn_))
  bce=float(np.mean(np.logaddexp(0,logits)-truth*logits))
  record=dict(epoch=epoch,lr=lr,train_bce=float(np.mean(losses)),internal_source_val_bce=bce,internal_source_val_auc=auc,seconds=time.monotonic()-begin)
  history.append(record);write(ROOT/'history.json',history)
  if epoch in CHECKPOINTS:
   folder=ROOT/'frozen'/f'epoch{epoch}';folder.mkdir();state={k:v.detach().cpu().float() for k,v in model.state_dict().items()}
   changed=sum(not torch.equal(initial[k],v) for k,v in state.items());assert changed>0
   torch.save(dict(state_dict=state,parameters=parameters,epoch=epoch,protocol_sha256=sha(ROOT/'protocol.json')),folder/'model.pt')
   write(folder/'frozen.json',dict(status='ACTUAL_TRAINED_PATCH_VERIFIER_FROZEN_BEFORE_DEVELOPMENT',sha256=sha(folder/'model.pt'),changed_tensors=changed,internal_val_auc=auc))
  if epoch%5==0:print('PATCH_VERIFIER_TRAIN',epoch,'BCE',round(record['train_bce'],4),'internalAUC',round(auc,4),'seconds',round(record['seconds']),flush=True)
 write(ROOT/'training_complete.json',dict(status='SIXTY_EPOCHS_ACTUAL_PATCH_VERIFIER_TRAINED',parameters=parameters,source_train_groups=480,internal_val_groups=120,
  history=history,detector_unchanged=True,hardware_access=False,sd_written=False))
 print('PATCH_VERIFIER_TRAINING_COMPLETE',parameters,flush=True)

if __name__=='__main__':main()
