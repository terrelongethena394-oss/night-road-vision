"""Select view-adapted weights on reused development cohorts, never new test."""
import copy,gc,sys,time
import numpy as np
from road_viewadapt_common import *
from road_accuracy_common import Detector

COHORTS={
 'original320':(BASE/'road_classwise_20261030_r2/known320_native',DATA/'dataset/images/val'),
 'low320':(BASE/'road_accuracy_lowlight_20261030_r1/native',BASE/'road_accuracy_lowlight_20261030_r1/fresh/images'),
}

def comparison(current,candidate):
 a=current['all']['classes'];b=candidate['all']['classes'];tp=lambda z:sum(z[k]['tp'] for k in ['truck','bus']);fp=lambda z:sum(z[k]['fp'] for k in ['truck','bus'])
 return dict(car_ap_gain=candidate['all']['classes']['car']['ap50']>=current['all']['classes']['car']['ap50']+.005,car_period_retention=all(candidate['by_time'][p]['classes']['car']['ap50']>=m['classes']['car']['ap50']-.005 for p,m in current['by_time'].items()),car_precision=b['car']['precision']>=a['car']['precision']-.005,car_recall=b['car']['recall']>=a['car']['recall']-.005,fourclass_map=candidate['all']['mAP50']>=current['all']['mAP50']-.002,truck_bus_tp=tp(b)>=.9*tp(a),truck_bus_fp=fp(b)<=.9*fp(a))

def run_views(det,rows,images,out):
 if (out/'complete.json').exists():return read(out/'fused_predictions.json')
 out.mkdir(parents=True,exist_ok=True);full=[];tiles=[[] for _ in range(3)];begin=time.monotonic()
 for start in range(0,len(rows),2):
  tasks=[];ims=[]
  for r in rows[start:start+2]:
   sensor,global_im=sensor400(images/r['name']);views=[global_im]+[sensor[y:y+240,x:x+400] for x,y in TILES]
   for i,im in enumerate(views):tasks.append((r,i));ims.append(im)
  preds=det.run(ims)
  for (r,view),pred in zip(tasks,preds):
   if view==0:full.append(dict(name=r['name'],timeofday=r['timeofday'],ground_truth=r['ground_truth'],detections=pred))
   else:tiles[view-1].append(dict(name=r['name'],timeofday=r['timeofday'],ground_truth=r['ground_truth'],detections=map_tile(pred,*TILES[view-1]).tolist()))
  if (start+2)%80==0:print('VIEWADAPT_DEVELOPMENT_VIEWS',out.parent.name,out.name,start+2,len(rows),round(time.monotonic()-begin),flush=True)
 fused=[dict(name=r['name'],timeofday=r['timeofday'],ground_truth=r['ground_truth'],detections=fuse(r['detections'],[t[i]['detections'] for t in tiles],.75).tolist()) for i,r in enumerate(full)]
 write(out/'global_raw.json',full)
 for i,t in enumerate(tiles):write(out/f'tile_raw_{i}.json',t)
 write(out/'fused_predictions.json',fused);write(out/'metrics.json',metrics(fused));write(out/'complete.json',dict(images=len(rows),four_views_per_image=True,hardware_access=False))
 return fused

def main():
 assert (ROOT/'training_complete.json').exists() and not (ROOT/'selected.json').exists()
 import torch
 det=Detector();current={};baseline_gpu={};cohorts={}
 training=read(ROOT/'training_manifest.json');train_groups={r['group'] for r in training};train_hashes={r['image_sha256'] for r in training}
 write(ROOT/'evaluation_config.json',dict(source_sha256=sha(Path(__file__)),protocol_sha256=sha(ROOT/'protocol.json'),initial_checkpoint_sha256=sha(WEIGHTS),cohorts=list(COHORTS),selection='All predeclared gates versus both actual C baseline and GPU control, maximize mean fourclass AP. No independent new test used here.'))
 for k,(folder,images) in COHORTS.items():
  raw=read(folder/'global_raw.json');tiles=[read(folder/f'tile_raw_{i}.json') for i in range(3)]
  assert not {r['name'].split('-')[0] for r in raw}&train_groups
  assert not {sha(images/r['name']) for r in raw}&train_hashes
  current[k]=metrics([dict(name=r['name'],timeofday=r['timeofday'],ground_truth=r['ground_truth'],detections=fuse(r['detections'],[t[i]['detections'] for t in tiles],.75).tolist()) for i,r in enumerate(raw)])
  cohorts[k]=(raw,images);baseline_gpu[k]=metrics(run_views(det,raw,images,ROOT/'development'/'baseline'/k))
  assert abs(current[k]['all']['classes']['car']['ap50']-baseline_gpu[k]['all']['classes']['car']['ap50'])<=.002,('Baseline GPU vs C exceeds declared numerical check',k)
 write(ROOT/'baseline_gpu_c_check.json',dict(reference=current,gpu=baseline_gpu,car_ap_difference_at_most=.002,comparison='New candidates must pass versus both current C and current GPU, followed by actual C verification if selected.'))
 records=[]
 for epoch in CHECKPOINTS:
  ck=ROOT/'frozen'/f'epoch{epoch}'/'model.pt';assert sha(ck)==read(ck.with_name('frozen.json'))['sha256']
  del det.model;gc.collect();torch.cuda.empty_cache();det.model=copy.deepcopy(torch.load(ck,map_location='cpu',weights_only=False)['model']).float().fuse().eval().cuda()
  scores={k:metrics(run_views(det,rows,images,ROOT/'development'/f'epoch{epoch}'/k)) for k,(rows,images) in cohorts.items()}
  gates={k:comparison(current[k],m) for k,m in scores.items()};gpu_gates={k:comparison(baseline_gpu[k],m) for k,m in scores.items()}
  record=dict(epoch=epoch,checkpoint=str(ck),sha256=sha(ck),scores=scores,gates=gates,gpu_control_gates=gpu_gates,passes=all(all(g.values()) for g in [*gates.values(),*gpu_gates.values()]));records.append(record)
  write(ROOT/'development_progress.json',records);print('VIEWADAPT_EPOCH_ASSESSED',epoch,record['passes'],gates,flush=True)
 good=[r for r in records if r['passes']];chosen=max(good,key=lambda r:np.mean([m['all']['mAP50'] for m in r['scores'].values()])) if good else None
 write(ROOT/'selected.json',dict(status='GPU_DEVELOPMENT_SELECTION_REQUIRES_ACTUAL_C_AND_NEW_HOLDOUT' if chosen else 'NO_WEIGHT_CHECKPOINT_PASSED_RETAIN_ABI24',qualified=bool(chosen),chosen=chosen,records=records,current=current,baseline_gpu=baseline_gpu,protocol_sha256=sha(ROOT/'protocol.json'),fresh_test_inference=False,hardware_access=False,sd_written=False))
 print('VIEWADAPT_SELECTED',None if chosen is None else chosen['epoch'],flush=True)

if __name__=='__main__':main()
