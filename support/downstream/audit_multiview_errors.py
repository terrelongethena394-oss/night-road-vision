"""Diagnose extra vehicle detections on reused development data only."""
from collections import Counter, defaultdict
from road_classwise_common import *

ROOT=BASE/'road_overlap_20261030_r1'
COHORTS={
 'original320':BASE/'road_classwise_20261030_r2/known320_native',
 'low320':LOW/'native',
 'reused301':BASE/'road_classwise_20261030_r2/native',
}

def overlap(p,b):
 b=np.asarray(b,np.float32).reshape(-1,4)
 v=np.maximum(0,np.minimum(p[2:4],b[:,2:])-np.maximum(p[:2],b[:,:2])).prod(1)
 ar=np.maximum(0,p[2:4]-p[:2]).prod();ba=np.maximum(0,b[:,2:]-b[:,:2]).prod(1)
 return v/(ar+ba-v+np.float32(1e-9))

def main():
 ROOT.mkdir(exist_ok=True)
 report={};examples=[]
 for label,folder in COHORTS.items():
  full=read(folder/'global_raw.json');tiles=[read(folder/f'tile_raw_{i}.json') for i in range(3)]
  records=[]
  for at,r in enumerate(full):
   a=np.asarray(r['detections'],np.float32).reshape(-1,6)
   mapped=[np.asarray(t[at]['detections'],np.float32).reshape(-1,6) for t in tiles]
   p=fuse(a,mapped,[0,.75,.75,.75]);p=p[p[:,4]>=.25]
   gt=np.asarray(r['ground_truth'],np.float32).reshape(-1,5);ok=correct(p,gt,np.array([.5],np.float32))[0][:,0]
   for box,is_tp in zip(p,ok):
    if box[5] not in [2,3]:continue
    original=bool(np.any(np.all(a==box,axis=1)))
    other=a[(a[:,5]!=box[5])&(a[:,5]!=0)&(a[:,4]>=.25)]
    ov=overlap(box,other[:,:4]);maxdiff=float(ov.max()) if len(ov) else 0.
    samegt=gt[gt[:,0]==box[5]];othergt=gt[gt[:,0]!=box[5]]
    sg=overlap(box,samegt[:,1:]);og=overlap(box,othergt[:,1:])
    support=0
    for tile in mapped:
     other=tile[(tile[:,5]==box[5])&(tile[:,4]>=1/3)]
     if len(other) and np.max(overlap(box,other[:,:4]))>=.5:support+=1
    rec=dict(name=r['name'],cohort=label,cls=NAMES[int(box[5])],tp=bool(is_tp),original=original,box=box.tolist(),max_other_full_iou=maxdiff,tile_support=support,same_gt_iou=float(sg.max()) if len(sg) else 0.,other_gt_iou=float(og.max()) if len(og) else 0.)
    records.append(rec)
  count={}
  for origin in ['original','supplement']:
   rr=[r for r in records if r['original']==(origin=='original')]
   count[origin]=dict(tp=sum(r['tp'] for r in rr),fp=sum(not r['tp'] for r in rr))
   if origin=='supplement':
    for threshold in [.3,.5,.7]:
     z=[r for r in rr if r['max_other_full_iou']>=threshold]
     count[f'crossclass_iou>={threshold}']=dict(tp=sum(r['tp'] for r in z),fp=sum(not r['tp'] for r in z))
    for k in [1,2]:
     z=[r for r in rr if r['tile_support']<=k]
     count[f'tile_support<={k}']=dict(tp=sum(r['tp'] for r in z),fp=sum(not r['tp'] for r in z))
    count['fp_overlaps_wrong_class_gt']=sum(not r['tp'] and r['other_gt_iou']>=.5 for r in rr)
    count['fp_low_sameclass_gt_overlap']=sum(not r['tp'] and r['same_gt_iou']<.1 for r in rr)
  report[label]=dict(images=len(full),counts=count)
  examples.extend(records)
 write(ROOT/'error_audit.json',report);write(ROOT/'box_audit.json',examples)
 print(report,flush=True)

if __name__=='__main__':main()
