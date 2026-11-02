"""Run actual portable C network on reused development before unused holdout."""
import os,shutil
import numpy as np
from road_viewadapt_common import *
from evaluate_road_viewadapt import COHORTS,comparison
from road_score_native import Calibrator

def main():
 selected=read(ROOT/'selected_classcalibrated.json');assert selected['qualified'];export=read(ROOT/'export/complete.json');assert export['selection_sha256']==sha(ROOT/'selected_classcalibrated.json')
 out=ROOT/'native_development';out.mkdir(exist_ok=True)
 if not (out/'fresh/manifest.json').exists():
  for kind in ['images','labels']:(out/'fresh'/kind).mkdir(parents=True,exist_ok=True)
  records=[]
  for cohort,(cache,images) in COHORTS.items():
   for r in read(cache/'global_raw.json'):
    stem=Path(r['name']).stem;label=images.parent.parent/'labels'/images.name/(stem+'.txt') if cohort=='original320' else images.parent/'labels'/(stem+'.txt')
    assert label.exists() and np.array_equal(truth(label),np.asarray(r['ground_truth'],np.float32).reshape(-1,5))
    for source,dest in [(images/r['name'],out/'fresh/images'/r['name']),(label,out/'fresh/labels'/(stem+'.txt'))]:
     if not dest.exists():os.link(source,dest)
     assert sha(source)==sha(dest)
    records.append(dict(name=r['name'],timeofday=r['timeofday'],cohort=cohort,source_image_sha256=sha(images/r['name']),source_label_sha256=sha(label)))
  assert len(records)==640 and len({r['name'] for r in records})==640;write(out/'fresh/manifest.json',records)
 import native_road_accuracy as native
 native.ROOT=out;native.SELECTION_FILE=BASE/'road_accuracy_20261030_r1/selected.json';native.WEIGHTS_FILE=ROOT/'export/weights.f32';native.EXPECTED_WEIGHTS_SHA=export['weights_sha256']
 if not (out/'native/complete.json').exists():native.main()
 manifest=read(out/'fresh/manifest.json');rows=read(out/'native/candidate_predictions.json');engine=Calibrator(ROOT);calibrated=[]
 for r in rows:calibrated.append(dict(name=r['name'],timeofday=r['timeofday'],ground_truth=r['ground_truth'],detections=engine.run(r['detections'],selected['chosen']['gains']).tolist()))
 scores={k:metrics([r for r,m in zip(calibrated,manifest) if m['cohort']==k]) for k in COHORTS};gg={k:comparison(selected['current'][k],m) for k,m in scores.items()}
 write(out/'calibrated_predictions.json',calibrated);write(ROOT/'c_development_result.json',dict(status='ACTUAL_C_DEVELOPMENT_PASSED_READY_FOR_UNUSED_HOLDOUT' if all(all(g.values()) for g in gg.values()) else 'ACTUAL_C_DEVELOPMENT_REJECTED_RETAIN_ABI24',qualified=all(all(g.values()) for g in gg.values()),gates=gg,scores=scores,baseline=selected['current'],all_calibration_c_numpy_byte_exact=True,selection_sha256=sha(ROOT/'selected_classcalibrated.json'),weights_sha256=export['weights_sha256'],hardware_access=False,sd_written=False));print('VIEWADAPT_ACTUAL_C_GATES',gg,flush=True)

if __name__=='__main__':main()
