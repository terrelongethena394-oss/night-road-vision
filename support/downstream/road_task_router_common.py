from pathlib import Path
import numpy as np
from road_enhanced_detection_common import BASE,read,write,sha,gates
ROOT=BASE/'road_task_router_20261031_r1'
SEED=2026103171
MAIN=BASE/'road_allview_gammafit_20261031_r1/frozen/enh8/model.pt'
EPOCHS=[20,40,80]
THRESHOLDS=[0.,.1,.2,.3,.4,.5]
def features(a):
    z=a.astype(np.int64);y=(54*z[:,:,0]+183*z[:,:,1]+19*z[:,:,2]+128)//256
    b=y.reshape(4,60,8,50).transpose(0,2,1,3).reshape(32,3000);mean=b.mean(1);var=(b*b).mean(1)-mean*mean
    v=np.r_[mean/255,var/65025,(z[:,:,0]-z[:,:,1]).mean()/255,(z[:,:,2]-z[:,:,1]).mean()/255,
      (np.abs(y[:,1:]-y[:,:-1]).sum()+np.abs(y[1:,:]-y[:-1,:]).sum())/(255*(240*399+239*400)),(y<=8).mean()]
    assert v.shape==(68,) and np.isfinite(v).all();return v.astype(np.float32)
def counts(r):
    from road_numpy_eval import correct
    p=np.asarray(r['detections'],np.float32).reshape(-1,6);p=p[(p[:,4]>=.25)&(p[:,5]==1)];g=np.asarray(r['ground_truth'],np.float32).reshape(-1,5);g=g[g[:,0]==1];tp=int(correct(p,g,np.array([.5],np.float32))[0][:,0].sum());return np.array([tp,len(p)-tp,len(g)-tp],np.int32)
def make_model():
    import torch.nn as nn
    return nn.Sequential(nn.Linear(68,16),nn.ReLU(),nn.Dropout(.2),nn.Linear(16,3))
