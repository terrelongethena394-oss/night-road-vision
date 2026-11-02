"""Develop a small add-on verifier, retaining original4view boxes."""
import shutil,time
import numpy as np
import road_accuracy_common as ac
from road_numpy_eval import evaluate
from car_patch_verifier_common import *
from study_car_zoom_20261030 import map_zoom,XS

def fuse_verified(raw,views,probs,weight,power):
 a=np.asarray(raw,np.float32).reshape(-1,6);strong=a[a[:,4]>=.25];extra=[]
 for pp,qq in zip(views,probs):
  for p,q in zip(np.asarray(pp,np.float32).reshape(-1,6),qq):
   if p[4]<.05:continue
   if len(strong):
    area=np.maximum(0,p[2:4]-p[:2]).prod();oa=np.maximum(0,strong[:,2:4]-strong[:,:2]).prod(1)
    inter=np.maximum(0,np.minimum(p[2:4],strong[:,2:4])-np.maximum(p[:2],strong[:,:2])).prod(1)
    if np.any((inter/(area+oa-inter+1e-9)>=.3)|(inter/(np.minimum(area,oa)+1e-9)>=.8)):continue
   b=p.copy();factor=np.sqrt(np.float32(q)) if power==.5 else np.float32(q)
   b[4]*=np.float32(weight)*factor
   if b[4]>=.001:extra.append(b)
 return ac.nms_numpy(np.concatenate([a,np.asarray(extra,np.float32).reshape(-1,6)]),.6,300)

def cohorts():
 data=BASE/'road_brightness_route_20261030_r1/fresh'
 low=[r for r in read(data/'manifest.json') if r['cohort']=='low'];base={r['name']:r['raw_multiview'] for r in read(BASE/'road_bright_detector_audit_20261030_r1/predictions.json')}
 views={r['name']:r['mapped'] for r in read(ZOOM/'zoom_predictions.json')};control={r['name']:r for r in read(ZOOM/'chosen_predictions.json')}
 out={'reused320':dict(manifest=low,images=data/'images',base=base,views=views,control=control)}
 data=ZOOM/'confirmation/fresh';low=[r for r in read(data/'manifest.json') if r['cohort']=='low']
 base={r['name']:r for r in read(ZOOM/'confirmation/baseline_predictions.json')};control={r['name']:r for r in read(ZOOM/'confirmation/candidate_predictions.json')}
 local=[{r['name']:r['detections'] for r in read(ZOOM/'confirmation'/f'zoom{i}_actual_c.json')} for i in range(3)]
 y=read(ZOOM/'protocol.json')['geometry']['y'];views={r['name']:[map_zoom(local[j][r['name']],x,y).tolist() for j,x in enumerate(XS)] for r in low}
 out['reused160']=dict(manifest=low,images=data/'images',base=base,views=views,control=control)
 return out

def conditions(base,control,new):
 return dict(ap=new['ap50']>=base['ap50']+.01,precision=new['precision']>=base['precision']-.005,
  recall=new['recall']>=base['recall']+.01,
  added_fp_reduced25=max(0,new['fp']-base['fp'])<=.75*max(0,control['fp']-base['fp']),
  added_tp_retained90=new['tp']-base['tp']>=.9*(control['tp']-base['tp']))

