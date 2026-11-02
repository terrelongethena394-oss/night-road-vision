"""Single frozen policy, new group test; no reselection after outcomes."""
from pathlib import Path
import time
import cv2,numpy as np
from road_roi_guard_common import *
from road_arm_common import preprocess400

def main():
 selected=read(ROOT/'selected.json');assert selected['qualified'];policy=selected['chosen']['policy'];protocol=read(ROOT/'fresh_protocol.json');assert protocol['chosen_sha256']==sha(ROOT/'selected.json') and protocol['policy']==policy;assert (ROOT/'fresh/complete.json').exists()
 out=ROOT/'fresh_evaluation';out.mkdir(exist_ok=False);write(out/'frozen.json',dict(status='POLICY_FROZEN_BEFORE_NEW_TEST_FORWARD',chosen_sha256=sha(ROOT/'selected.json'),test_protocol_sha256=sha(ROOT/'fresh_protocol.json'),manifest_sha256=sha(ROOT/'fresh/manifest.json'),checkpoint_sha256=TEACHER_SHA))
 from road_adapt_eval_core import torch,evaluate_serial_predictions,non_max_suppression,scale_boxes
 from utils.metrics import compute_ap,ap_per_class
 torch.set_num_threads(3);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;assert sha(TEACHER)==TEACHER_SHA
 model=torch.load(TEACHER,map_location='cpu',weights_only=False)['model'].float().fuse().cuda().eval();rows=[{**r,'label_path':str(ROOT/'fresh/labels'/(Path(r['name']).stem+'.txt'))} for r in read(ROOT/'fresh/manifest.json')];assert len(rows)==480
 original={};merged={};roi_only={};t=time.monotonic()
 with torch.inference_mode():
  for at in range(0,len(rows),8):
   rs=rows[at:at+8];inputs=[]
   for r in rs:
    image=cv2.imread(str(ROOT/'fresh/images'/r['name']))[:,:,::-1].copy();sensor=cv2.resize(image,(800,480),interpolation=cv2.INTER_LINEAR);sensor[:,:,0]&=248;sensor[:,:,1]&=252;sensor[:,:,2]&=248;b=sensor.astype(np.uint16);full=((b[0::2,0::2]+b[0::2,1::2]+b[1::2,0::2]+b[1::2,1::2]+2)//4).astype(np.uint8)
    inputs.extend([preprocess400(full).transpose(2,0,1),preprocess400(sensor[120:360,200:600].copy()).transpose(2,0,1)])
   x=torch.from_numpy(np.ascontiguousarray(np.stack(inputs))).cuda().float()/255;ps=non_max_suppression(model(x),.001,.6,max_det=300)
   for j,r in enumerate(rs):
    a=ps[2*j];z=ps[2*j+1]
    for p in [a,z]:
     if len(p):scale_boxes((320,320),p[:,:4],(240,400),ratio_pad=((.8,.8),(0.,64.)))
    z=z[(z[:,0]>1)&(z[:,1]>1)&(z[:,2]<399)&(z[:,3]<239)].clone();z[:,[0,2]]=z[:,[0,2]]*.5+100;z[:,[1,3]]=z[:,[1,3]]*.5+60
    original[r['name']]=a.cpu().float().tolist();roi_only[r['name']]=z.cpu().float().tolist();merged[r['name']]=fuse(original[r['name']],roi_only[r['name']],policy)
   if (at+len(rs))%80==0:print('ROI_GUARD_NEW_TEST',at+len(rs),round(time.monotonic()-t,1),flush=True)
 baseline=evaluate_serial_predictions(rows,original,out,'original');candidate=evaluate_serial_predictions(rows,merged,out,'guarded_roi');write(out/'unmerged_roi_predictions.json',roi_only);gs=gates(baseline,candidate)
 for period in ['dawn/dusk','night','daytime']:
  a=baseline['by_time'][period]['classes'];b=candidate['by_time'][period]['classes'];gs[period+'_fp_retention']=sum(v['fp'] for v in b.values())<=sum(v['fp'] for v in a.values())*1.1+2;gs[period+'_person_fp_retention']=b['person']['fp']<=a['person']['fp']*1.1+2
 def records(p):
  result=[]
  for r in read(p):
   if r['timeofday']=='dawn/dusk':
    pred=np.asarray(r['detections'],np.float64).reshape(-1,6);tp=np.asarray(r['correct'],bool).reshape(-1,10)[:,0];truth=np.asarray(r['ground_truth'],np.float64).reshape(-1,5);result.append((r['name'],tp,pred[:,4],pred[:,5],truth[:,0]))
  return sorted(result,key=lambda r:r[0])
 recs=[records(out/'original_predictions.json'),records(out/'guarded_roi_predictions.json')];assert len(recs[0])==len(recs[1])==160 and [r[0] for r in recs[0]]==[r[0] for r in recs[1]]
 def ap(arr):
  tp,conf,pc,tc=arr;order=np.argsort(-conf);tp=tp[order];pc=pc[order];classes,counts=np.unique(tc,return_counts=True);values=[]
  for c,n in zip(classes,counts):
   good=pc==c
   if not good.any():values.append(0.);continue
   t=tp[good].cumsum();f=(1-tp[good]).cumsum();values.append(compute_ap(t/(n+1e-16),t/(t+f))[0])
  return float(np.mean(values))
 rng=np.random.default_rng(2026102852);deltas=[]
 for k in range(1000):
  idx=rng.integers(0,160,160);arrs=[tuple(np.concatenate([r[i][j] for i in idx]) for j in [1,2,3,4]) for r in recs];values=[ap(a) for a in arrs]
  if k<20:
   for a,v in zip(arrs,values):
    tp,conf,pc,tc=a;official=float(ap_per_class(tp[:,None],conf,pc,tc,names={0:'person',1:'car',2:'truck',3:'bus'})[5][:,0].mean());assert abs(v-official)<1e-12
  deltas.append(values[1]-values[0])
  if (k+1)%250==0:print('ROI_GUARD_PAIRED_BOOTSTRAP',k+1,flush=True)
 ci=np.percentile(deltas,[2.5,97.5]).tolist();accepted=all(gs.values()) and ci[0]>0
 write(ROOT/'fresh_complete.json',dict(status='ROI_GUARD_NEW480_TEST_COMPLETE',baseline=baseline,candidate=candidate,gates=gs,paired_bootstrap=dict(replicates=1000,seed=2026102852,interval95=ci,first20_checked_against_upstream=True),quality_accepted=accepted,policy=policy,source='BDD originaltrain reserved previously unseen prefixgroups; same camera-domain source, not official validation benchmark.',selection_sha256=sha(ROOT/'selected.json'),no_reselection=True,board_deployment_accepted=False,hardware_access=False,sd_written=False));np.save(out/'paired_bootstrap_deltas.npy',np.asarray(deltas));print('ROI_GUARD_NEW_TEST_COMPLETE',accepted,ci,gs,flush=True)
if __name__=='__main__':main()
