"""Real class+box regression training using original train labels only."""
import math,shutil,time
import numpy as np
from car_box_refine_common import *

def main():
 assert (ROOT/'prepared.json').exists() and not (ROOT/'training_config.json').exists()
 import torch
 torch.set_num_threads(4);torch.manual_seed(SEED);torch.cuda.manual_seed_all(SEED)
 torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
 prepared=read(ROOT/'prepared.json')
 for name,digest in prepared['sha256'].items():assert sha(ROOT/name)==digest
 n=prepared['shape'][0];pixels=np.memmap(ROOT/'patches.u8',mode='r',dtype=np.uint8,shape=(n,32,32,3));meta=np.fromfile(ROOT/'metadata.f32','<f4').reshape(n,6)
 targets=np.fromfile(ROOT/'targets.u8',np.uint8);deltas=np.fromfile(ROOT/'deltas.f32','<f4').reshape(n,4);records=read(ROOT/'patches.json')
 fit=np.array([r['split']=='train' for r in records]);positive=np.flatnonzero(fit&(targets==1));negative=np.flatnonzero(fit&(targets==0))
 hard=np.array([i for i in negative if records[i]['box'][4]>=.25]);assert len(hard)>100
 val=np.flatnonzero(~fit);boxes=np.asarray([records[i]['box'][:4] for i in val],np.float32);gt=np.asarray([records[i]['gt'] for i in val],np.float32)
 model=make_model().cuda();assert sum(p.numel() for p in model.parameters())==17549
 initial_path=PREV/'frozen/epoch30/model.pt';old=torch.load(initial_path,map_location='cpu',weights_only=False)['state_dict']
 model.load_state_dict({k:v for k,v in old.items() if not k.startswith('fc2.')},strict=False)
 with torch.no_grad():
  model.fc2.weight.zero_();model.fc2.bias.zero_();model.fc2.weight[0].copy_(old['fc2.weight'][0]);model.fc2.bias[0].copy_(old['fc2.bias'][0])
 optimizer=torch.optim.AdamW(model.parameters(),lr=.0005,weight_decay=.0001);(ROOT/'frozen').mkdir()
 write(ROOT/'training_config.json',dict(status='BOX_REFINEMENT_CONFIG_FROZEN_BEFORE_GRADIENTS',parameters=17549,epochs=EPOCHS,checkpoints=CHECKPOINTS,
  initial_features_sha256=sha(initial_path),loss='BCE+5*SmoothL1(beta.1) positives',hard_negatives=len(hard),source_sha256=sha(Path(__file__)),protocol_sha256=sha(ROOT/'protocol.json')))
 shutil.copy2(Path(__file__),ROOT/'source'/Path(__file__).name)
 def batch(ids):
  x=torch.from_numpy(np.ascontiguousarray(np.asarray(pixels[ids]).transpose(0,3,1,2))).cuda().float()/255
  return x,torch.from_numpy(meta[ids]).cuda()
 history=[];begin=time.monotonic()
 for epoch in range(1,EPOCHS+1):
  rng=np.random.default_rng(SEED+epoch);ids=np.r_[rng.choice(positive,3000),rng.choice(hard,1500),rng.choice(negative,1500)];rng.shuffle(ids)
  lr=.00005+.00045*(1+math.cos(math.pi*(epoch-1)/(EPOCHS-1)))/2
  for group in optimizer.param_groups:group['lr']=lr
  model.train();losses=[];regloss=[]
  for at in range(0,len(ids),128):
   ii=ids[at:at+128];x,m=batch(ii);t=torch.from_numpy(targets[ii].astype(np.float32)).cuda();delta=torch.from_numpy(deltas[ii]).cuda()
   out=model(x,m);cls=torch.nn.functional.binary_cross_entropy_with_logits(out[:,0],t)
   reg=torch.nn.functional.smooth_l1_loss(out[t==1,1:],delta[t==1],beta=.1);loss=cls+5*reg
   assert torch.isfinite(loss);optimizer.zero_grad(set_to_none=True);loss.backward();norm=torch.nn.utils.clip_grad_norm_(model.parameters(),5.);assert torch.isfinite(norm);optimizer.step()
   losses.append(float(loss.detach()));regloss.append(float(reg.detach()))
   if epoch==1 and at==0:write(ROOT/'gradient_smoke.json',dict(status='CLASS_AND_BOX_HEAD_GRADIENTS_FINITE',loss=float(loss.detach()),regression=float(reg.detach()),norm=float(norm)))
  model.eval();pred=[]
  with torch.inference_mode():
   for at in range(0,len(val),256):
    x,m=batch(val[at:at+256]);pred.extend(model(x,m).cpu().tolist())
  pred=np.asarray(pred,np.float32);truth=targets[val];prob=1/(1+np.exp(-pred[:,0]));ranks=np.empty(len(val),np.float64);ranks[np.argsort(prob,kind='stable')]=np.arange(1,len(val)+1)
  npos=int(truth.sum());auc=float((ranks[truth==1].sum()-npos*(npos+1)/2)/(npos*(len(val)-npos)))
  wh=boxes[:,2:4]-boxes[:,:2];d=np.clip(pred[:,1:],-1.5,1.5);center=(boxes[:,2:4]+boxes[:,:2])*.5+d[:,:2]*wh;size=wh*np.exp(d[:,2:]);ref=np.c_[center-size*.5,center+size*.5]
  def iou(a):
   inter=np.maximum(0,np.minimum(a[:,2:4],gt[:,2:4])-np.maximum(a[:,:2],gt[:,:2])).prod(1)
   return inter/(np.maximum(0,a[:,2:4]-a[:,:2]).prod(1)+np.maximum(0,gt[:,2:4]-gt[:,:2]).prod(1)-inter+1e-9)
  rec=dict(epoch=epoch,lr=lr,train_loss=float(np.mean(losses)),train_regression=float(np.mean(regloss)),internal_val_auc=auc,
   internal_positive_iou_before=float(np.mean(iou(boxes)[truth==1])),internal_positive_iou_after=float(np.mean(iou(ref)[truth==1])),seconds=time.monotonic()-begin)
  history.append(rec);write(ROOT/'history.json',history)
  if epoch in CHECKPOINTS:
   folder=ROOT/'frozen'/f'epoch{epoch}';folder.mkdir();torch.save(dict(state_dict={k:v.detach().cpu().float() for k,v in model.state_dict().items()},epoch=epoch,parameters=17549),folder/'model.pt')
   write(folder/'frozen.json',dict(status='CLASS_AND_BOX_REFINER_FROZEN_BEFORE_DEVELOPMENT',sha256=sha(folder/'model.pt'),epoch=epoch))
  if epoch%10==0:print('BOX_REFINE_TRAIN',epoch,'AUC',round(auc,4),'IoU',round(rec['internal_positive_iou_before'],4),round(rec['internal_positive_iou_after'],4),'seconds',round(rec['seconds']),flush=True)
 write(ROOT/'training_complete.json',dict(status='EIGHTY_EPOCHS_REAL_BOX_REFINEMENT_COMPLETE',parameters=17549,history=history,detector_unchanged=True,hardware_access=False,sd_written=False))
 print('BOX_REFINE_TRAINING_COMPLETE',flush=True)

if __name__=='__main__':main()
