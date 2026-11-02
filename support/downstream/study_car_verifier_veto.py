"""Separate veto-only hypothesis after continuous-score verifier failure."""
from pathlib import Path
import shutil,time
import numpy as np
import road_accuracy_common as ac
from road_numpy_eval import evaluate
from car_patch_verifier_common import *
from evaluate_car_patch_verifier import cohorts,conditions

def fuse_veto(raw,views,probs,threshold,mode,weight=.65):
 a=np.asarray(raw,np.float32).reshape(-1,6);strong=a[a[:,4]>=.25];extra=[]
 for pp,qq in zip(views,probs):
  for p,q in zip(np.asarray(pp,np.float32).reshape(-1,6),qq):
   if p[4]<.05:continue
   if mode=='hard' and q<threshold:continue
   if len(strong):
    area=np.maximum(0,p[2:4]-p[:2]).prod();oa=np.maximum(0,strong[:,2:4]-strong[:,:2]).prod(1)
    inter=np.maximum(0,np.minimum(p[2:4],strong[:,2:4])-np.maximum(p[:2],strong[:,:2])).prod(1)
    if np.any((inter/(area+oa-inter+1e-9)>=.3)|(inter/(np.minimum(area,oa)+1e-9)>=.8)):continue
   b=p.copy();factor=min(np.float32(1),np.float32(q)/np.float32(threshold)) if mode=='taper' else np.float32(1)
   b[4]*=np.float32(weight)*factor
   if b[4]>=.001:extra.append(b)
 return ac.nms_numpy(np.concatenate([a,np.asarray(extra,np.float32).reshape(-1,6)]),.6,300)

def main():
 assert not read(ROOT/'selected.json')['qualified'] and not (ROOT/'veto_protocol.json').exists()
 protocol=dict(status='VETO_HYPOTHESIS_FROZEN_AFTER_CONTINUOUS_SCORE_FAILURE_BEFORE_VETO_SEARCH',
  previous_failure_sha256=sha(ROOT/'selected.json'),
  reason='Uniform probability multiplication lowers scores of real vehicles too. Test rejecting only obvious background while keeping original scores for other zoom proposals.',
  classifier_checkpoints=CHECKPOINTS,thresholds=[.02,.05,.1,.2,.3],modes=['hard','taper'],weight=.65,
  rules='Hard:reject added proposal if verifier probability<threshold. Taper:only below threshold multiply score by q/threshold. Otherwise unchanged original0.65 zoom score. Prior4view boxes untouched.',
  gates='All original AP/P/R,newFP reduction25%,extraTP retention90% gates on both reused320 and reused160 separately;highest mean AP selects one candidate.',
  fresh_policy=read(ROOT/'protocol.json')['fresh_policy'],
  no_new_test_inference=True,hardware_access=False,sd_written=False)
 write(ROOT/'veto_protocol.json',protocol);datasets=cohorts();baseline={};control={}
 for key,d in datasets.items():
  baseline[key]=evaluate([d['base'][r['name']] for r in d['manifest']])['classes']['car']
  control[key]=evaluate([d['control'][r['name']] for r in d['manifest']])['classes']['car']
 records=[];outputs={};begin=time.monotonic()
 for epoch in CHECKPOINTS:
  probs={key:read(ROOT/'development'/f'epoch{epoch}_{key}_probabilities.json') for key in datasets}
  for threshold in protocol['thresholds']:
   for mode in protocol['modes']:
    scores={};gg={};predictions={}
    for key,d in datasets.items():
     rows=[]
     for r in d['manifest']:
      name=r['name'];p=fuse_veto(d['base'][name]['detections'],d['views'][name],probs[key][name],threshold,mode)
      rows.append(dict(name=name,ground_truth=d['base'][name]['ground_truth'],detections=p.tolist()))
     scores[key]=evaluate(rows)['classes']['car'];gg[key]=conditions(baseline[key],control[key],scores[key]);predictions[key]=rows
    passed=all(all(g.values()) for g in gg.values());tag=f'e{epoch}_t{threshold}_{mode}';ck=ROOT/'frozen'/f'epoch{epoch}/model.pt'
    record=dict(tag=tag,epoch=epoch,checkpoint=str(ck),sha256=sha(ck),threshold=threshold,mode=mode,weight=.65,scores=scores,gates=gg,qualified=passed)
    records.append(record);write(ROOT/'veto_progress.json',records)
    if passed:outputs[tag]=predictions
    print('VERIFIER_VETO_SCORE',tag,passed,{k:(round(v['ap50'],5),v['tp'],v['fp']) for k,v in scores.items()},'seconds',round(time.monotonic()-begin),flush=True)
 good=[r for r in records if r['qualified']];chosen=max(good,key=lambda r:np.mean([v['ap50'] for v in r['scores'].values()])) if good else None
 selected=dict(status='ONE_VETO_CANDIDATE_REQUIRES_C_AND_UNUSED_CONFIRMATION' if chosen else 'NO_VETO_CANDIDATE_KEEP_ABI27',qualified=chosen is not None,
  chosen=chosen,records=records,baselines=baseline,unverified_controls=control,protocol_sha256=sha(ROOT/'veto_protocol.json'),
  previous_continuous_failure_sha256=sha(ROOT/'selected.json'),new_test_inference=False,hardware_access=False,sd_written=False)
 write(ROOT/'veto_selected.json',selected)
 if chosen:
  for key,rows in outputs[chosen['tag']].items():write(ROOT/'development'/f'veto_chosen_{key}_predictions.json',rows)
 shutil.copy2(Path(__file__),ROOT/'source'/Path(__file__).name);print('VERIFIER_VETO_SELECTION',None if chosen is None else chosen['tag'],flush=True)

if __name__=='__main__':main()
