"""Refine only originally-added zoom boxes; never alter accepted4view boxes."""
import shutil,time
import numpy as np
import road_accuracy_common as ac
from road_numpy_eval import evaluate
from car_box_refine_common import *
from evaluate_car_patch_verifier import cohorts,conditions

def overlaps_strong(p,strong):
 if not len(strong):return False
 area=np.maximum(0,p[2:4]-p[:2]).prod();oa=np.maximum(0,strong[:,2:4]-strong[:,:2]).prod(1)
 inter=np.maximum(0,np.minimum(p[2:4],strong[:,2:4])-np.maximum(p[:2],strong[:,:2])).prod(1)
 return bool(np.any((inter/(area+oa-inter+1e-9)>=.3)|(inter/(np.minimum(area,oa)+1e-9)>=.8)))

def eligible(p,strong):return p[4]>=.05 and not overlaps_strong(p,strong)

def fuse_refined(raw,views,predictions,strength,cap,class_gate):
 a=np.asarray(raw,np.float32).reshape(-1,6);strong=a[a[:,4]>=.25];extra=[]
 for pp,dd in zip(views,predictions):
  for p,d in zip(np.asarray(pp,np.float32).reshape(-1,6),np.asarray(dd,np.float32).reshape(-1,5)):
   if not eligible(p,strong):continue
   probability=float(1/(1+np.exp(-np.float32(d[0]))))
   if probability<class_gate:continue
   b=adjust(p,d[1:],strength,cap) if strength else p.copy()
   if overlaps_strong(b,strong):continue
   if b[2]<=b[0] or b[3]<=b[1]:continue
   b[4]*=np.float32(.65);extra.append(b)
 return ac.nms_numpy(np.concatenate([a,np.asarray(extra,np.float32).reshape(-1,6)]),.6,300)

def main():
 assert (ROOT/'training_complete.json').exists() and not (ROOT/'selected.json').exists()
 import torch
 model=make_model().cuda().eval();datasets=cohorts();cache={};baseline={};control={}
 for key,d in datasets.items():
  pixels=[];meta=[];indices=[]
  for r in d['manifest']:
   name=r['name'];sensor,_=ac.sensor400(d['images']/name)
   a=np.asarray(d['base'][name]['detections'],np.float32).reshape(-1,6);strong=a[a[:,4]>=.25]
   for j,pp in enumerate(d['views'][name]):
    for i,b in enumerate(pp):
     b=np.asarray(b,np.float32)
     if not eligible(b,strong):continue
     image,m=patch(sensor,b);pixels.append(image);meta.append(m);indices.append((name,j,i))
  cache[key]=(np.asarray(pixels,np.uint8),np.asarray(meta,np.float32),indices)
  baseline[key]=evaluate([d['base'][r['name']] for r in d['manifest']])['classes']['car'];control[key]=evaluate([d['control'][r['name']] for r in d['manifest']])['classes']['car']
  for r in d['manifest']:
   dummy=[np.zeros((len(v),5),np.float32) for v in d['views'][r['name']]]
   same=fuse_refined(d['base'][r['name']]['detections'],d['views'][r['name']],dummy,0,0,0)
   assert same.tobytes()==np.asarray(d['control'][r['name']]['detections'],np.float32).tobytes(),r['name']
  print('BOX_REFINE_DEV_PATCHES',key,len(pixels),'identity_control_exact',flush=True)
 records=[];best_outputs={};(ROOT/'development').mkdir();begin=time.monotonic()
 for epoch in CHECKPOINTS:
  ck=ROOT/'frozen'/f'epoch{epoch}/model.pt';assert sha(ck)==read(ck.with_name('frozen.json'))['sha256']
  model.load_state_dict(torch.load(ck,map_location='cpu',weights_only=False)['state_dict']);predictions={}
  for key,d in datasets.items():
   pixels,meta,indices=cache[key];outputs=[]
   with torch.inference_mode():
    for at in range(0,len(pixels),256):
     x=torch.from_numpy(np.ascontiguousarray(pixels[at:at+256].transpose(0,3,1,2))).cuda().float()/255;m=torch.from_numpy(meta[at:at+256]).cuda()
     outputs.extend(model(x,m).cpu().tolist())
   groups={r['name']:[np.zeros((len(v),5),np.float32) for v in d['views'][r['name']]] for r in d['manifest']}
   for (name,j,i),v in zip(indices,outputs):groups[name][j][i]=v
   predictions[key]=groups;write(ROOT/'development'/f'epoch{epoch}_{key}_outputs.json',{name:[v.tolist() for v in vs] for name,vs in groups.items()})
  for strength in [.5,1.]:
   for cap in [.1,.25]:
    for class_gate in [0.,.3]:
     scores={};gg={};rows_all={}
     for key,d in datasets.items():
      rows=[]
      for r in d['manifest']:
       name=r['name'];p=fuse_refined(d['base'][name]['detections'],d['views'][name],predictions[key][name],strength,cap,class_gate)
       rows.append(dict(name=name,ground_truth=d['base'][name]['ground_truth'],detections=p.tolist()))
      scores[key]=evaluate(rows)['classes']['car'];gg[key]=conditions(baseline[key],control[key],scores[key]);rows_all[key]=rows
     good=all(all(g.values()) for g in gg.values());tag=f'e{epoch}_s{strength}_c{cap}_g{class_gate}'
     rec=dict(tag=tag,epoch=epoch,checkpoint=str(ck),sha256=sha(ck),strength=strength,cap=cap,class_gate=class_gate,scores=scores,gates=gg,qualified=good)
     records.append(rec);write(ROOT/'development_progress.json',records)
     if good:best_outputs[tag]=rows_all
     print('BOX_REFINE_DEV_SCORE',tag,good,{k:(round(v['ap50'],5),v['tp'],v['fp']) for k,v in scores.items()},gg,'seconds',round(time.monotonic()-begin),flush=True)
 good=[r for r in records if r['qualified']];chosen=max(good,key=lambda r:np.mean([v['ap50'] for v in r['scores'].values()])) if good else None
 write(ROOT/'selected.json',dict(status='ONE_BOX_REFINER_REQUIRES_C_AND_UNUSED_CONFIRMATION' if chosen else 'NO_BOX_REFINER_PASSED_KEEP_ABI27',qualified=chosen is not None,
  chosen=chosen,records=records,baselines=baseline,unverified_controls=control,protocol_sha256=sha(ROOT/'protocol.json'),fresh_inference=False,hardware_access=False,sd_written=False))
 if chosen:
  for key,rows in best_outputs[chosen['tag']].items():write(ROOT/'development'/f'chosen_{key}_predictions.json',rows)
 shutil.copy2(Path(__file__),ROOT/'source'/Path(__file__).name);print('BOX_REFINE_SELECTED',None if chosen is None else chosen['tag'],flush=True)

if __name__=='__main__':main()
