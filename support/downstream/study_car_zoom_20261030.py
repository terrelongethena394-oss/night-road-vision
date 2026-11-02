"""Train-label-selected zoom geometry, fixed frozen CNN, reused development only."""
from pathlib import Path
import shutil,time
import numpy as np
import road_accuracy_common as ac
from road_numpy_eval import evaluate
from road_enhanceadapt_common import BASE,INITIAL,AUDIT,ADAPT,read,write,sha
ROOT=BASE/'road_car_zoom_20261030_r1'
WEIGHTS=[.35,.5,.65,.8]
XS=[0,260,520]

def zoom(sensor,x,y):
 a=sensor[y:y+168,x:x+280].astype(np.uint32);assert a.shape==(168,280,3)
 xn=np.clip(14*np.arange(400)-3,0,279*20);yn=np.clip(14*np.arange(240)-3,0,167*20)
 xx,fx=xn//20,xn%20;yy,fy=yn//20,yn%20;x1=np.minimum(xx+1,279);y1=np.minimum(yy+1,167)
 v=a[yy[:,None],xx[None,:]]*((20-fy)[:,None]*(20-fx)[None,:])[:,:,None]
 v+=a[yy[:,None],x1[None,:]]*((20-fy)[:,None]*fx[None,:])[:,:,None]
 v+=a[y1[:,None],xx[None,:]]*(fy[:,None]*(20-fx)[None,:])[:,:,None]
 v+=a[y1[:,None],x1[None,:]]*(fy[:,None]*fx[None,:])[:,:,None]
 return ((v+200)//400).astype(np.uint8)

def map_zoom(pred,x,y):
 p=np.asarray(pred,np.float32).reshape(-1,6).copy()
 p=p[(p[:,5]==1)&(p[:,0]>1)&(p[:,1]>1)&(p[:,2]<399)&(p[:,3]<239)]
 p[:,:4]*=np.float32(.35);p[:,[0,2]]+=np.float32(x*.5);p[:,[1,3]]+=np.float32(y*.5)
 return p

def fuse_zoom(raw,views,weight):
 a=np.asarray(raw,np.float32).reshape(-1,6);strong=a[a[:,4]>=.25];extra=[]
 for pp in views:
  for p in np.asarray(pp,np.float32).reshape(-1,6):
   if p[4]<.05:continue
   if len(strong):
    area=np.maximum(0,p[2:4]-p[:2]).prod();oa=np.maximum(0,strong[:,2:4]-strong[:,:2]).prod(1)
    inter=np.maximum(0,np.minimum(p[2:4],strong[:,2:4])-np.maximum(p[:2],strong[:,:2])).prod(1)
    if np.any((inter/(area+oa-inter+1e-9)>=.3)|(inter/(np.minimum(area,oa)+1e-9)>=.8)):continue
   q=p.copy();q[4]*=np.float32(weight);extra.append(q)
 b=np.concatenate([a,np.asarray(extra,np.float32).reshape(-1,6)])
 return ac.nms_numpy(b,.6,300)

def gates(a,b):
 return dict(ap=b['ap50']>=a['ap50']+.01,precision=b['precision']>=a['precision']-.005,
             recall=b['recall']>=a['recall']+.01)

def main():
 assert not ROOT.exists();ROOT.mkdir();(ROOT/'source').mkdir()
 assert not read(BASE/'road_car_consensus_20261030_r1/selected.json')['qualified']
 train=read(ADAPT/'training_manifest.json');centers=[]
 for r in train:
  gt=ac.truth(BASE/'road_detection_20261026/dataset/labels/train'/(Path(r['name']).stem+'.txt'))
  for g in gt:
   if g[0]==1 and 1<=g[3]-g[1]<=16 and 1<=g[4]-g[2]<=12:centers.append((g[1:]+g[[3,4,1,2]])[:2])
 # Bounding boxes, not validation images/predictions, select one vertical band.
 boxes=[]
 for r in train:
  gt=ac.truth(BASE/'road_detection_20261026/dataset/labels/train'/(Path(r['name']).stem+'.txt'))
  boxes.extend(g[1:]*2 for g in gt if g[0]==1 and 1<=g[3]-g[1]<=16 and 1<=g[4]-g[2]<=12)
 b=np.asarray(boxes,np.float32);assert len(b)>100
 coverage={}
 for y in range(40,313,8):
  covered=np.zeros(len(b),bool)
  for x in XS:covered|=(b[:,0]>=x+2)&(b[:,2]<=x+278)&(b[:,1]>=y+2)&(b[:,3]<=y+166)
  coverage[y]=int(covered.sum())
 y=max(coverage,key=coverage.get)
 protocol=dict(status='GEOMETRY_AND_SEARCH_FROZEN_BEFORE_NEW_ZOOM_PREDICTIONS',
  purpose='Increase small-car pixel detail while preserving current raw detector and enhancement display.',
  geometry=dict(width=280,height=168,x=XS,y=y,selection='Max full-box coverage of original2400 training small cars, width1..16 and height1..12 in400proxy. Fixed x, y grid40..312 step8. No development labels/predictions used for geometry.',
                small_train_boxes=len(b),coverage_by_y=coverage),
  pixel_path='Integer bilinear280x168->400x240 with denominator20 per axis, nearest integer ties up; then unchanged exact preprocess400 to320x320.',
  model_sha256=sha(INITIAL),network='Unchanged frozen accepted car CNN. Old4raw views plus3zoom views;7forwards,357PLcalls per shot. Mean>48 keeps old4views.',
  fusion='Preserve raw4view strong car boxes. New zoom car>=.05, reject crop-edge boxes, discard matches IoU>=.3 or containment>=.8 to raw confidence>=.25; weight then NMS.6 max300.',
  weights=WEIGHTS,development='Previously used audit320 low,96 brighter are controls. Not a new blind test.',
  gates='CarAP gain>=1pp,precision drop<=.5pp,recall gain>=1pp. Absolute FP may rise with more TP; report both, do not hide this tradeoff. HigherAP selects one qualifying weight.',
  fresh_policy='Unused160 low+64 brighter excluding all recorded groups/hashes. Same gates and99%paired-image bootstrap carAP gain lower>0 vs current raw4view. No fresh-driven replacement.',
  hardware_access=False,sd_written=False)
 write(ROOT/'protocol.json',protocol);shutil.copy2(Path(__file__),ROOT/'source'/Path(__file__).name)
 print('CAR_ZOOM_GEOMETRY_TRAIN_ONLY',y,coverage[y],len(b),flush=True)
 manifest=read(BASE/'road_brightness_route_20261030_r1/fresh/manifest.json');low=[r for r in manifest if r['cohort']=='low']
 base={r['name']:r['raw_multiview'] for r in read(AUDIT/'predictions.json')}
 assert len(low)==320;ac.WEIGHTS=INITIAL;det=ac.Detector();preds=[];begin=time.monotonic()
 for at in range(0,len(low),8):
  rr=low[at:at+8];ims=[]
  for r in rr:
   sensor,_=ac.sensor400(BASE/'road_brightness_route_20261030_r1/fresh/images'/r['name']);ims.extend(zoom(sensor,x,y) for x in XS)
  pp=det.run(ims)
  for i,r in enumerate(rr):preds.append(dict(name=r['name'],local=[pp[3*i+j] for j in range(3)],mapped=[map_zoom(pp[3*i+j],x,y).tolist() for j,x in enumerate(XS)]))
  if (at+len(rr))%80==0:print('CAR_ZOOM_DEVELOPMENT',at+len(rr),len(low),round(time.monotonic()-begin),flush=True)
 write(ROOT/'zoom_predictions.json',preds);baseline=read(AUDIT/'result.json')['scores']['low']['raw_multiview'];records=[];outputs={}
 for w in WEIGHTS:
  rows=[dict(name=r['name'],ground_truth=base[r['name']]['ground_truth'],detections=fuse_zoom(base[r['name']]['detections'],r['mapped'],w).tolist()) for r in preds]
  m=evaluate(rows)['classes']['car'];g=gates(baseline,m);records.append(dict(weight=w,metrics=m,gates=g,qualified=all(g.values())));outputs[w]=rows
  print('CAR_ZOOM_SCORE',w,m,g,flush=True)
 good=[r for r in records if r['qualified']];chosen=max(good,key=lambda r:r['metrics']['ap50']) if good else None
 write(ROOT/'selected.json',dict(status='ONE_ZOOM_CANDIDATE_REQUIRES_UNUSED_CONFIRMATION' if chosen else 'NO_ZOOM_CANDIDATE_KEEP_ABI27',qualified=chosen is not None,chosen=chosen,baseline=baseline,records=records,
  protocol_sha256=sha(ROOT/'protocol.json'),model_sha256=sha(INITIAL),new_test_inference=False,hardware_access=False,sd_written=False))
 if chosen:write(ROOT/'chosen_predictions.json',outputs[chosen['weight']])
 print('CAR_ZOOM_SELECTION',None if chosen is None else chosen['weight'],flush=True)

if __name__=='__main__':main()
