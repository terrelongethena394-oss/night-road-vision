from pathlib import Path
import shutil
from car_roi_delivery_common import *
def main():
    proof=read(ROOT/'c_proof/complete.json');assert proof['qualified'] and proof['selection_sha256']==sha(ROOT/'selected.json');assert not (ROOT/'confirmation').exists()
    out=ROOT/'confirmation';out.mkdir();(out/'source').mkdir()
    for n in ['holdout_exclusions.json','holdout_pool.json']:shutil.copy2(ROOT/n,out/n)
    write(out/'protocol.json',dict(status='FROZEN_BEFORE_NEW304_IMAGES',selection_sha256=sha(ROOT/'selected.json'),c_proof_sha256=sha(ROOT/'c_proof/complete.json'),
      fresh_policy=read(ROOT/'protocol.json')['fresh_policy'],raw_inference_only=True,original_absolute_numeric_rule_passed=proof['original_absolute_rule_passed'],numerical_policy_sha256=sha(ROOT/'c_proof/numerical_policy_v3.json'),hardware_access=False,sd_written=False))
    import prepare_viewadapt_holdout as hold
    hold.ROOT=out;hold.RULES=[dict(cohort='low',timeofday='night',images=240,minimum=0,maximum=48),dict(cohort='brighter',timeofday='daytime',images=64,minimum=70,maximum=255)];hold.main()
    shutil.copy2(__file__,ROOT/'source'/Path(__file__).name)
if __name__=='__main__':main()
