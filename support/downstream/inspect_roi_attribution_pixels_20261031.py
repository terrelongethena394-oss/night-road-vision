"""Fixed hash-selected ROI pixel inspection; not accuracy evidence."""
from pathlib import Path
import hashlib
from PIL import Image
from road_enhanced_detection_common import BASE,read,write,sha
import road_accuracy_common as ac
from study_roi_enhancement_attribution_20261031 import ROOT,enhance
from pilot_car_roi_verify_20261031 import choose_rois,roi_pixels
from prove_student_fusion_20261031 import Engine

def main():
    rows=read(ROOT/'development_manifest.json');by={b['name']:b for b in read(BASE/'road_allview_enhance_20261031_r1/predictions.json')['raw']}
    rows=sorted(rows,key=lambda r:hashlib.sha256(('roi_pixel_inspection_20261031|'+r['name']).encode()).hexdigest())
    e=Engine();out=ROOT/'fixed_pixel_inspection';out.mkdir(exist_ok=True);records=[]
    for r in rows:
        rois=choose_rois(by[r['name']]['detections'])
        if not rois:continue
        sensor,_=ac.sensor400(Path(r['data_root'])/'images'/r['name']);a=roi_pixels(sensor,rois[0]);b=e.run(a);i=len(records)
        for method in ['raw','learned10','learned100']:
            Image.fromarray(enhance(a,method,b)).save(out/f'{i}_{method}.png')
        records.append(dict(name=r['name'],roi=rois[0],source_sha256=sha(Path(r['data_root'])/'images'/r['name'])))
        if len(records)==2:break
    write(out/'selection.json',dict(status='HASH_SELECTED_PIXEL_INSPECTION_ONLY',selection='First2 fixedhashordered development sources with at leastone ROI; highestconfidence eligibleROI. No groundtruth or enhancement output used for selection.',images=records,accuracy_evidence=False,hardware_access=False))
    print('ROI_FIXED_PIXEL_INSPECTION_SAVED',out,flush=True)

if __name__=='__main__':main()
