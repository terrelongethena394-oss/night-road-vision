"""Conservative additional control: initialCB weights, same native ROI verification."""
from pathlib import Path
import time,shutil
import numpy as np
from road_enhanced_detection_common import BASE,INITIAL,read,write,sha,gates
from road_numpy_eval import evaluate
from pilot_car_roi_verify_20261031 import choose_rois,refine
from native_car_roi_20261031 import ROOT,Pixels
import road_accuracy_common as ac
def main():
    assert not (ROOT/'initial_control_result.json').exists();assert (ROOT/'native_pixels/complete.json').exists()
    write(ROOT/'additional_control_protocol.json',dict(status='FROZEN_BEFORE_INITIAL_WEIGHT_ROI_CONTROL_OUTCOMES',hypothesis='Check nativepixel gain without any additionaltraining; prevent mistaking extraROIresolution for augmentationtraininggain.',invariants='Exact same commonCBRAW7 proposals/ROIcenters/budget/resize/refinement;only verification weights initialCB. No changes to candidate or prior gates.',policy='Report this control and require candidate to beat it withsamegates before independent confirmation. Do not change candidate aftercontrol outputs.',initial_weights_sha256=sha(INITIAL),kernel_proof_sha256=sha(ROOT/'native_pixels/complete.json'),hardware_access=False,sd_written=False))
    shutil.copy2(__file__,ROOT/'source'/Path(__file__).name);allview=BASE/'road_allview_enhance_20261031_r1';rows=read(allview/'development_manifest.json');baseline=read(allview/'predictions.json')['raw'];index={r['name']:r for r in baseline};ac.WEIGHTS=INITIAL;det=ac.Detector();engine=Pixels();records=[];local=[];nn=0;begin=time.monotonic()
    for at,r in enumerate(rows):
        b=index[r['name']];sensor,_=ac.sensor400(Path(r['data_root'])/'images'/r['name']);rois=choose_rois(b['detections']);engine.begin(sensor);images=[engine.image(v) for v in rois];engine.end();pp=det.run(images) if images else [];a=refine(b['detections'],rois,pp);nn+=len(images);records.append(dict(name=r['name'],ground_truth=b['ground_truth'],detections=a.tolist()));local.append(dict(name=r['name'],rois=rois,detections=pp))
        if (at+1)%80==0:print('INITIAL_RAW_ROI_CONTROL',at+1,480,round(time.monotonic()-begin),flush=True)
    score=evaluate(records)['classes']['car'];write(ROOT/'initial_control_predictions.json',records);write(ROOT/'initial_control_local.json',local);result=dict(status='INITIAL_RAW_ROI_CONTROL_MEASURED_NOT_CANDIDATE',scores=score,verification_forwards=nn,common_proposal_forwards=7*480,protocol_sha256=sha(ROOT/'additional_control_protocol.json'),seconds=time.monotonic()-begin,hardware_access=False,sd_written=False);write(ROOT/'initial_control_result.json',result);print('INITIAL_RAW_ROI_CONTROL_RESULT',result,flush=True)
if __name__=='__main__':main()
