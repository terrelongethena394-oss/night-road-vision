"""Development-only conflict calibration; never reinterpret used data as holdout."""
import itertools,shutil
from road_classwise_common import *
from audit_multiview_errors import overlap,COHORTS,ROOT

def features(row,full):
 p=np.asarray(row['detections'],np.float32).reshape(-1,6)
 a=np.asarray(full['detections'],np.float32).reshape(-1,6)
 f=np.zeros((len(p),3),np.float32)
 for i,b in enumerate(p):
  if b[5] not in [2,3] or np.any(np.all(a==b,axis=1)):continue
  other=a[(a[:,5]!=b[5])&(a[:,5]!=0)&(a[:,4]>=.25)]
  ov=overlap(b,other[:,:4])
  for j,t in enumerate([.3,.5,.7]):
   scores=other[ov>=t,4]
   if len(scores):f[i,j]=np.max(scores)/(b[4]/np.float32(.75))
 return f

def adjust(rows,ff,idx,ratio,penalty):
 out=[]
 for row,feat in zip(rows,ff):
  p=np.asarray(row['detections'],np.float32).reshape(-1,6).copy()
  p[feat[:,idx]>=ratio,4]*=np.float32(penalty)
  p=p[p[:,4]>=.001];p=p[np.argsort(-p[:,4],kind='stable')]
  out.append(dict(name=row['name'],timeofday=row['timeofday'],ground_truth=row['ground_truth'],detections=p.tolist()))
 return out

def main():
 assert (ROOT/'error_audit.json').exists() and not (ROOT/'protocol.json').exists()
 grid=list(itertools.product(range(3),[.75,1.,1.25,1.5],[0.,.5,.75,.9]))
 write(ROOT/'protocol.json',dict(status='DEVELOPMENT_ONLY_FROZEN_BEFORE_GRID',reused_cohorts=['original320','low320','previous301 split low205/brighter96'],note='Previous independent test is now development data, NOT independent confirmation for this candidate. Weights unchanged. Keep all car/person scores and boxes; only lower scores of supplemental truck/bus boxes overlapping a competing full-frame vehicle whose score is at least ratio times the original tile score.',iou=[.3,.5,.7],score_ratio=[.75,1.,1.25,1.5],penalty=[0.,.5,.75,.9],gates='Same gates as previous classwise experiment, separately on each of four reused cohorts. Candidate requires future unused holdout. Choose max pooled truck/bus F0.5, tie mean mAP50.',hardware_access=False,sd_written=False))
 source=ROOT/'source';source.mkdir(exist_ok=True)
 for name in ['study_road_overlap.py','audit_multiview_errors.py']:
  shutil.copy2(Path(__file__).with_name(name),source/name)
 data={}
 for label,folder in COHORTS.items():
  raw=read(folder/'global_raw.json');tiles=[read(folder/f'tile_raw_{i}.json') for i in range(3)]
  rows=[dict(name=r['name'],timeofday=r['timeofday'],ground_truth=r['ground_truth'],detections=fuse(r['detections'],[t[i]['detections'] for t in tiles],[0,.75,.75,.75]).tolist()) for i,r in enumerate(raw)]
  ff=[features(r,a) for r,a in zip(rows,raw)]
  subsets={'low205':[i for i,r in enumerate(raw) if r['timeofday']=='night'],'brighter96':[i for i,r in enumerate(raw) if r['timeofday']=='daytime']} if label=='reused301' else {label:list(range(len(rows)))}
  for key,ids in subsets.items():
   data[key]=dict(rows=[rows[i] for i in ids],features=[ff[i] for i in ids],raw=metrics([raw[i] for i in ids]),current=metrics([rows[i] for i in ids]))
 records=[]
 for n,(idx,ratio,penalty) in enumerate(grid,1):
  scores={k:metrics(adjust(d['rows'],d['features'],idx,ratio,penalty)) for k,d in data.items()}
  gg={k:gates(d['raw'],d['current'],scores[k]) for k,d in data.items()}
  totals=[combined(m) for m in scores.values()];tp=sum(z['tp'] for z in totals);fp=sum(z['fp'] for z in totals);objects=sum(z['objects'] for z in totals);p=tp/(tp+fp);r=tp/objects
  record=dict(iou=[.3,.5,.7][idx],ratio=ratio,penalty=penalty,scores=scores,gates=gg,passes=all(all(z.values()) for z in gg.values()),pooled_f05=1.25*p*r/(.25*p+r));records.append(record)
  if n%8==0:print('OVERLAP_DEVELOPMENT',n,len(grid),'qualified',sum(z['passes'] for z in records),flush=True)
 good=[r for r in records if r['passes']];chosen=max(good,key=lambda z:(z['pooled_f05'],np.mean([m['all']['mAP50'] for m in z['scores'].values()]))) if good else None
 write(ROOT/'development_result.json',dict(status='DEVELOPMENT_CANDIDATE_REQUIRES_NEW_HOLDOUT' if chosen else 'NO_CONFLICT_RULE_PASSED_RETAIN_ABI24',qualified=bool(chosen),chosen=chosen,records=records,current={k:d['current'] for k,d in data.items()},raw={k:d['raw'] for k,d in data.items()},hardware_access=False,sd_written=False))
 print('OVERLAP_RESULT',None if chosen is None else {k:chosen[k] for k in ['iou','ratio','penalty','pooled_f05']},flush=True)

if __name__=='__main__':main()
