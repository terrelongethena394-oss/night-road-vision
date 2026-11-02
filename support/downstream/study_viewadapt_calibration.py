"""Development-only extension: keep all gates, jointly select fixed odds gain."""
import shutil
from road_viewadapt_common import *
from road_score_calibration import calibrate
from evaluate_road_viewadapt import comparison,COHORTS
GAINS=[1.,1.1,1.25,1.5,1.75,2.]

def main():
 selected=read(ROOT/'selected.json');assert not selected['qualified'] and not (ROOT/'calibration_protocol.json').exists()
 write(ROOT/'calibration_protocol.json',dict(status='DEVELOPMENT_EXTENSION_FROZEN_BEFORE_CALIBRATION_SEARCH',reason='Uncalibrated trained checkpoints improved car AP but failed operating-point truck/bus TP retention. Use reused development data only to select a shared, fixed truck/bus odds multiplier, keeping every original quality gate unchanged. Original failed selection is preserved.',gains=GAINS,checkpoints=CHECKPOINTS,formula='s_new=g*s/(1+(g-1)*s), truck/bus only after unchanged fusion; stable score sort, no new NMS, no car/person geometry/score changes.',selection='Highest mean fourclass mAP50 passing all original gates versus both C baseline and GPU control on both development cohorts; tie highest pooled truck/bus F0.5, then smaller gain.',no_gate_relaxation=True,no_fresh_inference=True,source_sha256=sha(Path(__file__)),hardware_access=False,sd_written=False))
 for n in ['road_score_calibration.py','study_viewadapt_calibration.py']:shutil.copy2(Path(__file__).with_name(n),ROOT/'source'/n)
 records=[]
 for record in selected['records']:
  epoch=record['epoch'];rows={k:read(ROOT/'development'/f'epoch{epoch}'/k/'fused_predictions.json') for k in COHORTS}
  for gain in GAINS:
   mapped={k:[dict(name=r['name'],timeofday=r['timeofday'],ground_truth=r['ground_truth'],detections=calibrate(r['detections'],gain).tolist()) for r in rr] for k,rr in rows.items()}
   scores={k:metrics(rr) for k,rr in mapped.items()};gates={k:comparison(selected['current'][k],m) for k,m in scores.items()};gpu={k:comparison(selected['baseline_gpu'][k],m) for k,m in scores.items()}
   values=[m['all']['classes'] for m in scores.values()];tp=sum(v[c]['tp'] for v in values for c in ['truck','bus']);fp=sum(v[c]['fp'] for v in values for c in ['truck','bus']);objects=sum(v[c]['objects'] for v in values for c in ['truck','bus']);p=tp/(tp+fp);r=tp/objects
   z=dict(epoch=epoch,checkpoint=record['checkpoint'],sha256=record['sha256'],gain=gain,scores=scores,gates=gates,gpu_control_gates=gpu,passes=all(all(g.values()) for g in [*gates.values(),*gpu.values()]),pooled_f05=1.25*p*r/(.25*p+r));records.append(z)
   print('VIEWADAPT_CALIBRATION',epoch,gain,z['passes'],flush=True)
 good=[r for r in records if r['passes']];chosen=max(good,key=lambda r:(sum(m['all']['mAP50'] for m in r['scores'].values())/2,r['pooled_f05'],-r['gain'])) if good else None
 write(ROOT/'selected_calibrated.json',dict(status='CALIBRATED_GPU_CANDIDATE_FROZEN_REQUIRES_ACTUAL_C_AND_UNUSED_TEST' if chosen else 'NO_CALIBRATED_CANDIDATE_PASSED_RETAIN_ABI24',qualified=bool(chosen),chosen=chosen,records=records,current=selected['current'],baseline_gpu=selected['baseline_gpu'],original_selection_sha256=sha(ROOT/'selected.json'),calibration_protocol_sha256=sha(ROOT/'calibration_protocol.json'),no_fresh_test_inference=True,hardware_access=False,sd_written=False))
 print('VIEWADAPT_CALIBRATED_SELECTED',None if chosen is None else (chosen['epoch'],chosen['gain']),flush=True)

if __name__=='__main__':main()
