"""One fixed candidate, actual C baseline/candidate on unused224 holdout."""
import os,shutil
import numpy as np
from road_viewadapt_common import *
from evaluate_road_viewadapt import comparison
from road_score_native import Calibrator
from road_numpy_eval import correct

def statistics(rows):
 out=[]
 for r in rows:
  p=np.asarray(r['detections'],np.float32).reshape(-1,6);g=np.asarray(r['ground_truth'],np.float32).reshape(-1,5);tp=correct(p,g,np.array([.5],np.float32))[0][:,0]
  q=p[p[:,4]>=.25];ok=correct(q,g,np.array([.5],np.float32))[0][:,0];rare=(q[:,5]==2)|(q[:,5]==3)
  out.append(dict(tp=tp,conf=p[:,4],cls=p[:,5],car_objects=int((g[:,0]==1).sum()),rare_tp=int((ok&rare).sum()),rare_fp=int((~ok&rare).sum())))
 return out

def car_ap50(stats,ids):
 tp=np.concatenate([stats[i]['tp'] for i in ids]);conf=np.concatenate([stats[i]['conf'] for i in ids]);cls=np.concatenate([stats[i]['cls'] for i in ids]);n=sum(stats[i]['car_objects'] for i in ids)
 order=np.argsort(-conf);t=tp[order][cls[order]==1].cumsum();f=(1-tp[order][cls[order]==1]).cumsum()
 if not n or not len(t):return 0.
 recall=t/(n+1e-16);precision=t/(t+f);mr=np.r_[0.,recall,1.];mp=np.r_[1.,precision,0.];mp=np.maximum.accumulate(mp[::-1])[::-1]
 return float(np.trapezoid(np.interp(np.linspace(0,1,101),mr,mp),np.linspace(0,1,101)))

def uncertainty(raw,new,seed,baseline_ap,candidate_ap):
 a=statistics(raw);b=statistics(new);n=len(a);ids=np.arange(n)
 assert abs(car_ap50(a,ids)-baseline_ap)<1e-12 and abs(car_ap50(b,ids)-candidate_ap)<1e-12
 rng=np.random.default_rng(seed);gains=[];fp=[];tp=[]
 for _ in range(1000):
  draw=rng.integers(0,n,n);gains.append(car_ap50(b,draw)-car_ap50(a,draw));fp.append(sum(a[i]['rare_fp']-b[i]['rare_fp'] for i in draw)*100/n);tp.append(sum(b[i]['rare_tp']-a[i]['rare_tp'] for i in draw)*100/n)
 return dict(images=n,replicates=1000,seed=seed,unit='paired resampling of one unique image/prefix group',car_ap50_difference_interval99=np.quantile(gains,[.005,.995]).tolist(),rare_fp_reduction_per100_images_interval99=np.quantile(fp,[.005,.995]).tolist(),rare_tp_change_per100_images_interval99=np.quantile(tp,[.005,.995]).tolist())

def main():
 selected=read(ROOT/'selected_classcalibrated.json');development=read(ROOT/'c_development_result.json');assert selected['qualified'] and development['qualified'] and development['selection_sha256']==sha(ROOT/'selected_classcalibrated.json')
 assert (ROOT/'fresh/complete.json').exists() and not (ROOT/'fresh_result.json').exists()
 export=read(ROOT/'export/complete.json');manifest=read(ROOT/'fresh/manifest.json');assert len(manifest)==224
 evaluation=ROOT/'fresh_evaluation';evaluation.mkdir(exist_ok=True)
 policy=dict(status='FROZEN_BEFORE_ANY_UNUSED224_DETECTOR_PREDICTIONS',selection_sha256=sha(ROOT/'selected_classcalibrated.json'),weights_sha256=export['weights_sha256'],manifest_sha256=sha(ROOT/'fresh/manifest.json'),gains=selected['chosen']['gains'],gates='All original deployment-adaptation gates unchanged, separately on low160/brighter64, plus paired99% image-bootstrap CI lower>0 for carAP gain in both cohorts. No fresh-driven reselection.',hardware_access=False,sd_written=False)
 if (evaluation/'policy.json').exists():assert read(evaluation/'policy.json')==policy
 else:write(evaluation/'policy.json',policy)
 import native_road_accuracy as native
 allrows={};engine=Calibrator(ROOT)
 for mode in ['baseline','candidate']:
  out=evaluation/mode;out.mkdir(exist_ok=True)
  for kind in ['images','labels']:(out/'fresh'/kind).mkdir(parents=True,exist_ok=True)
  for r in manifest:
   stem=Path(r['name']).stem
   for kind,name,key in [('images',r['name'],'image_sha256'),('labels',stem+'.txt','label_sha256')]:
    source=ROOT/'fresh'/kind/name;dest=out/'fresh'/kind/name;assert sha(source)==r[key]
    if not dest.exists():os.link(source,dest)
    assert sha(dest)==r[key]
  if (out/'fresh/manifest.json').exists():assert read(out/'fresh/manifest.json')==manifest
  else:write(out/'fresh/manifest.json',manifest)
  native.ROOT=out;native.SELECTION_FILE=BASE/'road_accuracy_20261030_r1/selected.json';native.WEIGHTS_FILE=ROOT/'export/weights.f32' if mode=='candidate' else BASE/'road_accuracy_20261030_r1/firmware/runtime/weights.f32';native.EXPECTED_WEIGHTS_SHA=export['weights_sha256'] if mode=='candidate' else '4c15d4b3ad9765f96204d0caa767e024f414149165150c94ed1701a48c4d47d1'
  if not (out/'native/complete.json').exists():native.main()
  rows=read(out/'native/candidate_predictions.json')
  if mode=='candidate':
   rows=[dict(name=r['name'],timeofday=r['timeofday'],ground_truth=r['ground_truth'],detections=engine.run(r['detections'],selected['chosen']['gains']).tolist()) for r in rows];write(out/'calibrated_predictions.json',rows)
  allrows[mode]=rows;print('VIEWADAPT_HOLDOUT_C_MODE_DONE',mode,flush=True)
 scores={};gg={};ci={}
 for cohort in ['low','brighter']:
  split={k:[r for r,m in zip(rr,manifest) if m['cohort']==cohort] for k,rr in allrows.items()};m={k:metrics(rr) for k,rr in split.items()};scores[cohort]=m;gg[cohort]=comparison(m['baseline'],m['candidate'])
  ci[cohort]=uncertainty(split['baseline'],split['candidate'],SEED+101+(cohort=='brighter'),m['baseline']['all']['classes']['car']['ap50'],m['candidate']['all']['classes']['car']['ap50']);gg[cohort]['car_ap_ci99_positive']=ci[cohort]['car_ap50_difference_interval99'][0]>0
 accepted=all(all(g.values()) for g in gg.values())
 write(ROOT/'fresh_result.json',dict(status='VIEWADAPT_INDEPENDENT_ACTUAL_C_CONFIRMATION_ACCEPTED' if accepted else 'VIEWADAPT_INDEPENDENT_ACTUAL_C_CONFIRMATION_REJECTED_RETAIN_ABI24',accepted=accepted,scores=scores,gates=gg,paired_uncertainty=ci,selection_sha256=sha(ROOT/'selected_classcalibrated.json'),weights_sha256=export['weights_sha256'],manifest_sha256=sha(ROOT/'fresh/manifest.json'),no_test_driven_reselection=True,all_class_calibration_c_numpy_byte_exact=True,hardware_access=False,sd_written=False))
 print('VIEWADAPT_UNUSED224_RESULT',accepted,gg,flush=True)

if __name__=='__main__':main()
