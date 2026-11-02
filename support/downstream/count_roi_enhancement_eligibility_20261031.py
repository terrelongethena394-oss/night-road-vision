"""Count actual brightness-eligible crops with byteexact native ROI pixels."""
from pathlib import Path
from road_enhanced_detection_common import BASE,read,write
import road_accuracy_common as ac
from study_roi_enhancement_attribution_20261031 import ROOT,mean_y
from pilot_car_roi_verify_20261031 import choose_rois
from native_car_roi_20261031 import Pixels
def main():
    rows=read(ROOT/'development_manifest.json');base=read(BASE/'road_allview_enhance_20261031_r1/predictions.json')['raw'];engine=Pixels(BASE/'road_car_roi_delivery_20261031_r1/c_proof/roi_verify.dll');details=[]
    for r,b in zip(rows,base):
        sensor,_=ac.sensor400(Path(r['data_root'])/'images'/r['name']);engine.begin(sensor)
        for v in choose_rois(b['detections']):
            mean=mean_y(engine.image(v));details.append(dict(name=r['name'],index=v['index'],mean_y=mean,enhancement_eligible=mean<=48))
        engine.end()
    write(ROOT/'roi_eligibility.json',dict(status='BRIGHTNESS_GUARD_DIAGNOSTIC_ONLY',rois=len(details),eligible=sum(d['enhancement_eligible'] for d in details),unchanged_bright=sum(not d['enhancement_eligible'] for d in details),details=details,new_images_used=False,hardware_access=False))
    print('ROI_INPUT_BRIGHTNESS_COUNTS',len(details),sum(d['enhancement_eligible'] for d in details),flush=True)
if __name__=='__main__':main()
