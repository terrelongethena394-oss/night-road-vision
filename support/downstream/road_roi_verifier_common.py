from pathlib import Path
import numpy as np
from road_roi_guard_common import BASE,TEACHER,TEACHER_SHA,read,write,sha,ROOT as GUARD,OLD
ROOT=BASE.parent/'road_roi_verifier_20261028'
R2=BASE.parent/'road_twilight_consistency_20261027'
SEED=2026102854
EPOCHS=12
CHECKPOINTS=[4,8,12]
FLOORS=[.5,.7,.85]

def person_eligible(full,p,policy):
 if int(p[5])!=0 or p[4]<.05:return False
 w,h=p[2]-p[0],p[3]-p[1]
 if min(p[0]-100,p[1]-60,300-p[2],180-p[3])<policy['border'] or not policy['person_aspect'][0]<=w/max(h,1e-9)<=policy['person_aspect'][1]:return False
 a=np.asarray(full,np.float32).reshape(-1,6);a=a[(a[:,5]==0)&(a[:,4]>=.25)]
 if len(a):
  v=np.maximum(0,np.minimum(p[2:4],a[:,2:4])-np.maximum(p[:2],a[:,:2])).prod(1);area=max(w*h,1e-9);oa=np.maximum(0,a[:,2:4]-a[:,:2]).prod(1)
  if np.any((v/(area+oa-v+1e-9)>=policy['dedup_iou'])|(v/(np.minimum(area,oa)+1e-9)>=policy['dedup_containment'])):return False
 return True

def crop_patch(sensor,p):
 # p is in400x240 full-view coordinates; crop from the true800x480 source.
 # Nearest-center integer sampling is deliberately identical in future C code.
 x1,y1,x2,y2=map(float,p[:4]);cx=x1+x2;cy=y1+y2;w=(x2-x1)*2;h=(y2-y1)*2
 left=max(0,min(799,int(np.floor(cx-.625*w))));top=max(0,min(479,int(np.floor(cy-.625*h))))
 right=max(left+1,min(800,int(np.ceil(cx+.625*w))));bottom=max(top+1,min(480,int(np.ceil(cy+.625*h))))
 xs=left+((2*np.arange(24)+1)*(right-left)//48);ys=top+((2*np.arange(48)+1)*(bottom-top)//96)
 return sensor[ys[:,None],xs[None,:]].copy()

def make_model():
 import torch
 return torch.nn.Sequential(torch.nn.Conv2d(3,8,3,2,1),torch.nn.ReLU(),torch.nn.Conv2d(8,16,3,2,1),torch.nn.ReLU(),torch.nn.Conv2d(16,16,3,2,1),torch.nn.ReLU(),torch.nn.AdaptiveAvgPool2d(1),torch.nn.Flatten(),torch.nn.Linear(16,1))

def verified_fuse(full,roi,policy,probabilities,floor):
 # Only ROI confidence changes; the same guard/NMS and full-frame boxes remain.
 from road_roi_guard_common import fuse
 z=np.asarray(roi,np.float32).reshape(-1,6).copy()
 for index,value in probabilities.items():z[int(index),4]*=floor+(1-floor)*float(value)
 return fuse(full,z,policy)
