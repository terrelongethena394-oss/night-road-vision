"""Check refactored metrics against frozen previous results, plus fusion controls."""
from pathlib import Path
from road_adapt_common import BASE,ROOT,FUSION_POLICIES,read,write
def main():
    from road_adapt_eval_core import evaluate_serial_predictions,supplement_predictions
    folder=ROOT/'metric_regression';folder.mkdir(exist_ok=False)
    rows=[{**r,'label_path':str(BASE/'dataset/labels/test'/(Path(r['name']).stem+'.txt'))} for r in read(BASE/'dataset/manifest.json') if r['split']=='test' and r['status']=='READY']
    previous=read(BASE/'test/raw400_metrics.json');preds={r['name']:r['detections'] for r in read(BASE/'test/raw400_predictions.json')}
    got=evaluate_serial_predictions(rows,preds,folder,'previous_raw400')
    assert abs(got['all']['mAP50']-previous['all']['mAP50'])<1e-12 and abs(got['all']['mAP50_95']-previous['all']['mAP50_95'])<1e-12
    for period in ['night','dawn/dusk','daytime']:
        for name in ['person','car','truck','bus']:
            a=got['by_time'][period]['classes'][name];b=previous['by_time'][period]['classes'][name]
            assert a['tp']==b['tp_at_conf025'] and a['fp']==b['fp_at_conf025'] and a['fn']==b['fn_at_conf025']
    policy=FUSION_POLICIES[0];raw=[[0,0,20,20,.8,0],[80,80,110,110,.4,1]];enh=[[0,0,20,20,.95,0],[40,40,60,70,.8,0]]
    bright=supplement_predictions(raw,enh,policy,60);dark=supplement_predictions(raw,enh,policy,10)
    assert len(bright)==2 and len(dark)==3 and sum(p[0]==0 and p[4]>.79 for p in dark)==1
    assert sum(p[0]==40 and abs(p[4]-.4)<1e-6 for p in dark)==1
    proof=dict(status='REFINED_METRICS_MATCH_FROZEN_480_IMAGE_COUNTS_AND_AP',previous480='Regression parity only, never policy selection.',all_map50=got['all']['mAP50'],all_map50_95=got['all']['mAP50_95'],fusion_highlight_bypass=True,fusion_strong_raw_overlap_exclusion=True,fixture_extra_box_preserved=True,fresh_test_accessed=False)
    write(folder/'complete.json',proof);print('ADAPT_METRIC_AND_FUSION_COMPONENT_PROOF_PASS',proof,flush=True)
if __name__=='__main__':main()
