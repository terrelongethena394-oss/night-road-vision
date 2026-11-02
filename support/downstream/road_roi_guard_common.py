"""Label-free, deterministic high-detail center-proposal guards and fusion."""
from pathlib import Path
import numpy as np
from road_twilight_r2_common import BASE,TEACHER,TEACHER_SHA,read,write,sha
ROOT=BASE.parent/'road_roi_guard_20261028'
OLD=BASE.parent/'road_center_roi_20261027'

def fuse(full,roi,policy):
 from torchvision.ops import nms
 import torch
 a=np.asarray(full,np.float32).reshape(-1,6);z=np.asarray(roi,np.float32).reshape(-1,6).copy();keep=[]
 for p in z:
  cls=int(p[5]);w,h=p[2]-p[0],p[3]-p[1];border=min(p[0]-100,p[1]-60,300-p[2],180-p[3])
  if border<policy['border']:continue
  if cls==0 and not policy['person_aspect'][0]<=w/max(h,1e-9)<=policy['person_aspect'][1]:continue
  other=a[(a[:,5]==cls)&(a[:,4]>=.25)]
  if len(other):
   ov=np.maximum(0,np.minimum(p[2:4],other[:,2:4])-np.maximum(p[:2],other[:,:2])).prod(1);area=max(w*h,1e-9);oa=np.maximum(0,other[:,2:4]-other[:,:2]).prod(1)
   iou=ov/(area+oa-ov+1e-9);contain=ov/(np.minimum(area,oa)+1e-9)
   if np.any((iou>=policy['dedup_iou'])|(contain>=policy['dedup_containment'])):continue
  p[4]*=policy['weights'][cls];keep.append(p)
 b=np.concatenate([a,np.asarray(keep,np.float32).reshape(-1,6)])
 if not len(b):return []
 t=torch.from_numpy(b);ids=nms(t[:,:4]+t[:,5:6]*7680,t[:,4],.6)[:300]
 return t[ids].tolist()

def gates(a,b):
 ap=a['by_time']['dawn/dusk'];bp=b['by_time']['dawn/dusk'];p=ap['classes']['person'];q=bp['classes']['person']
 return dict(dusk_ap=bp['mAP50']>=ap['mAP50']+.02,overall=b['all']['mAP50']>=a['all']['mAP50']+.01,dusk_person_recall=q['recall']>=p['recall']+.03,night=b['by_time']['night']['mAP50']>=a['by_time']['night']['mAP50']-.005,day=b['by_time']['daytime']['mAP50']>=a['by_time']['daytime']['mAP50']-.005,dusk_fp=sum(v['fp'] for v in bp['classes'].values())<=sum(v['fp'] for v in ap['classes'].values())*1.1+2,dusk_person_fp=q['fp']<=p['fp']*1.1+2)
