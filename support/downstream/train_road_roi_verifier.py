"""Small proposal verifier, true training GT only; no detector retraining."""
import math,shutil,time
from pathlib import Path
import numpy as np
from road_roi_verifier_common import *
PARAMETERS=3729
LR_MAX=.001

def main():
 started=time.monotonic()
 while not (ROOT/'prepared.json').exists():
  if time.monotonic()-started>1800:raise TimeoutError('Verifier training patches not ready')
  time.sleep(2)
 import torch
 torch.set_num_threads(3);torch.manual_seed(SEED);torch.cuda.manual_seed_all(SEED);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
 prepared=read(ROOT/'prepared.json');assert sha(ROOT/'patches.u8')==prepared['patches_sha256'] and sha(ROOT/'targets.i8')==prepared['targets_sha256'];n=prepared['train_patches'];raw=np.memmap(ROOT/'patches.u8',mode='r',dtype=np.uint8,shape=tuple(prepared['shape']));labels=np.fromfile(ROOT/'targets.i8',np.int8)[:n];positives=np.flatnonzero(labels==1);negatives=np.flatnonzero(labels==0)
 model=make_model().cuda();assert sum(p.numel() for p in model.parameters())==PARAMETERS;optimizer=torch.optim.AdamW(model.parameters(),lr=LR_MAX,weight_decay=.0001);(ROOT/'frozen').mkdir();shutil.copy2(Path(__file__),ROOT/'source'/Path(__file__).name)
 write(ROOT/'training_config.json',dict(status='VERIFIER_CONFIG_FROZEN_BEFORE_GRADIENTS',parameters=PARAMETERS,seed=SEED,epochs=EPOCHS,checkpoints=CHECKPOINTS,balanced_samples_per_epoch=4000,batch=128,augmentations='None; exact deployed nearest-center RGB565 crop.',loss='Binary BCEWithLogits, train labels only.',optimizer=dict(name='AdamW',lr_max=LR_MAX,lr_min=.0001,weight_decay=.0001,clip=5),amp=False,tf32=False,data_sha256=sha(ROOT/'prepared.json'),source_sha256=sha(Path(__file__))))
 history=[];begin=time.monotonic()
 for epoch in range(1,EPOCHS+1):
  rng=np.random.default_rng(SEED+epoch);idx=np.r_[rng.choice(positives,2000),rng.choice(negatives,2000)];rng.shuffle(idx);model.train();lr=.0001+(LR_MAX-.0001)*(1+math.cos(math.pi*(epoch-1)/(EPOCHS-1)))/2
  for group in optimizer.param_groups:group['lr']=lr
  losses=[]
  for at in range(0,len(idx),128):
   ids=idx[at:at+128];x=torch.from_numpy(np.ascontiguousarray(np.asarray(raw[ids]).transpose(0,3,1,2))).cuda().float()/255;y=torch.from_numpy(labels[ids].astype(np.float32)).cuda();optimizer.zero_grad(set_to_none=True);logits=model(x).flatten();loss=torch.nn.functional.binary_cross_entropy_with_logits(logits,y);assert torch.isfinite(loss);loss.backward();norm=torch.nn.utils.clip_grad_norm_(model.parameters(),5.);assert torch.isfinite(norm);optimizer.step();losses.append(float(loss.detach()))
  r=dict(epoch=epoch,lr=lr,mean_bce=float(np.mean(losses)),seconds=time.monotonic()-begin);history.append(r);write(ROOT/'history.json',history)
  if epoch in CHECKPOINTS:
   folder=ROOT/'frozen'/f'epoch{epoch}';folder.mkdir();torch.save(dict(state_dict={k:v.detach().cpu().float() for k,v in model.state_dict().items()},epoch=epoch,parameters=PARAMETERS,training_config_sha256=sha(ROOT/'training_config.json')),folder/'model.pt');write(folder/'frozen.json',dict(status='VERIFIER_CHECKPOINT_FROZEN_BEFORE_SELECTION',epoch=epoch,sha256=sha(folder/'model.pt')))
  print('VERIFIER_TRAIN_EPOCH',epoch,round(r['mean_bce'],5),round(r['seconds'],1),flush=True)
 write(ROOT/'training_complete.json',dict(status='TRAIN_ONLY_VERIFIER_TRAINED',history=history,source_train_images=3000,parameters=PARAMETERS,detector_unchanged=True,hardware_access=False,sd_written=False));print('VERIFIER_TRAIN_COMPLETE',flush=True)
if __name__=='__main__':main()
