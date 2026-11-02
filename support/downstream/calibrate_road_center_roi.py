"""Old-validation-only score calibration for extra high-resolution ROI proposals."""
from pathlib import Path
import numpy as np
from road_twilight_r2_common import ROOT,BASE,read,write,sha
OUT=ROOT.parent/'road_center_roi_20261027'
def main():
 assert (OUT/'complete.json').exists();dest=OUT/'calibration';dest.mkdir(exist_ok=False)
 weights=[.25,.35,.45,.55,.70,.85]
 write(dest/'protocol.json',dict(status='ROI_CONFIDENCE_GRID_FROZEN_BEFORE_RECOMPUTATION',weights=weights,data='Old320 validation only',rule='Unchanged ROI crop/edge rule and NMS. Multiply only ROI proposal confidence by weight before merging. Select maximum duskAP among unchanged feasibility gates; if no eligible retain baseline. No new holdout inference.',gates=read(OUT/'protocol.json')['gate'],hardware_access=False))
 from road_adapt_eval_core import torch,evaluate_serial_predictions
 from torchvision.ops import nms
 base=read(OUT/'full_metrics.json');full=read(OUT/'full_predictions.json');roi={r['name']:r for r in read(OUT/'center_only_diagnostic_predictions.json')};rows=[dict(name=r['name'],timeofday=r['timeofday'],label_path=str(BASE/'dataset/labels/val'/(Path(r['name']).stem+'.txt'))) for r in full]
 records=[]
 for weight in weights:
  pred={}
  for r in full:
   a=torch.tensor(r['detections'],dtype=torch.float32,device='cuda').reshape(-1,6);z=torch.tensor(roi[r['name']]['detections'],dtype=torch.float32,device='cuda').reshape(-1,6);z[:,4]*=weight;both=torch.cat([a,z]);ids=nms(both[:,:4]+both[:,5:6]*7680,both[:,4],.6)[:300] if len(both) else torch.empty(0,dtype=torch.long,device='cuda');pred[r['name']]=both[ids].cpu().tolist()
  tag='roi_weight_'+str(weight).replace('.','p');m=evaluate_serial_predictions(rows,pred,dest,tag);a=base['by_time']['dawn/dusk'];b=m['by_time']['dawn/dusk'];p=a['classes']['person'];q=b['classes']['person']
  gates=dict(dusk_ap=b['mAP50']>=a['mAP50']+.02,dusk_person_recall=q['recall']>=p['recall']+.03,night=m['by_time']['night']['mAP50']>=base['by_time']['night']['mAP50']-.005,day=m['by_time']['daytime']['mAP50']>=base['by_time']['daytime']['mAP50']-.005,dusk_fp=sum(v['fp'] for v in b['classes'].values())<=sum(v['fp'] for v in a['classes'].values())*1.1+2,dusk_person_fp=q['fp']<=p['fp']*1.1+2)
  records.append(dict(weight=weight,metrics=m,gates=gates,eligible=all(gates.values()),prediction_path=str(dest/(tag+'_predictions.json'))));print('CENTER_ROI_CALIBRATION',weight,b['mAP50'],q['recall'],q['fp'],gates,flush=True)
 good=[r for r in records if r['eligible']];chosen=max(good,key=lambda r:(r['metrics']['by_time']['dawn/dusk']['mAP50'],r['metrics']['all']['mAP50'])) if good else None
 write(dest/'complete.json',dict(status='ROI_VALIDATION_CALIBRATION_COMPLETE',baseline=base,records=records,selected=chosen,old_validation_qualified=bool(good),no_new_test_inference=True,protocol_sha256=sha(dest/'protocol.json'),hardware_access=False))
 print('CENTER_ROI_CALIBRATION_COMPLETE',chosen['weight'] if chosen else None,flush=True)
if __name__=='__main__':main()
