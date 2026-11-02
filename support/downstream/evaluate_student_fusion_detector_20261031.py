"""Diagnostic only:why display and RAW detector remain separate."""
import sys,time
from pathlib import Path
import numpy as np
import road_accuracy_common as ac
from road_numpy_eval import evaluate
from road_retinex_student_common import BASE,read,write,sha
from prove_student_fusion_20261031 import Engine,ROOT

def main():
    assert not (ROOT/'detector_diagnostic.json').exists()
    write(ROOT/'detector_diagnostic_protocol.json',dict(status='EXPOSED80_FIXED_MODEL_SINGLE_VIEW_DIAGNOSTIC',
      purpose='Measure effect of sending display enhancement to unchanged detector;actual board route remains RAW regardless of result. No new independent gain claim or fresh-data selection.',
      model_sha256=sha(BASE/'road_viewadapt_20261030_r1/export/model.pt'),hardware_access=False,sd_written=False))
    ac.WEIGHTS=BASE/'road_viewadapt_20261030_r1/export/model.pt';det=ac.Detector();engine=Engine()
    rows=read(BASE/'road_paper_predenoise_20261031_r1/predictions.json')['raw'];data=BASE/'road_brightness_route_20261030_r1/fresh';records={m:[] for m in ['raw','enhanced']};begin=time.monotonic()
    for i,r in enumerate(rows):
        _,a=ac.sensor400(data/'images'/r['name']);z=engine.run(a)
        for name,p in zip(records,det.run([a,z])):
            p=np.asarray(p,np.float32).reshape(-1,6);p=p[p[:,5]==1]
            records[name].append(dict(name=r['name'],cohort=r['cohort'],ground_truth=r['ground_truth'],detections=p.tolist()))
        if r['cohort']=='brighter':assert np.array_equal(a,z) and records['raw'][-1]['detections']==records['enhanced'][-1]['detections']
        if (i+1)%16==0:print('FUSION_DETECTOR_DIAGNOSTIC',i+1,80,round(time.monotonic()-begin),flush=True)
    scores={c:{m:evaluate([r for r in rr if r['cohort']==c])['classes']['car'] for m,rr in records.items()} for c in ['low','brighter']}
    write(ROOT/'detector_diagnostic_predictions.json',records)
    write(ROOT/'detector_diagnostic.json',dict(status='RAW_DETECTION_ROUTE_RETAINED',scores=scores,images=80,not_independent=True,single_view_only=True,enhanced_detector_deployed=False,hardware_access=False,sd_written=False))
    print('FUSION_DETECTOR_DIAGNOSTIC_COMPLETE',scores,flush=True)
if __name__=='__main__':main()
