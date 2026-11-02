"""Joint class calibration on reused development only; all original gates intact."""
import copy,itertools,shutil
import numpy as np
from road_viewadapt_common import *
from road_score_calibration import calibrate
from evaluate_road_viewadapt import comparison,COHORTS

def merge(truck,bus):
 m=copy.deepcopy(truck)
 for part,source in [(m['all'],bus['all'])]+[(m['by_time'][t],bus['by_time'][t]) for t in m['by_time']]:
  part['classes']['bus']=copy.deepcopy(source['classes']['bus']);valid=[c for c in part['classes'].values() if c['objects']]
  part['mAP50']=float(np.mean([c['ap50'] for c in valid]));part['mAP50_95']=float(np.mean([c['ap50_95'] for c in valid]));part['vehicle_mAP50']=float(np.mean([c['ap50'] for n,c in part['classes'].items() if n in ['car','truck','bus'] and c['objects']]))
 return m

def main():
 shared=read(ROOT/'selected_calibrated.json');assert not shared['qualified'] and not (ROOT/'class_calibration_protocol.json').exists()
 gains=sorted({r['gain'] for r in shared['records']})
 write(ROOT/'class_calibration_protocol.json',dict(status='CLASSWISE_DEVELOPMENT_EXTENSION_BEFORE_ANY_UNUSED_HOLDOUT_INFERENCE',reason='A shared truck/bus gain cannot meet all gates. Their score distributions differ; use the same six predeclared gains independently for each class. No accuracy gate is relaxed; no new holdout prediction is accessed.',gains=gains,checkpoints=CHECKPOINTS,selection='Max mean fourclass mAP50, tie pooled truck/bus F0.5, then smaller sum of gains, only candidates meeting all original gates versus both C and GPU baseline in both cohorts.',optimization='Per-class metrics are independent because geometry, classes, NMS and output count are unchanged. Recombine already computed class metrics for grid, then recompute complete selected metrics to verify equivalence.',no_fresh_inference=True,hardware_access=False,sd_written=False))
 records=[]
 for epoch in CHECKPOINTS:
  by={r['gain']:r for r in shared['records'] if r['epoch']==epoch}
  for tg,bg in itertools.product(gains,gains):
   scores={k:merge(by[tg]['scores'][k],by[bg]['scores'][k]) for k in COHORTS};gg={k:comparison(shared['current'][k],m) for k,m in scores.items()};gpu={k:comparison(shared['baseline_gpu'][k],m) for k,m in scores.items()}
   c=[m['all']['classes'] for m in scores.values()];tp=sum(z[n]['tp'] for z in c for n in ['truck','bus']);fp=sum(z[n]['fp'] for z in c for n in ['truck','bus']);objects=sum(z[n]['objects'] for z in c for n in ['truck','bus']);p=tp/(tp+fp);r=tp/objects
   rec=dict(epoch=epoch,checkpoint=by[tg]['checkpoint'],sha256=by[tg]['sha256'],gains=[tg,bg],scores=scores,gates=gg,gpu_control_gates=gpu,passes=all(all(g.values()) for g in [*gg.values(),*gpu.values()]),pooled_f05=1.25*p*r/(.25*p+r));records.append(rec)
 good=[r for r in records if r['passes']];chosen=max(good,key=lambda r:(np.mean([m['all']['mAP50'] for m in r['scores'].values()]),r['pooled_f05'],-sum(r['gains']))) if good else None
 if chosen:
  epoch=chosen['epoch']
  for k in COHORTS:
   rows=read(ROOT/'development'/f'epoch{epoch}'/k/'fused_predictions.json');out=[dict(name=r['name'],timeofday=r['timeofday'],ground_truth=r['ground_truth'],detections=calibrate(r['detections'],chosen['gains']).tolist()) for r in rows]
   actual=metrics(out)
   for pa,pb in [(actual['all'],chosen['scores'][k]['all'])]+[(actual['by_time'][t],chosen['scores'][k]['by_time'][t]) for t in actual['by_time']]:
    assert pa['classes']==pb['classes']
    assert abs(pa['mAP50']-pb['mAP50'])<1e-12 and abs(pa['mAP50_95']-pb['mAP50_95'])<1e-12
   chosen['scores'][k]=actual;folder=ROOT/'calibrated_development'/k;folder.mkdir(parents=True);write(folder/'predictions.json',out);write(folder/'metrics.json',actual)
 write(ROOT/'selected_classcalibrated.json',dict(status='CLASS_CALIBRATED_CANDIDATE_FROZEN_REQUIRES_ACTUAL_C_AND_UNUSED_TEST' if chosen else 'NO_CLASS_CALIBRATED_CANDIDATE_PASSED_RETAIN_ABI24',qualified=bool(chosen),chosen=chosen,records=records,current=shared['current'],baseline_gpu=shared['baseline_gpu'],shared_selection_sha256=sha(ROOT/'selected_calibrated.json'),class_calibration_protocol_sha256=sha(ROOT/'class_calibration_protocol.json'),no_fresh_test_inference=True,hardware_access=False,sd_written=False))
 for n in ['road_score_calibration.py','study_viewadapt_classcalibration.py']:shutil.copy2(Path(__file__).with_name(n),ROOT/'source'/n)
 print('VIEWADAPT_CLASS_CALIBRATION',None if chosen is None else (chosen['epoch'],chosen['gains']),len(good),'qualified',flush=True)

if __name__=='__main__':main()
