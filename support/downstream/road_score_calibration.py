"""Fixed odds-score remapping for truck/bus; no geometry or car/person edits."""
import numpy as np

def calibrate(pred,gain):
 p=np.asarray(pred,np.float32).reshape(-1,6).copy();gains=np.asarray(gain,np.float32).reshape(-1)
 if len(gains)==1:gains=np.repeat(gains,2)
 assert len(gains)==2 and np.isfinite(gains).all() and np.all((gains>=1)&(gains<=2))
 assert np.isfinite(p).all() and np.all((p[:,4]>=0)&(p[:,4]<=1))
 for cls,g in zip([2,3],gains):
  mask=p[:,5]==cls;s=p[mask,4]
  p[mask,4]=(g*s)/(np.float32(1)+(g-np.float32(1))*s)
 return p[np.argsort(-p[:,4],kind='stable')]

