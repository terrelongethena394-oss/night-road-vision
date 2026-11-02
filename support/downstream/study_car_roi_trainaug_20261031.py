"""Augmented-training benefit at matched native ROI verification cost.
This is explicitly RAW inference, not proof enhanced inference is superior.
"""
import gc,time,shutil
from pathlib import Path
import numpy as np
from road_enhanced_detection_common import BASE,read,write,sha,gates
from road_numpy_eval import evaluate
import road_accuracy_common as ac
from pilot_car_roi_verify_20261031 import choose_rois,roi_pixels,refine
ROOT=BASE/'road_car_roi_trainaug_20261031_r1'
TRAIN=BASE/'road_allview_gammafit_20261031_r1'

def main():
    import torch
    assert not ROOT.exists();ROOT.mkdir();(ROOT/'source').mkdir();pilot=BASE/'road_car_roi_verify_20261031_r1';assert read(pilot/'pilot_result.json')['qualified'] is False
    raw_checkpoint=TRAIN/'frozen/raw8/model.pt';candidate=TRAIN/'frozen/enh8/model.pt'
    write(ROOT/'protocol.json',dict(status='FROZEN_BEFORE_FULL480_ROI_TRAIN_AUGMENTATION_EVALUATION',
      hypothesis='Pilot failed enhanced-inference attribution but enhancement-trained ENH8 with RAWverification inputs outperformed matchedRAW8. Test trainingaugmentation plus nativeROIverification, not claim pre-inference enhancement is better.',
      pilot_sha256=sha(pilot/'pilot_result.json'),reuse_scope='64pilotimages are part of reused480, so this full480 is still development only; never independent confirmation.',
      invariants='Same exact choose_rois/roi_pixels/refine functions from frozenpilot;commonCBRAW7 proposals,160x96nativeROI,atmost8,identicalconfidence andgeometry bothverificationroutes. Both takeRAW pixels, same7+Kmainforwards. Mainmodels samearchitecture/init/trainmanifest/8epochs/optimizer/seed;only trainingdarkpixelgamma augmentation differs. No new gradients or parametergrid.',
      models=dict(control=str(raw_checkpoint),control_sha256=sha(raw_checkpoint),candidate=str(candidate),candidate_sha256=sha(candidate)),
      gates='Vs originalRAW7 andmatched RAW8 nativeverification:AP+.5pp,P>=,R+.5pp,FP<=,F1+.5pp. Also report priorRAWflip14 descriptive, differentgeometry/count. Entirestudyrejectedifanyprimarygatefails;no retune.',
      fresh_policy='Only after actualC proof freezeone candidate, newunused240low+64bright excluding allpriornames/groups/hashes. Samegates pluspaired99%APgainCI>0 vsbothprimaryRAWcontrols. ActualC commonCB7 andbothROIexperts,bright originalCB4 bypass. No test-drivenreplacement.',
      deployment_scope='Candidate ifvalidated would be RAWinference with enhancement-trained weights and ROIverification;imageenhancementfordisplay must be separatelylabelled,not as detectioninput. Do not overwrite currentABI29/SD without actualvalidation.',hardware_access=False,sd_written=False))
    for n in [Path(__file__).name,'pilot_car_roi_verify_20261031.py']:shutil.copy2(Path(__file__).with_name(n),ROOT/'source'/n)
    allview=BASE/'road_allview_enhance_20261031_r1';rows=read(allview/'development_manifest.json');assert len(rows)==480;write(ROOT/'development_manifest.json',rows)
    baseline=read(allview/'predictions.json')['raw'];index={r['name']:r for r in baseline};assert [r['name'] for r in rows]==[r['name'] for r in baseline]
    ac.WEIGHTS=raw_checkpoint;det=ac.Detector();records={};locals_all={};counts={};begin=time.monotonic()
    for mode,checkpoint in [('matched_raw',raw_checkpoint),('candidate',candidate)]:
        del det.model;gc.collect();torch.cuda.empty_cache();det.model=torch.load(checkpoint,map_location='cpu',weights_only=False)['model'].float().fuse().eval().cuda();rr=[];local=[];nn=0
        for at,r in enumerate(rows):
            b=index[r['name']];sensor,_=ac.sensor400(Path(r['data_root'])/'images'/r['name']);rois=choose_rois(b['detections']);images=[roi_pixels(sensor,v) for v in rois];pp=det.run(images) if images else [];nn+=len(images);a=refine(b['detections'],rois,pp)
            rr.append(dict(name=r['name'],ground_truth=b['ground_truth'],detections=a.tolist()));local.append(dict(name=r['name'],rois=rois,detections=pp))
            if (at+1)%80==0:print('CAR_ROI_FULL480',mode,at+1,480,round(time.monotonic()-begin),flush=True)
        records[mode]=rr;locals_all[mode]=local;counts[mode]=nn;print('CAR_ROI_FULL480_SCORE',mode,evaluate(rr)['classes']['car'],flush=True)
    scores={mode:evaluate(rr)['classes']['car'] for mode,rr in records.items()};scores['baseline']=evaluate(baseline)['classes']['car'];gg={key:gates(scores[key],scores['candidate']) for key in ['baseline','matched_raw']};qualified=all(all(v.values()) for v in gg.values())
    write(ROOT/'predictions.json',records);write(ROOT/'local_predictions.json',locals_all);result=dict(status='TRAIN_AUG_ROI_REQUIRES_ACTUAL_C_AND_UNUSED_CONFIRMATION' if qualified else 'TRAIN_AUG_ROI_DEVELOPMENT_REJECTED_KEEP_ABI29',qualified=qualified,scores=scores,gates=gg,verification_forwards=counts,common_proposal_forwards=7*480,main_candidate_sha256=sha(candidate),main_control_sha256=sha(raw_checkpoint),protocol_sha256=sha(ROOT/'protocol.json'),enhancement_at_inference=False,trained_with_dark_gamma=True,new_independent_test_used=False,hardware_access=False,sd_written=False,seconds=time.monotonic()-begin)
    write(ROOT/'selected.json',result);print('CAR_ROI_FULL480_RESULT',result,flush=True)
if __name__=='__main__':main()
