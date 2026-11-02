"""Post-freeze ablation on the same new images, no checkpoint/policy reselection."""
from pathlib import Path
from road_roi_spatial_common import *
from road_roi_guard_common import fuse

def main():
 assert (ROOT/'fresh_complete.json').exists();out=ROOT/'fresh_ablation';out.mkdir(exist_ok=False)
 from road_adapt_eval_core import evaluate_serial_predictions
 full=read(ROOT/'fresh_evaluation/original_predictions.json');roi=read(ROOT/'fresh_evaluation/unmerged_roi_predictions.json');policy=read(ROOT/'protocol.json')['roi_policy'];rows=[dict(name=r['name'],timeofday=r['timeofday'],label_path=str(ROOT/'fresh/labels'/(Path(r['name']).stem+'.txt'))) for r in full];pred={r['name']:fuse(r['detections'],roi[r['name']],policy) for r in full};m=evaluate_serial_predictions(rows,pred,out,'geometry_without_verifier')
 write(out/'complete.json',dict(status='SAME_COHORT_VERIFIER_ABLATION_COMPLETE_NO_RESELECTION',geometry_only=m,verified=read(ROOT/'fresh_complete.json')['candidate'],policy=policy,model_selection_changed=False,hardware_access=False));print('ROI_VERIFIER_ABLATION_COMPLETE',flush=True)
if __name__=='__main__':main()
