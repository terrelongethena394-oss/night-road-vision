"""Old-validation-only proposal geometry audit; labels are never runtime filter inputs."""
from pathlib import Path
import numpy as np
from road_twilight_r2_common import BASE,read,write
OLD=BASE.parent/'road_center_roi_20261027'
OUT=BASE.parent/'road_roi_guard_20261028'

def main():
 OUT.mkdir(exist_ok=False)
 from road_adapt_eval_core import torch,truth,process_batch
 full=read(OLD/'full_predictions.json');roi={r['name']:r for r in read(OLD/'center_only_diagnostic_predictions.json')};records=[]
 for row in full:
  a=np.asarray(row['detections'],np.float32).reshape(-1,6);z=np.asarray(roi[row['name']]['detections'],np.float32).reshape(-1,6);z=z[z[:,4]>=.25]
  labels=torch.from_numpy(truth(dict(label_path=str(BASE/'dataset/labels/val'/(Path(row['name']).stem+'.txt'))),400,240))
  correct=process_batch(torch.from_numpy(z),labels,torch.tensor([.5])).numpy()[:,0]
  for i,p in enumerate(z):
   others=a[(a[:,5]==p[5])&(a[:,4]>=.25)];wh=p[2:4]-p[:2];area=float(wh.prod());ov=np.maximum(0,np.minimum(p[2:4],others[:,2:4])-np.maximum(p[:2],others[:,:2])).prod(1);oa=np.maximum(0,others[:,2:4]-others[:,:2]).prod(1)
   iou=ov/(area+oa-ov+1e-9);contain=ov/(np.minimum(area,oa)+1e-9)
   records.append(dict(name=row['name'],timeofday=row['timeofday'],cls=int(p[5]),correct=bool(correct[i]),score=float(p[4]),width=float(wh[0]),height=float(wh[1]),aspect=float(wh[0]/max(wh[1],1e-9)),border=float(min(p[0]-100,p[1]-60,300-p[2],180-p[3])),max_iou_full=float(iou.max(initial=0)),max_containment_full=float(contain.max(initial=0))))
 summary=[]
 for period in ['night','dawn/dusk','daytime']:
  for cls in range(4):
   for good in [False,True]:
    rs=[r for r in records if r['timeofday']==period and r['cls']==cls and r['correct']==good]
    if rs:summary.append(dict(timeofday=period,cls=cls,correct=good,n=len(rs),features={k:np.percentile([r[k] for r in rs],[0,25,50,75,100]).tolist() for k in ['score','width','height','aspect','border','max_iou_full','max_containment_full']}))
 write(OUT/'proposal_audit.json',dict(status='OLD_VALIDATION_ONLY_ERROR_AUDIT',summary=summary,proposals=records,hardware_access=False,new_test_inference=False))
 for r in summary:
  if r['timeofday']=='dawn/dusk' and r['cls']==0:print('ROI_PERSON_AUDIT',r,flush=True)
if __name__=='__main__':main()
