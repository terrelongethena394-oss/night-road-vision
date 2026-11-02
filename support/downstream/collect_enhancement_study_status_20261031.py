from road_enhanced_detection_common import BASE,read,write,sha
from study_roi_enhancement_attribution_20261031 import ROOT
def main():
    summaries=[]
    for name in ['road_enhanced_detection_20261031_r1','road_task_gate_20261031_r1','road_allview_enhance_20261031_r1','road_allview_gammafit_20261031_r1','road_car_roi_verify_20261031_r1']:
        folder=BASE/name;p=folder/('pilot_result.json' if name=='road_car_roi_verify_20261031_r1' else 'selected.json')
        if not p.exists():continue
        d=read(p);r=dict(study=name,status=d.get('status'),qualified=d.get('qualified'),result_sha256=sha(p),result_path=str(p),independent_test=False)
        summaries.append(r)
    write(ROOT/'prior_study_scope.json',dict(status='PRIOR_DEVELOPMENT_RESULTS_INDEX_ONLY',studies=summaries,no_new_predictions=True,hardware_access=False))
    print(summaries,flush=True)
if __name__=='__main__':main()
