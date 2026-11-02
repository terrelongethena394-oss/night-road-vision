"""One frozen new-group test with paired image bootstrap; no checkpoint reselection."""
from pathlib import Path
import time
import cv2,numpy as np
from road_twilight_common import *
from evaluate_road_twilight import evaluate,gates
def main():
 assert (ROOT/'fresh/complete.json').exists()
 policy=ROOT/'fresh_release_policy.json'
 if not policy.exists():write(policy,dict(status='RELEASE_AND_UNCERTAINTY_RULES_FROZEN_BEFORE_FRESH_PREDICTIONS',raw_fallback='A separately frozen raw control may improve recognition without proving enhancement helps. Require duskAP>=original+.01, overall>=original+.005, night/day>=original-.005, dusk-person recall>=original-.02, dusk totalFP/personFP<=1.10*original+2.',enhancement='All previously frozen validation and point gates plus positive paired CI versus matched raw control.',uncertainty='1000 paired filename-prefix-group bootstrap replicates; two release contrasts, use percentile97.5% intervals (1.25,98.75) each as a Bonferroni-style familywise precaution. Both branches require lower bound>0. No statistical claim about individual classes.',seed=2026102746,holdout_read_only=True,if_no_old_validation_improved_candidate='Do not consume new test predictions; preserve metadata-only new holdout for further validation-only development.'))
 start=time.monotonic()
 while not ((ROOT/'selected.json').exists() and (ROOT/'training_complete.json').exists()):
  if time.monotonic()-start>10800:raise TimeoutError('Selection not finished')
  time.sleep(2)
 sel=read(ROOT/'selected.json');control=sel['control'];candidate=sel['candidate']
 old_gain=sel['control_metrics']['by_time']['dawn/dusk']['mAP50']-sel['original']['by_time']['dawn/dusk']['mAP50']
 if not sel['enhancement_validation_accepted'] and (control['epoch']==0 or old_gain<.01):
  write(ROOT/'holdout_not_consumed.json',dict(status='NO_OLD_VALIDATION_ELIGIBLE_UPGRADE_NEW_TEST_REMAINS_UNREAD',selected_sha256=sha(ROOT/'selected.json'),training_complete_sha256=sha(ROOT/'training_complete.json'),hardware_access=False));print('TWILIGHT_NEW_TEST_NOT_CONSUMED_NO_QUALIFIED_CANDIDATE',flush=True);return
 for r in [control,candidate]:assert sha(r['weights'])==r['sha256']
 out=ROOT/'fresh_evaluation';out.mkdir(exist_ok=False);write(out/'frozen.json',dict(status='CANDIDATES_FROZEN_BEFORE_ANY_NEW_HOLDOUT_FORWARD',selection_sha256=sha(ROOT/'selected.json'),policy_sha256=sha(policy),control=control,candidate=candidate,data_sha256=sha(ROOT/'fresh/manifest.json')))
 from prepare_road_light import sensor_proxy
 from road_enhance_common import enhance
 from road_arm_common import preprocess400
 rows=[{**r,'label_path':str(ROOT/'fresh/labels'/(Path(r['name']).stem+'.txt'))} for r in read(ROOT/'fresh/manifest.json')]
 raw={r['name']:sensor_proxy(cv2.imread(str(ROOT/'fresh/images'/r['name']))[:,:,::-1].copy()) for r in rows}
 def load(active):return lambda r:preprocess400(enhance(raw[r['name']],1,32)[0] if active else raw[r['name']])
 baseline=evaluate(TEACHER,rows,load(False),out/'original','original')
 if control['epoch']==0:
  raw_control=baseline;control_predictions=out/'original/original_predictions.json'
 else:
  raw_control=evaluate(control['weights'],rows,load(False),out/'control','control');control_predictions=out/'control/control_predictions.json'
 enhanced_raw=evaluate(candidate['weights'],rows,load(False),out/'candidate_raw','candidate_raw');enhanced=evaluate(candidate['weights'],rows,load(True),out/'candidate_enh','candidate_enh')
 enhanced_gates=gates(baseline,raw_control,enhanced_raw,enhanced)
 a=raw_control;b=baseline;ap=a['by_time']['dawn/dusk'];bp=b['by_time']['dawn/dusk'];pa=ap['classes']['person'];pb=bp['classes']['person']
 raw_gates=dict(dusk=ap['mAP50']>=bp['mAP50']+.01,overall=a['all']['mAP50']>=b['all']['mAP50']+.005,night=a['by_time']['night']['mAP50']>=b['by_time']['night']['mAP50']-.005,day=a['by_time']['daytime']['mAP50']>=b['by_time']['daytime']['mAP50']-.005,dusk_person_recall=pa['recall']>=pb['recall']-.02,dusk_fp=sum(v['fp'] for v in ap['classes'].values())<=1.1*sum(v['fp'] for v in bp['classes'].values())+2,dusk_person_fp=pa['fp']<=1.1*pb['fp']+2)
 from utils.metrics import compute_ap,ap_per_class
 def records(p):
  result=[]
  for r in read(p):
   if r['timeofday']!='dawn/dusk':continue
   pred=np.array(r['detections'],np.float64).reshape(-1,6);tp=np.array(r['correct'],bool).reshape(-1,10)[:,0];truth=np.array(r['ground_truth'],np.float64).reshape(-1,5)
   result.append((r['name'],tp,pred[:,4],pred[:,5],truth[:,0]))
  return sorted(result,key=lambda r:r[0])
 original_records=records(out/'original/original_predictions.json');ctrl_records=records(control_predictions);enh_records=records(out/'candidate_enh/candidate_enh_predictions.json');assert [r[0] for r in original_records]==[r[0] for r in ctrl_records]==[r[0] for r in enh_records] and len(original_records)==160
 def arrays(recs,idx):return tuple(np.concatenate([recs[i][j] for i in idx]) for j in [1,2,3,4])
 def fast_ap(a):
  tp,conf,pc,tc=a;order=np.argsort(-conf);tp=tp[order];pc=pc[order];classes,counts=np.unique(tc,return_counts=True);values=[]
  for c,n in zip(classes,counts):
   good=pc==c
   if not good.any():values.append(0.);continue
   t=tp[good].cumsum();f=(1-tp[good]).cumsum();values.append(compute_ap(t/(n+1e-16),t/(t+f))[0])
  return float(np.mean(values))
 rng=np.random.default_rng(2026102746);deltas=[];audit=[]
 for k in range(1000):
  idx=rng.integers(0,160,160);arr=[arrays(r,idx) for r in [original_records,ctrl_records,enh_records]];vals=[fast_ap(a) for a in arr]
  if k<20:
   for a,value in zip(arr,vals):
    tp,conf,pc,tc=a;official=float(ap_per_class(tp[:,None],conf,pc,tc,names={0:'person',1:'car',2:'truck',3:'bus'})[5][:,0].mean());assert abs(value-official)<1e-12
   audit.append(k)
  deltas.append([vals[1]-vals[0],vals[2]-vals[1]])
  if (k+1)%200==0:print('TWILIGHT_PAIRED_BOOTSTRAP',k+1,flush=True)
 ds=np.asarray(deltas);ci=np.percentile(ds,[1.25,98.75],axis=0);uncertainty=dict(seed=2026102746,replicates=1000,interval_percent=97.5,raw_control_minus_original=ci[:,0].tolist(),enhanced_minus_matched_raw=ci[:,1].tolist(),first20_replicates_all_three_APs_equal_upstream=True)
 raw_accepted=all(raw_gates.values()) and ci[0,0]>0
 enhancement_accepted=sel['enhancement_validation_accepted'] and all(enhanced_gates.values()) and ci[0,1]>0
 decision='enhanced_input' if enhancement_accepted else ('improved_raw' if raw_accepted else 'retain_current')
 result=dict(status='FROZEN_TWILIGHT_NEW480_COMPARISON_COMPLETE',original=baseline,raw_control=raw_control,candidate_raw=enhanced_raw,candidate_enhanced=enhanced,enhanced_point_gates=enhanced_gates,raw_fallback_gates=raw_gates,uncertainty=uncertainty,raw_detector_upgrade_accepted=raw_accepted,enhancement_upgrade_accepted=enhancement_accepted,deployment_decision=decision,selection_sha256=sha(ROOT/'selected.json'),frozen_models=read(out/'frozen.json'),no_checkpoint_reselection=True,hardware_access=False,sd_written=False)
 write(ROOT/'fresh_complete.json',result);np.save(out/'paired_bootstrap_deltas.npy',ds);print('TWILIGHT_FRESH_RELEASE_DECISION',decision,uncertainty,enhanced_gates,raw_gates,flush=True)
if __name__=='__main__':main()
