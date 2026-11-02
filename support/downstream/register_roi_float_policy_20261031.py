"""Diagnosed numerical amendment BEFORE unseen data; never alters accuracy gates."""
import shutil
from car_roi_delivery_common import *
def main():
    out=ROOT/'c_proof';diagnostic=read(out/'float_diagnostic/diagnostic.json');assert diagnostic['maximum']<.003 and diagnostic['post_nms']['max_coords_abs']<.005 and diagnostic['post_nms']['max_score_abs']<.00002
    assert not (ROOT/'confirmation').exists() and not (out/'complete.json').exists()
    shutil.copy2(ROOT/'source/prove_car_roi_delivery_20261031.py',out/'source/strict_attempt1.py')
    write(out/'original_probe_failure.json',dict(status='ORIGINAL_ABSOLUTE_DECODE_RULE_FAILED_PRESERVED',source_name='a2a359fb-14f1d903.jpg',view='base6',model='originalCB',max_abs_from_original_batch8=.0020599365,mean_abs_from_original_batch8=4.676678e-6,original_max_limit=.001,original_mean_limit=.00002,diagnosis_sha256=sha(out/'float_diagnostic/diagnostic.json'),accuracy_gates_unchanged=True))
    policy=dict(status='NUMERICAL_POLICY_V2_REGISTERED_BEFORE_UNUSED_DATA',reason='FP32 scalar CPU and GPU accumulation produce different box widths at ~1.6e-5relative;FP64probe confirms rounding,notweightlayouterror. Originalabsolutecriterion remainsrecordedasfailed. Neverchangecandidateweights/thresholds/accuracygates.',
      reference_diagnostic_sha256=sha(out/'float_diagnostic/diagnostic.json'),center_max_abs=.001,wh_atol=.0001,wh_rtol=.00002,probability_max_abs=.00002,whole_decode_mean_abs=.00002,
      additional_output_check='PostNMS predictionsscore>=.01 matchedbijectively,C/GPU classesexact,coordinatesmax.005at400proxy,scoremax.00002. Lower-scoreAPtailsremainverifiedbyfullyactualCunusedconfirmation.',
      source_implementation_unchanged=True,accuracy_gates_unchanged=True,unused_images_downloaded=False,hardware_access=False,sd_written=False)
    write(out/'numerical_policy_v2.json',policy);print('ROI_NUMERIC_AMENDMENT_RECORDED_ORIGINAL_FAILURE_PRESERVED',flush=True)
if __name__=='__main__':main()
