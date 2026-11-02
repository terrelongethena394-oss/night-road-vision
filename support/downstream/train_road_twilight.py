"""Matched full-width FP32 fine-tuning with deterministic twilight exposure sampling."""
from pathlib import Path
import collections,copy,hashlib,json,math,os,random,shutil,sys,time
import numpy as np
from road_twilight_common import *
HERE=Path(__file__).resolve().parent
def main():
 assert (ROOT/'prepare_complete.json').exists();assert sha(TEACHER)==TEACHER_SHA
 os.environ.update(YOLOv5_AUTOINSTALL='false',WANDB_DISABLED='true',COMET_MODE='DISABLED',YOLOV5_CONFIG_DIR=str(ROOT/'config'),CUBLAS_WORKSPACE_CONFIG=':4096:8')
 (ROOT/'config').mkdir(exist_ok=True);shutil.copy2('C:/Windows/Fonts/arial.ttf',ROOT/'config/Arial.ttf')
 shutil.copy2(HERE/'train_road_twilight.py',ROOT/'source/train_road_twilight.py')
 os.chdir(ROOT/'yolov5');sys.path.insert(0,str(ROOT/'yolov5'))
 import torch,yaml
 from utils.dataloaders import create_dataloader
 from utils.loss import ComputeLoss
 from utils.torch_utils import ModelEMA
 torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
 manifest=read(ROOT/'dataset/manifest.json');lookup={Path(r['name']).stem:r for r in manifest if r['split']=='train'};assert len(lookup)==2400
 hyp=yaml.safe_load((BASE/'road_hyp.yaml').read_text(encoding='utf-8'));hyp.update(mosaic=0.,mixup=0.,hsv_h=.005,hsv_s=.1,hsv_v=.05,scale=.10,translate=.02)
 loss_hyp=dict(hyp);loss_hyp['cls']*=4/80;loss_hyp['obj']*=.25;loss_hyp['label_smoothing']=0.
 write(ROOT/'training_config.json',dict(hyp=hyp,loss_hyp=loss_hyp,source_sha256=sha(HERE/'train_road_twilight.py'),train_manifest_sha256=sha(ROOT/'dataset/manifest.json'),initialization_sha256=TEACHER_SHA,precision='FP32, no AMP or TF32',ema='Upstream ModelEMA default decay/tau, same for both modes'))
 allrecords={};sampler_checks={};began=time.monotonic()
 for mode in ['raw_control','enhance_adapt']:
  random.seed(SEED);np.random.seed(SEED);torch.manual_seed(SEED);torch.cuda.manual_seed_all(SEED)
  folder=ROOT/'runs'/mode;folder.mkdir(parents=True,exist_ok=False)
  model=torch.load(TEACHER,map_location='cpu',weights_only=False)['model'].float();model.hyp=loss_hyp;model.nc=4;model.gr=1.;model=model.cuda().train().requires_grad_(True)
  assert all(p.requires_grad for p in model.parameters())
  model_before={k:v.detach().cpu().clone() for k,v in model.state_dict().items()};init_hash=hashlib.sha256(b''.join(v.numpy().tobytes() for v in model_before.values())).hexdigest()
  if mode=='raw_control':shared_initial_hash=init_hash
  else:assert init_hash==shared_initial_hash
  loader,dataset=create_dataloader(str(ROOT/'dataset'/mode/'images/train'),320,16,32,hyp=hyp,augment=True,cache=False,workers=0,shuffle=True,image_weights=True)
  assert len(dataset)==2400;stems=[Path(p).stem for p in dataset.im_files];assert set(stems)==set(lookup)
  if mode=='raw_control':shared_stems=stems
  else:assert stems==shared_stems
  by={period:np.array([i for i,name in enumerate(stems) if lookup[name]['timeofday']==period]) for period in QUOTA}
  loss_fn=ComputeLoss(model);loss_fn.BCEcls.pos_weight=torch.tensor([1.5,1.,1.,1.],device='cuda:0')
  optimizer=torch.optim.AdamW(model.parameters(),lr=1e-4,betas=(.9,.999),weight_decay=1e-5);ema=ModelEMA(model);records=[];steps=0
  for epoch in range(1,EPOCHS+1):
   random.seed(SEED+epoch);np.random.seed(SEED+epoch);torch.manual_seed(SEED+epoch);torch.cuda.manual_seed_all(SEED+epoch)
   rng=np.random.default_rng(SEED+epoch);periods=rng.choice(['night','dawn/dusk','daytime'],size=2400,p=[.25,.5,.25]);indices=[int(rng.choice(by[p])) for p in periods];dataset.indices=indices
   plan_hash=hashlib.sha256('|'.join(stems[i] for i in indices).encode()).hexdigest()
   lr=2e-5+8e-5*(1+math.cos(math.pi*(epoch-1)/max(1,EPOCHS-1)))/2
   for group in optimizer.param_groups:group['lr']=lr
   model.train();sums=np.zeros(3);batches=0;observed=[];epoch_start=time.monotonic()
   for images,targets,paths,shapes in loader:
    assert all('/train/' in str(p).replace('\\','/') for p in paths);observed.extend(Path(p).stem for p in paths)
    x=images.cuda().float()/255;targets=targets.cuda();optimizer.zero_grad(set_to_none=True);pred=model(x);loss,items=loss_fn(pred,targets)
    assert torch.isfinite(loss);loss.backward();norm=torch.nn.utils.clip_grad_norm_(model.parameters(),10.);assert torch.isfinite(norm);optimizer.step();ema.update(model)
    steps+=1;sums+=items.detach().cpu().numpy();batches+=1
    if steps==1:write(folder/'gradient_smoke.json',dict(status='INITIAL_TRAIN_GRADIENT_FINITE',loss=float(loss.detach()),gradient_norm=float(norm),head_shapes=[list(p.shape) for p in pred],initial_state_sha256=init_hash,train_only=True))
    if steps%75==0:print('TWILIGHT_TRAIN_PROGRESS',mode,epoch,steps,round(float(loss.detach()),5),round(time.monotonic()-began,1),flush=True)
   assert batches==150 and len(observed)==2400
   order_hash=hashlib.sha256('|'.join(observed).encode()).hexdigest()
   if mode=='raw_control':sampler_checks[epoch]=(plan_hash,order_hash)
   else:assert sampler_checks[epoch]==(plan_hash,order_hash),'Matched sampler or augmentation loader order changed'
   record=dict(epoch=epoch,steps=steps,lr=lr,mean_supervised_components=(sums/batches).tolist(),epoch_seconds=time.monotonic()-epoch_start,sampled_period_counts=dict(collections.Counter(periods.tolist())),unique_training_images=len(set(observed)),plan_sha256=plan_hash,actual_path_order_sha256=order_hash);records.append(record);write(folder/'history.json',records)
   if epoch in CHECKPOINTS:
    checkpoint=ROOT/'frozen'/mode/f'epoch{epoch}';checkpoint.mkdir(parents=True,exist_ok=False);saved=copy.deepcopy(ema.ema).cpu().float().eval()
    torch.save(dict(epoch=epoch,model=saved,ema=None,optimizer=None,updates=ema.updates,protocol_sha256=sha(ROOT/'protocol.json')),checkpoint/'model.pt')
    write(checkpoint/'frozen.json',dict(status='EMA_CHECKPOINT_FROZEN_BEFORE_VALIDATION',mode=mode,epoch=epoch,sha256=sha(checkpoint/'model.pt'),protocol_sha256=sha(ROOT/'protocol.json'),validation_used_for_gradients=False,fresh_test_inference=False));print('TWILIGHT_CHECKPOINT_FROZEN',mode,epoch,flush=True)
   print('TWILIGHT_EPOCH_DONE',mode,epoch,round(record['epoch_seconds'],1),flush=True)
  allrecords[mode]=records;write(folder/'complete.json',dict(status='MATCHED_FULL_WIDTH_TRAINING_COMPLETE',mode=mode,epochs=EPOCHS,records=records,same_initial_state_sha256=init_hash,hardware_access=False,sd_written=False))
  del loader,dataset,optimizer,loss_fn,model,ema,model_before;torch.cuda.empty_cache()
 write(ROOT/'training_complete.json',dict(status='BOTH_MATCHED_16_EPOCH_MODELS_FROZEN',records=allrecords,seconds=time.monotonic()-began,matched_sampler_order_all_epochs=True,hardware_access=False,sd_written=False));print('TWILIGHT_MATCHED_TRAINING_COMPLETE',flush=True)
if __name__=='__main__':main()
