"""Validation-only classwise calibration; a new untouched holdout is still required."""
from pathlib import Path
import numpy as np
from road_twilight_r2_common import ROOT,BASE,read,write,sha
OUT=ROOT.parent/'road_center_roi_20261027'
def main():
 dest=OUT/'classwise';dest.mkdir(exist_ok=False);weights=[.25,.35,.45,.475,.50,.525,.55,.70,.85]
 write(dest/'protocol.json',dict(status='CLASSWISE_VALIDATION_CALIBRATION_GRID_FROZEN',weights=weights,reason='Global weight cannot satisfy old-validation FP and person recall together. Calibrate each of four class scores independently; class-aware NMS does not merge different classes.',allocation='For each class duskFP<=1.10*baselineFP+0.5, perclassAP>=baselineAP-.005. Person maximize recall thenAP; other classes maximizeAP thenrecall. If no eligible class weight, retain weight0 (raw only for that class).',final_guards='Unchanged old feasibility gates, total+person FP <=1.10*baseline+2, duskAP gain>=.02, personRecall gain>=.03, night/dayAP>=baseline-.005.',new_holdout='Required before any improvement claim or board change; previous R2 test is development-only now.',hardware_access=False))
 from road_adapt_eval_core import torch,evaluate_serial_predictions
 from torchvision.ops import nms
 full=read(OUT/'full_predictions.json');roi={r['name']:r for r in read(OUT/'center_only_diagnostic_predictions.json')};rows=[dict(name=r['name'],timeofday=r['timeofday'],label_path=str(BASE/'dataset/labels/val'/(Path(r['name']).stem+'.txt'))) for r in full]
 def merge(ws):
  predictions={}
  for r in full:
   a=torch.tensor(r['detections'],dtype=torch.float32,device='cuda').reshape(-1,6);z=torch.tensor(roi[r['name']]['detections'],dtype=torch.float32,device='cuda').reshape(-1,6);factor=z.new_tensor(ws)[z[:,5].long()];z=z[factor>0];factor=factor[factor>0];z[:,4]*=factor;both=torch.cat([a,z]);ids=nms(both[:,:4]+both[:,5:6]*7680,both[:,4],.6)[:300] if len(both) else torch.empty(0,dtype=torch.long,device='cuda');predictions[r['name']]=both[ids].cpu().tolist()
  return predictions
 base=read(OUT/'full_metrics.json');candidates=[]
 old={r['weight']:r for r in read(OUT/'calibration/complete.json')['records']}
 for w in weights:
  if w in old:m=old[w]['metrics']
  else:m=evaluate_serial_predictions(rows,merge([w]*4),dest,'global_'+str(w).replace('.','p'))
  candidates.append(dict(weight=w,metrics=m))
 names=['person','car','truck','bus'];choice=[]
 for cls in names:
  b=base['by_time']['dawn/dusk']['classes'][cls];ok=[r for r in candidates if r['metrics']['by_time']['dawn/dusk']['classes'][cls]['fp']<=b['fp']*1.1+.5 and r['metrics']['by_time']['dawn/dusk']['classes'][cls]['ap50']>=b['ap50']-.005]
  def key(r):
   m=r['metrics']['by_time']['dawn/dusk']['classes'][cls];return (m['recall'],m['ap50']) if cls=='person' else (m['ap50'],m['recall'])
  choice.append(max(ok,key=key)['weight'] if ok else 0.)
 write(dest/'chosen_before_merged_evaluation.json',dict(weights=choice,classes=names,protocol_sha256=sha(dest/'protocol.json'),new_holdout_not_read=True))
 m=evaluate_serial_predictions(rows,merge(choice),dest,'classwise');a=base['by_time']['dawn/dusk'];b=m['by_time']['dawn/dusk'];p=a['classes']['person'];q=b['classes']['person'];gates=dict(dusk_ap=b['mAP50']>=a['mAP50']+.02,dusk_person_recall=q['recall']>=p['recall']+.03,night=m['by_time']['night']['mAP50']>=base['by_time']['night']['mAP50']-.005,day=m['by_time']['daytime']['mAP50']>=base['by_time']['daytime']['mAP50']-.005,dusk_fp=sum(v['fp'] for v in b['classes'].values())<=sum(v['fp'] for v in a['classes'].values())*1.1+2,dusk_person_fp=q['fp']<=p['fp']*1.1+2)
 write(dest/'complete.json',dict(status='CLASSWISE_ROI_OLD_VALIDATION_COMPLETE',weights=choice,classes=names,baseline=base,candidate=m,gates=gates,old_validation_qualified=all(gates.values()),new_holdout_not_read=True,hardware_access=False,sd_written=False));print('CENTER_ROI_CLASSWISE_COMPLETE',choice,gates,'dusk',a['mAP50'],b['mAP50'],'recall',p['recall'],q['recall'],flush=True)
if __name__=='__main__':main()
