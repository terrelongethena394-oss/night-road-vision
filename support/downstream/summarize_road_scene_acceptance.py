from pathlib import Path
from prepare_road_scene_acceptance import LAB
from car_roi_delivery_common import read
for p in sorted(LAB.glob('case*_verified.json')):
    r=read(p);print('CASE',r['case'],r['title'],'GT/TP/FP/FN',r['cars_annotated'],r['tp'],r['fp'],r['fn'],flush=True)
    print('OUTPUT',r['output'],flush=True)
    print('LUMA',round(r['raw_mean_luma'],2),round(r['enhanced_mean_luma'],2),'SHADOW',r['raw_shadow_mean_luma'],r['enhanced_shadow_mean_luma'],flush=True)
    print('GT',r['ground_truth_board400'],'CORRECT',r['prediction_correct'],'MISSED',r['missed_ground_truth_indices'],flush=True)
