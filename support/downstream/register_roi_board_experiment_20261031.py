"""Authorize engineering validation of a prespecified successful baseline contrast.
Preserve joint study failure: no assertion of extra-training superiority.
"""
from pathlib import Path
from car_roi_delivery_common import *
def main():
    result=read(ROOT/'confirmation/fresh_result.json');assert result['accepted'] is False and all(result['gates']['baseline'].values());assert result['selection_sha256']==sha(ROOT/'selected.json');assert sha(CHECKPOINT)==read(ROOT/'selected.json')['checkpoint_sha256']
    app=ROOT/'board_candidate/firmware';proof=read(app/'arm_complete.json');assert sha(app/'road_detail.elf')==proof['elf_sha256'] and proof['roi_weights_sha256']==sha(ROOT/'export/weights.f32')
    policy=dict(status='BASELINE_CONTRAST_ONLY_FROZEN_ENGINEERING_EXPERIMENT',
      full_study_accepted=False,full_study_failure_preserved=True,extra_training_superiority_established=False,enhanced_input_superiority_established=False,
      rationale='The prespecified candidate-vs-ABI29RAW7 contrast passed EVERY originallyfrozenaccuracygate and99%pairedAPgainCI. The jointstudy rejected additionaltraining superiority vsinitialsameROI. Validatehardware implementation ofEXACTSAMEfrozencandidate asanengineeringexperiment,not relabeljointstudyasaccepted or selectanothermodel.',
      baseline_contrast=result['gates']['baseline'],baseline_ap_gain_ci99=result['car_ap50_difference_interval99']['baseline'],joint_study_sha256=sha(ROOT/'confirmation/fresh_result.json'),
      selected_checkpoint_sha256=sha(CHECKPOINT),runtime_weights_sha256=sha(app/'runtime/roi_weights.f32'),elf_sha256=sha(app/'road_detail.elf'),no_test_driven_reselection=True,
      activity='JTAG/RAM only, physical implementation/readback anddisplay validation. ExistingABI29 restoredifengineeringchecks fail. No SD/Flash writes. No furthermodeltuning onthese304images.',
      board_programmed=False,sd_written=False)
    write(ROOT/'board_candidate/engineering_experiment_policy.json',policy);print('BASELINE_CONTRAST_ONLY_BOARD_EXPERIMENT_REGISTERED',flush=True)
if __name__=='__main__':main()