def main():
 assert (ROOT/'training_complete.json').exists() and not (ROOT/'selected.json').exists()
 import torch
 torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
 model=make_model().cuda().eval();datasets=cohorts();cache={};baseline={};control={}
 for key,d in datasets.items():
  images=[];meta=[];indices=[]
  for r in d['manifest']:
   sensor,_=ac.sensor400(d['images']/r['name'])
   for j,pp in enumerate(d['views'][r['name']]):
    for i,b in enumerate(pp):
     a,m=patch(sensor,b);images.append(a);meta.append(m);indices.append((r['name'],j,i))
  cache[key]=(np.asarray(images,np.uint8),np.asarray(meta,np.float32),indices)
  baseline[key]=evaluate([d['base'][r['name']] for r in d['manifest']])['classes']['car']
  control[key]=evaluate([d['control'][r['name']] for r in d['manifest']])['classes']['car']
  print('VERIFIER_DEV_PATCHES',key,len(images),flush=True)
 records=[];begin=time.monotonic();(ROOT/'development').mkdir();best_outputs={}
 for epoch in CHECKPOINTS:
  ck=ROOT/'frozen'/f'epoch{epoch}/model.pt';assert sha(ck)==read(ck.with_name('frozen.json'))['sha256']
  saved=torch.load(ck,map_location='cpu',weights_only=False);model.load_state_dict(saved['state_dict']);probabilities={}
  for key,d in datasets.items():
   pixels,meta,indices=cache[key];pp=[]
   with torch.inference_mode():
    for at in range(0,len(pixels),256):
     x=torch.from_numpy(np.ascontiguousarray(pixels[at:at+256].transpose(0,3,1,2))).cuda().float()/255
     m=torch.from_numpy(meta[at:at+256]).cuda();pp.extend(torch.sigmoid(model(x,m)).cpu().tolist())
   groups={r['name']:[np.zeros(len(v),np.float32) for v in d['views'][r['name']]] for r in d['manifest']}
   for (name,j,i),q in zip(indices,pp):groups[name][j][i]=q
   probabilities[key]=groups
   write(ROOT/'development'/f'epoch{epoch}_{key}_probabilities.json',{name:[v.tolist() for v in vs] for name,vs in groups.items()})
  for weight in [.65,.85,1.]:
   for power in [.5,1.]:
    scores={};gg={};predictions={}
    for key,d in datasets.items():
     rows=[]
     for r in d['manifest']:
      name=r['name'];p=fuse_verified(d['base'][name]['detections'],d['views'][name],probabilities[key][name],weight,power)
      rows.append(dict(name=name,ground_truth=d['base'][name]['ground_truth'],detections=p.tolist()))
     scores[key]=evaluate(rows)['classes']['car'];gg[key]=conditions(baseline[key],control[key],scores[key]);predictions[key]=rows
    passed=all(all(g.values()) for g in gg.values());tag=f'e{epoch}_w{weight}_p{power}'
    record=dict(tag=tag,epoch=epoch,checkpoint=str(ck),sha256=sha(ck),weight=weight,power=power,scores=scores,gates=gg,qualified=passed)
    records.append(record);write(ROOT/'development_progress.json',records)
    if passed:best_outputs[tag]=predictions
    print('VERIFIER_DEV_SCORE',tag,passed,{k:(round(v['ap50'],5),v['tp'],v['fp']) for k,v in scores.items()},gg,'seconds',round(time.monotonic()-begin),flush=True)
 good=[r for r in records if r['qualified']];chosen=max(good,key=lambda r:np.mean([v['ap50'] for v in r['scores'].values()])) if good else None
 selected=dict(status='VERIFIER_DEVELOPMENT_PASS_REQUIRES_C_AND_NEW_CONFIRMATION' if chosen else 'NO_VERIFIER_CANDIDATE_KEEP_ABI27',qualified=chosen is not None,
  chosen=chosen,records=records,baselines=baseline,unverified_controls=control,protocol_sha256=sha(ROOT/'protocol.json'),
  reused_development_images=480,new_test_inference=False,hardware_access=False,sd_written=False)
 write(ROOT/'selected.json',selected)
 if chosen:
  for key,rows in best_outputs[chosen['tag']].items():write(ROOT/'development'/f'chosen_{key}_predictions.json',rows)
 shutil.copy2(Path(__file__),ROOT/'source'/Path(__file__).name)
 print('PATCH_VERIFIER_SELECTED',None if chosen is None else chosen['tag'],flush=True)

if __name__=='__main__':main()
