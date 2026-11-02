"""Choose verifier checkpoint+floor on old320 only; no reused test selection."""
from pathlib import Path
import time
import numpy as np
from road_roi_verifier_common import *
from road_roi_guard_common import gates

def main():
 start=time.monotonic()
 while not (ROOT/'training_complete.json').exists():
  if time.monotonic()-start>2400:raise TimeoutError('Verifier not trained')
  time.sleep(2)
 from road_adapt_eval_core import torch,evaluate_serial_predictions
 torch.set_num_threads(3);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
 out=ROOT/'validation';out.mkdir(exist_ok=False);prepared=read(ROOT/'prepared.json');n=prepared['train_patches'];raw=np.memmap(ROOT/'patches.u8',mode='r',dtype=np.uint8,shape=tuple(prepared['shape']));meta=read(ROOT/'patches.json')[n:];full=read(OLD/'full_predictions.json');roi={r['name']:r['detections'] for r in read(OLD/'center_only_diagnostic_predictions.json')};baseline=read(OLD/'full_metrics.json');policy=read(ROOT/'protocol.json')['roi_policy'];rows=[dict(name=r['name'],timeofday=r['timeofday'],label_path=str(BASE/'dataset/labels/val'/(Path(r['name']).stem+'.txt'))) for r in full];records=[]
 write(out/'protocol.json',dict(status='OLD320_VERIFIER_EPOCH_FLOOR_CHOICES_FROZEN',epochs=CHECKPOINTS,floors=FLOORS,additional_retention='All three time groups totalFP/personFP<=1.10baseline+2; no quality gate relaxation.',fresh_inference=False))
 for epoch in CHECKPOINTS:
  ck=ROOT/'frozen'/f'epoch{epoch}';assert sha(ck/'model.pt')==read(ck/'frozen.json')['sha256'];model=make_model().cuda().eval();model.load_state_dict(torch.load(ck/'model.pt',map_location='cpu',weights_only=False)['state_dict']);probs=[]
  with torch.inference_mode():
   for at in range(n,len(raw),256):
    x=torch.from_numpy(np.ascontiguousarray(np.asarray(raw[at:at+256]).transpose(0,3,1,2))).cuda().float()/255;probs.extend(model(x).sigmoid().flatten().cpu().tolist())
  assert len(probs)==len(meta);by={r['name']:{} for r in full}
  for r,p in zip(meta,probs):by[r['name']][r['roi_index']]=p
  for floor in FLOORS:
   tag=f'epoch{epoch}_floor'+str(floor).replace('.','p');pred={r['name']:verified_fuse(r['detections'],roi[r['name']],policy,by[r['name']],floor) for r in full};m=evaluate_serial_predictions(rows,pred,out,tag);gs=gates(baseline,m)
   for period in ['dawn/dusk','night','daytime']:
    a=baseline['by_time'][period]['classes'];b=m['by_time'][period]['classes'];gs[period+'_fp_retention']=sum(v['fp'] for v in b.values())<=sum(v['fp'] for v in a.values())*1.1+2;gs[period+'_person_fp_retention']=b['person']['fp']<=a['person']['fp']*1.1+2
   r=dict(epoch=epoch,floor=floor,checkpoint=str(ck/'model.pt'),sha256=sha(ck/'model.pt'),metrics=m,gates=gs,passed=all(gs.values()));records.append(r);write(out/'progress.json',records);print('VERIFIER_OLD_VALIDATION',epoch,floor,m['by_time']['dawn/dusk']['mAP50'],m['by_time']['dawn/dusk']['classes']['person']['recall'],m['by_time']['dawn/dusk']['classes']['person']['fp'],r['passed'],flush=True)
 good=[r for r in records if r['passed']];chosen=max(good,key=lambda r:(r['metrics']['by_time']['dawn/dusk']['mAP50'],r['metrics']['all']['mAP50'])) if good else None
 write(ROOT/'selected.json',dict(status='VERIFIER_SELECTED_BEFORE_NEW_TEST',baseline=baseline,records=records,chosen=chosen,qualified=bool(good),protocol_sha256=sha(ROOT/'protocol.json'),new_test_inference=False,hardware_access=False));print('VERIFIER_SELECTION_COMPLETE',None if chosen is None else (chosen['epoch'],chosen['floor']),flush=True)
if __name__=='__main__':main()
