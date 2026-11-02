"""Separate localization errors from empty-background errors on reused data."""
from pathlib import Path
import numpy as np
from car_patch_verifier_common import *
from evaluate_car_patch_verifier import cohorts
from road_numpy_eval import correct

def main():
 result={}
 for key,d in cohorts().items():
  classes=dict(background=0,partial_overlap=0,localization=0,duplicate=0);true=0;items=[]
  for r in d['manifest']:
   name=r['name'];a=np.asarray(d['base'][name]['detections'],np.float32).reshape(-1,6);a=a[a[:,4]>=.25]
   b=np.asarray(d['control'][name]['detections'],np.float32).reshape(-1,6);b=b[b[:,4]>=.25]
   gt=np.asarray(d['control'][name]['ground_truth'],np.float32).reshape(-1,5)
   ok=correct(b,gt,np.array([.5],np.float32))[0][:,0]
   for box,hit in zip(b,ok):
    existing=len(a) and np.any(np.max(np.abs(a[:,:4]-box[:4]),axis=1)<1e-4)
    if existing:continue
    if hit:true+=1;continue
    overlap=iou_max(box,gt[:,1:]);kind='background' if overlap<.1 else 'partial_overlap' if overlap<.3 else 'localization' if overlap<.5 else 'duplicate'
    classes[kind]+=1;items.append(dict(name=name,box=box.tolist(),max_gt_iou=overlap,kind=kind))
  result[key]=dict(added_true_boxes=true,added_false_boxes=classes,examples=items)
 records=read(ROOT/'patches.json');counts={}
 for label in [0,1]:
  bb=[r['box'][4] for r in records if r['split']=='train' and r['target']==label]
  counts[str(label)]=dict(count=len(bb),score_above038=sum(v>=.384615 for v in bb),score_quantiles=np.quantile(bb,[0,.25,.5,.75,1]).tolist())
 write(ROOT/'error_diagnosis.json',dict(cohorts=result,training_confidence_bias=counts,source='Reused development only',hardware_access=False))
 print('ADDED_FP_DIAGNOSIS',{k:{j:v for j,v in vv.items() if j!='examples'} for k,vv in result.items()},counts,flush=True)

if __name__=='__main__':main()
