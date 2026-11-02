"""Independent class-specific fusion reference and fixed development gates."""
from road_accuracy_common import BASE,DATA,APP,NAMES,read,write,sha,nms_numpy,map_tile,metrics,correct
from pathlib import Path
import numpy as np
ROOT=BASE/'road_classwise_20261030_r1'
OLD=BASE/'road_accuracy_20261030_r1'
LOW=BASE/'road_accuracy_lowlight_20261030_r1'
GRID=[0.,.25,.45,.6,.75]
SEED=2026103012
def fuse(full,tiles,weights):
 a=np.asarray(full,np.float32).reshape(-1,6);extra=[];weights=np.asarray(weights,np.float32)
 for tile in tiles:
  for p in np.asarray(tile,np.float32).reshape(-1,6):
   cls=int(p[5])
   if cls==0 or weights[cls]<=0 or p[4]<.05:continue
   others=a[(a[:,5]==cls)&(a[:,4]>=.25)]
   if len(others):
    area=np.maximum(0,p[2:4]-p[:2]).prod();oa=np.maximum(0,others[:,2:4]-others[:,:2]).prod(1)
    overlap=np.maximum(0,np.minimum(p[2:4],others[:,2:4])-np.maximum(p[:2],others[:,:2])).prod(1)
    if np.any((overlap/(area+oa-overlap+1e-9)>=.3)|(overlap/(np.minimum(area,oa)+1e-9)>=.8)):continue
   q=p.copy();q[4]*=weights[cls];extra.append(q)
 person=a[a[:,5]==0];vehicles=np.concatenate([a[a[:,5]!=0],np.asarray(extra,np.float32).reshape(-1,6)])
 vehicles=nms_numpy(vehicles,maxdet=300-len(person)) if len(person)<300 else np.empty((0,6),np.float32)
 combined=np.concatenate([person,vehicles]);return combined[np.argsort(-combined[:,4],kind='stable')]
def combined(m):
 d=m['all']['classes'];tp=sum(d[k]['tp'] for k in ['truck','bus']);fp=sum(d[k]['fp'] for k in ['truck','bus']);objects=sum(d[k]['objects'] for k in ['truck','bus'])
 p=tp/(tp+fp) if tp+fp else 0.;r=tp/objects if objects else 0.
 return dict(tp=tp,fp=fp,objects=objects,precision=p,recall=r,f05=1.25*p*r/(.25*p+r) if p+r else 0.)
def gates(raw,current,candidate):
 r=combined(raw);a=combined(current);b=combined(candidate)
 return dict(car_ap=all(candidate['by_time'][p]['classes']['car']['ap50']>=current['by_time'][p]['classes']['car']['ap50']-.001 for p in current['by_time']),car_precision=candidate['all']['classes']['car']['precision']>=current['all']['classes']['car']['precision']-.001,car_recall=candidate['all']['classes']['car']['recall']>=current['all']['classes']['car']['recall']-.001,all_map=candidate['all']['mAP50']>=current['all']['mAP50']-.005,rareclass_ap_vs_single=all(candidate['all']['classes'][k]['ap50']>=raw['all']['classes'][k]['ap50']-.005 for k in ['truck','bus'] if raw['all']['classes'][k]['objects']),rareclass_tp_vs_single=all(candidate['all']['classes'][k]['tp']>=raw['all']['classes'][k]['tp'] for k in ['truck','bus']),truck_bus_tp_retained=b['tp']>=a['tp']*.8,truck_bus_fp_reduced25=b['fp']<=a['fp']*.75)
