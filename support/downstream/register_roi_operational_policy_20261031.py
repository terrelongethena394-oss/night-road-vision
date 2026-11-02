"""Use operational output agreement, retaining both failed raw-activation rules."""
import shutil
from car_roi_delivery_common import *
def main():
    out=ROOT/'c_proof';d=read(out/'float_diagnostic_v2/diagnostic.json');assert not (ROOT/'confirmation').exists() and not (out/'complete.json').exists();assert d['post_nms']['classes_equal'] and d['post_nms']['max_coords_abs']<.005 and d['post_nms']['max_score_abs']<.00002
    shutil.copy2(ROOT/'source/prove_car_roi_delivery_20261031.py',out/'source/numerical_attempt2.py')
    write(out/'numerical_policy_v3.json',dict(status='OPERATIONAL_OUTPUT_POLICY_FROZEN_BEFORE_UNUSED_DATA',
      reason='Raw decoded center/width tolerance is not stable across different FP32 accumulation schedules. Two FP64/CPU/GPUdiagnoses show subpixel rounding,withsamefinalclasses/countsand<=.00156pixelboxdifferences. Keepv1/v2failures;do notcallthempassed. EvaluateobservableoutputsusingpostNMSlimitsalreadyregisteredinv2,notnewlargerboxlimits.',
      preserves_original_failed_rules=True,v2_policy_sha256=sha(out/'numerical_policy_v2.json'),v2_failure_sha256=sha(out/'numeric_failure_v2.json'),second_diagnostic_sha256=sha(out/'float_diagnostic_v2/diagnostic.json'),
      raw_coordinates_and_sizes='Diagnostic only; all values and prior failure flags retained.',probability_max_abs=.00002,whole_decode_mean_abs=.00002,post_nms_min_score=.01,post_nms_coord_max=.005,post_nms_score_max=.00002,post_nms_count_and_classes_exact=True,
      accuracy_gates_unchanged=True,all_unused_accuracy_inference_actual_C_required=True,no_model_or_detector_threshold_changes=True,hardware_access=False,sd_written=False))
    print('OPERATIONAL_NUMERIC_POLICY_REGISTERED_BEFORE_UNUSED_DATA',flush=True)
if __name__=='__main__':main()
