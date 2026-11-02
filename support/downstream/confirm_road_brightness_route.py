"""Fresh416 confirmation of one frozen scene router, no fresh-driven tuning."""
import os
import numpy as np
from road_brightness_route_common import *
from road_accuracy_common import sensor400
from road_score_native import Calibrator
from prove_brightness_router import Router
from confirm_road_viewadapt import statistics,car_ap50

def bootstrap(a,b):
 aa=statistics(a);bb=statistics(b);n=len(aa);rng=np.random.default_rng(SEED+100);precision=[];fp=[];ap=[]
 for _ in range(2000):
  ids=rng.integers(0,n,n);at=sum(aa[i]['rare_tp'] for i in ids);af=sum(aa[i]['rare_fp'] for i in ids);bt=sum(bb[i]['rare_tp'] for i in ids);bf=sum(bb[i]['rare_fp'] for i in ids)
  precision.append((bt/(bt+bf) if bt+bf else 0)-(at/(at+af) if at+af else 0));fp.append((af-bf)*100/n);ap.append(car_ap50(bb,ids)-car_ap50(aa,ids))
 return dict(images=n,replicates=2000,seed=SEED+100,confidence=.995,precision_difference_interval995=np.quantile(precision,[.0025,.9975]).tolist(),false_positive_reduction_per100_interval995=np.quantile(fp,[.0025,.9975]).tolist(),car_ap50_difference_interval995_descriptive=np.quantile(ap,[.0025,.9975]).tolist())

def main():
 assert (ROOT/'fresh/complete.json').exists() and (ROOT/'router_c/complete.json').exists() and not (ROOT/'fresh_result.json').exists()
 manifest=read(ROOT/'fresh/manifest.json');assert len(manifest)==416
 export=read(ADAPT/'export/complete.json');assert export['weights_sha256']==read(ROOT/'protocol.json')['weights']['dark_adapted']
 out=ROOT/'fresh_evaluation';out.mkdir(exist_ok=True);router=Router();cal=Calibrator(ROOT)
 routes={}
 for m in manifest:
  _,raw=sensor400(ROOT/'fresh/images'/m['name']);v=router.run(raw);assert v==(m['mean_y']<=GATE_MEAN);routes[m['name']]=v
 write(out/'policy.json',dict(status='FROZEN_BEFORE_ANY_FRESH416_PREDICTIONS',protocol_sha256=sha(ROOT/'protocol.json'),manifest_sha256=sha(ROOT/'fresh/manifest.json'),route_by_name=routes,low_primary='Rare vehicle precision gain and FP reduction 99.5% paired CI lower>0, same fixed quality retention gates. Bright byte exact. No significant-carAP claim implied.',hardware_access=False,sd_written=False))
 import native_road_accuracy as native
 rows_by_mode={};cached={}
 for mode in ['baseline','routed_low','routed_bright']:
  records=manifest if mode=='baseline' else [r for r in manifest if bool(routes[r['name']])==(mode=='routed_low')]
  root=out/mode;root.mkdir(exist_ok=True)
  for kind in ['images','labels']:(root/'fresh'/kind).mkdir(parents=True,exist_ok=True)
  for r in records:
   for kind,name,key in [('images',r['name'],'image_sha256'),('labels',Path(r['name']).stem+'.txt','label_sha256')]:
    source=ROOT/'fresh'/kind/name;dest=root/'fresh'/kind/name;assert sha(source)==r[key]
    if not dest.exists():os.link(source,dest)
    assert sha(dest)==r[key]
  if (root/'fresh/manifest.json').exists():assert read(root/'fresh/manifest.json')==records
  else:write(root/'fresh/manifest.json',records)
  native.ROOT=root;native.SELECTION_FILE=BASE/'road_accuracy_20261030_r1/selected.json';native.WEIGHTS_FILE=ADAPT/'export/weights.f32' if mode=='routed_low' else BASE/'road_accuracy_20261030_r1/firmware/runtime/weights.f32';native.EXPECTED_WEIGHTS_SHA=read(ROOT/'protocol.json')['weights']['dark_adapted' if mode=='routed_low' else 'bright_stable']
  if not (root/'native/complete.json').exists():native.main()
  rows=read(root/'native/candidate_predictions.json')
  if mode=='routed_low':rows=[dict(name=r['name'],timeofday=r['timeofday'],ground_truth=r['ground_truth'],detections=cal.run(r['detections'],GAINS).tolist()) for r in rows]
  rows_by_mode[mode]=rows;cached[mode]=root/'native';print('ROUTED_HOLDOUT_MODE_DONE',mode,flush=True)
 baseline=rows_by_mode['baseline'];new_byname={r['name']:r for key in ['routed_low','routed_bright'] for r in rows_by_mode[key]};routed=[new_byname[r['name']] for r in manifest];write(out/'routed_predictions.json',routed)
 # Independent executions of the original neural model on bright frames,
 # checking every cached view's complete detections before fused output.
 for tag in ['global_raw','tile_raw_0','tile_raw_1','tile_raw_2']:
  lookup={r['name']:r for r in read(cached['baseline']/(tag+'.json'))}
  for r in read(cached['routed_bright']/(tag+'.json')):assert np.asarray(r['detections'],'<f4').tobytes()==np.asarray(lookup[r['name']]['detections'],'<f4').tobytes()
 for a,b in zip(baseline,routed):
  if not routes[a['name']]:assert np.asarray(a['detections'],'<f4').tobytes()==np.asarray(b['detections'],'<f4').tobytes()
 low_old=[r for r in baseline if routes[r['name']]];low_new=[r for r in routed if routes[r['name']]];m0=metrics(low_old);m1=metrics(low_new);gg=gates(m0,m1);ci=bootstrap(low_old,low_new);gg['rare_precision_ci995_positive']=ci['precision_difference_interval995'][0]>0;gg['rare_fp_ci995_positive']=ci['false_positive_reduction_per100_interval995'][0]>0
 accepted=all(gg.values());write(ROOT/'fresh_result.json',dict(status='ROUTED416_INDEPENDENT_CONFIRMATION_ACCEPTED' if accepted else 'ROUTED416_INDEPENDENT_CONFIRMATION_REJECTED_RETAIN_ABI24',accepted=accepted,low_gates=gg,low_baseline=m0,low_candidate=m1,uncertainty=ci,brighter=dict(images=len(rows_by_mode['routed_bright']),all4_view_detections_and_fused_outputs_byte_exact_to_independent_stable_runs=True,metrics=metrics(rows_by_mode['routed_bright'])),route_all416_c_numpy_exact=True,model_sha256=read(ROOT/'protocol.json')['weights'],new_confirmation_no_reselection=True,hardware_access=False,sd_written=False));print('ROUTED416_CONFIRMATION_RESULT',accepted,gg,ci,flush=True)

if __name__=='__main__':main()
