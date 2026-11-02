"""All checkpoint choice uses only the old validation; fresh test remains unread."""
from pathlib import Path
import time
import cv2,numpy as np
from road_twilight_common import *
def evaluate(weights,rows,loader,folder,tag):
 from road_adapt_eval_core import torch,evaluate_serial_predictions,non_max_suppression,scale_boxes
 folder=Path(folder);folder.mkdir(parents=True,exist_ok=False);torch.set_num_threads(2);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
 model=torch.load(weights,map_location='cpu',weights_only=False)['model'].float().fuse().cuda().eval();predictions={}
 with torch.inference_mode():
  for at in range(0,len(rows),8):
   rs=rows[at:at+8];images=[loader(r).transpose(2,0,1) for r in rs];x=torch.from_numpy(np.ascontiguousarray(np.stack(images))).cuda().float()/255
   ps=non_max_suppression(model(x),.001,.6,max_det=300)
   for r,p in zip(rs,ps):
    if len(p):scale_boxes((320,320),p[:,:4],(240,400),ratio_pad=((.8,.8),(0.,64.)))
    predictions[r['name']]=p.cpu().float().tolist()
 del model;torch.cuda.empty_cache();return evaluate_serial_predictions(rows,predictions,folder,tag)
def gates(original,control,raw,enh):
 a=enh['by_time'];b=original['by_time'];c=control['by_time'];p=a['dawn/dusk']['classes']['person'];cp=c['dawn/dusk']['classes']['person']
 return dict(dusk_vs_original=a['dawn/dusk']['mAP50']>=b['dawn/dusk']['mAP50']+.01,dusk_vs_matched_raw=a['dawn/dusk']['mAP50']>=c['dawn/dusk']['mAP50']+.005,dusk_runtime_enhancement=a['dawn/dusk']['mAP50']>=raw['by_time']['dawn/dusk']['mAP50']+.005,overall=enh['all']['mAP50']>=original['all']['mAP50']+.005,night=a['night']['mAP50']>=max(b['night']['mAP50'],c['night']['mAP50']-.005),day=a['daytime']['mAP50']>=b['daytime']['mAP50']-.005,dusk_person_recall=p['recall']>=cp['recall'],dusk_fp=sum(v['fp'] for v in a['dawn/dusk']['classes'].values())<=1.1*sum(v['fp'] for v in c['dawn/dusk']['classes'].values())+2,dusk_person_fp=p['fp']<=cp['fp']*1.1+2)
def main():
 out=ROOT/'validation';out.mkdir(exist_ok=False)
 write(ROOT/'selection_addendum.json',dict(status='FROZEN_BEFORE_VALIDATION_AND_FRESH_PREDICTIONS',initial_control='Original epoch0 is an admissible raw fallback; all adapted raw checkpoints must pass previously frozen retention guards.',fresh_primary_uncertainty='1000 paired image/group bootstrap replicates in dawn/dusk, percentile95% CI of enhanced-adapt+enhanced minus selected matched-control+raw mAP50. For reliable-enhancement claim and default enhanced-input deployment require lower bound>0 in addition to frozen point gates. One primary contrast; no new checkpoint choices after fresh outcomes.',bootstrap_seed=2026102746,bootstrap_replicates=1000,hardware_access=False))
 rows=[{**r,'label_path':str(BASE/'dataset/labels/val'/(Path(r['name']).stem+'.txt'))} for r in read(ROOT/'dataset/manifest.json') if r['split']=='val'];assert len(rows)==320
 def loader(kind):return lambda r:cv2.imread(str(ROOT/'dataset'/kind/'images/val'/(Path(r['name']).stem+'.png')))[:,:,::-1].copy()
 original=evaluate(TEACHER,rows,loader('raw_control'),out/'original','original');records={};started=time.monotonic()
 for mode in ['raw_control','enhance_adapt']:
  records[mode]=[]
  for epoch in CHECKPOINTS:
   ck=ROOT/'frozen'/mode/f'epoch{epoch}'
   while not (ck/'frozen.json').exists():
    if time.monotonic()-started>7200:raise TimeoutError('Matched checkpoints not ready')
    time.sleep(2)
   frozen=read(ck/'frozen.json');assert sha(ck/'model.pt')==frozen['sha256'];tag=f'{mode}_e{epoch}';raw=evaluate(ck/'model.pt',rows,loader('raw_control'),out/(tag+'_raw'),tag+'_raw')
   r=dict(mode=mode,epoch=epoch,weights=str(ck/'model.pt'),sha256=frozen['sha256'],raw=raw)
   if mode=='enhance_adapt':r['enhanced']=evaluate(ck/'model.pt',rows,loader('enhance_adapt'),out/(tag+'_enh'),tag+'_enh')
   records[mode].append(r);write(out/'progress.json',dict(original=original,records=records));print('TWILIGHT_VALIDATION_CHECKPOINT',mode,epoch,raw['by_time']['dawn/dusk']['mAP50'],r.get('enhanced',raw)['by_time']['dawn/dusk']['mAP50'],flush=True)
 controls=[dict(mode='original',epoch=0,weights=str(TEACHER),sha256=TEACHER_SHA,raw=original)]
 for r in records['raw_control']:
  m=r['raw'];a=m['by_time'];b=original['by_time'];good=m['all']['mAP50']>=original['all']['mAP50']-.005 and a['night']['mAP50']>=b['night']['mAP50']-.005 and a['daytime']['mAP50']>=b['daytime']['mAP50']-.005
  r['raw_retention_passed']=good
  if good:controls.append(r)
 control=max(controls,key=lambda r:(r['raw']['by_time']['dawn/dusk']['mAP50'],r['raw']['all']['mAP50']))
 passing=[]
 for r in records['enhance_adapt']:
  r['gates']=gates(original,control['raw'],r['raw'],r['enhanced']);r['passed']=all(r['gates'].values())
  if r['passed']:passing.append(r)
 pool=passing or records['enhance_adapt'];candidate=max(pool,key=lambda r:(r['enhanced']['by_time']['dawn/dusk']['mAP50'],r['enhanced']['all']['mAP50']))
 frozen=dict(status='TWILIGHT_MODELS_FROZEN_BEFORE_NEW_HOLDOUT',control={k:control[k] for k in ['mode','epoch','weights','sha256']},candidate={k:candidate[k] for k in ['mode','epoch','weights','sha256']},enhancement_validation_accepted=bool(passing),candidate_gates=candidate['gates'],records=records,original=original,control_metrics=control['raw'],candidate_raw=candidate['raw'],candidate_enhanced=candidate['enhanced'],protocol_sha256=sha(ROOT/'protocol.json'),addendum_sha256=sha(ROOT/'selection_addendum.json'),fresh_inference_performed=False,hardware_access=False,sd_written=False)
 write(ROOT/'selected.json',frozen);print('TWILIGHT_SELECTION_COMPLETE',control['epoch'],candidate['epoch'],'enhancement_accepted',bool(passing),candidate['gates'],flush=True)
if __name__=='__main__':main()
