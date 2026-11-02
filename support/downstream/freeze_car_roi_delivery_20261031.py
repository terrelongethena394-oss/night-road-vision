"""Separate RAW-inference delivery hypothesis; preserve all rejected ENH studies."""
from pathlib import Path
import shutil
from car_roi_delivery_common import *
def main():
    assert not ROOT.exists();ROOT.mkdir();(ROOT/'source').mkdir();s=read(STUDY/'selected.json');assert not s['qualified'];initial=read(STUDY/'initial_control_result.json');m=s['scores']['matched_raw'];gg=dict(stable_raw7=gates(s['scores']['baseline'],m),same_roi_initial=gates(initial['scores'],m));assert all(all(v.values()) for v in gg.values());assert sha(CHECKPOINT)==s['main_control_sha256']
    write(ROOT/'protocol.json',dict(status='RAW_ROI_DELIVERY_FROZEN_BEFORE_C_AND_UNUSED_TEST',seed=SEED,scope='RAWinference ROIverification, imageenhancementdisplayseparate. NOT claim enhanced-input detection or augmentationtraining advantage.',
      candidate_checkpoint=str(CHECKPOINT),candidate_checkpoint_sha256=sha(CHECKPOINT),proposal_checkpoint=str(INITIAL),proposal_checkpoint_sha256=sha(INITIAL),
      algorithm='Unchanged frozenpilot ROIselection/160x96resize/refinement:common originalCBRAW7 proposals,score[.15,.65),height[3,20),width>=4,atmost8uniqueorigins,RAWpixels,RAW8verificationmodel;scoregeomean,ROIboxreplacementif>=.25,unmatchedoldscorehalved,finalNMS.6/max300. Brightoverallmean>48 stays original4RAWviews,noROIs.',
      development='Exposed480/4308carGT;pilot64included. Candidate chosenasRAWcontrolfromrejectedENHstudy by highestAP among nativeROI variants passingcurrentstrictgates. No fresh labels/predictions used.',
      gates='Against stableRAW7 andinitialCBweightswithIDENTICALnativeROIgeometry/count:AP+.5pp,P>=,R+.5pp,FP<=,F1+.5pp. Conf.25,IoU.5fixed. No further checkpoint/threshold/ROI tuning.',
      c_policy='Cplan andpost vsfrozenNumPy all480,sourcecanaries;nativeROIpixelsalreadybyteexact16synthetics. Fixed24devsourcesbyhash for actualCPU-C networks vsGPU exactsameinput,max.001mean.00002. Not all480actualCaccuracy. NewconfirmationmustentirelyactualC.',
      fresh_policy='One frozen candidate,newunused240night meanY<=48 plus64day meanY>=70,exclude all recordedprefixgroups/names/exacthashes. Samegates vsbothRAWcontrols andpaired2000-imagebootstrap99%APgainCI lower>0 vsboth;brightoutputsbyteexact. ActualCproposal+bothverificationweights+post. No test-driven replacement. RejectretainABI29 onanyfailure.',
      board_policy='Only afterindependentconfirmation,JTAG/RAMvalidation,SD/Flashuntouched;currentABI29restorable.',hardware_access=False,sd_written=False))
    selection=dict(status='RAW_ROI_DEVELOPMENT_QUALIFIED_REQUIRES_C_AND_UNUSED_CONFIRMATION',qualified=True,scores=dict(candidate=m,baseline=s['scores']['baseline'],same_roi_initial=initial['scores']),gates=gg,checkpoint_sha256=sha(CHECKPOINT),source_study_sha256=sha(STUDY/'selected.json'),initial_control_sha256=sha(STUDY/'initial_control_result.json'),protocol_sha256=sha(ROOT/'protocol.json'),enhancement_at_detection_inference=False,hardware_access=False,sd_written=False)
    write(ROOT/'selected.json',selection);shutil.copy2(STUDY/'development_manifest.json',ROOT/'development_manifest.json')
    for n in [Path(__file__).name,'car_roi_delivery_common.py','road_car_roi_verify.c','road_native_car_roi.c','pilot_car_roi_verify_20261031.py']:shutil.copy2(Path(__file__).with_name(n),ROOT/'source'/n)
    import prepare_viewadapt_exclusions as ex
    ex.ROOT=ROOT;ex.SEED=SEED;ex.main();ledger=read(ROOT/'holdout_exclusions.json');known=read(ROOT/'development_manifest.json')+read(BASE/'road_car_balanced_20261030_r1/confirmation/fresh/manifest.json');assert {r['group'] for r in known}<=set(ledger['groups']) and {r['image_sha256'] for r in known}<=set(ledger['image_hashes'])
    print('RAW_ROI_DELIVERY_FROZEN',selection['scores'],flush=True)
if __name__=='__main__':main()
