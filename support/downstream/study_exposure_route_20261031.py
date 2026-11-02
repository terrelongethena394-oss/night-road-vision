"""Small exposed-development exposure-band search; no image-name/GT routing at runtime."""
from pathlib import Path
import time,shutil
import numpy as np
from road_enhanced_detection_common import BASE,read,write,sha,gates,f1
from road_numpy_eval import evaluate
from confirm_road_viewadapt import statistics,car_ap50
import road_accuracy_common as ac
ROOT=BASE/'road_exposure_route_20261031_r1'
def main():
    assert not ROOT.exists();ROOT.mkdir();(ROOT/'source').mkdir();prior=BASE/'road_allview_enhance_20261031_r1'
    methods=['gamma080','gamma065','paper_reference','abi29mix10','task_gate12'];edges=[0,8,16,24,32,40,48]
    write(ROOT/'protocol.json',dict(status='HYPERPARAMETER_GRID_FROZEN_BEFORE_BAND_OUTCOME_INSPECTION',
      purpose='Prior full-cohort results already seen and failed; this is explicitly further development optimization, not independent evidence. Test if fixed exposure bands can avoid scenes harmed by enhancement.',
      methods=methods,edges=edges,rules='One contiguous rawmeanY band with endpoints from edges; enhance all7views using one selectedmethod inside band, RAW7 elsewhere. OverallmeanY>48 retainsoriginal4RAW, method owncropmeanY bypassunchanged. Atleast64 developmentimages routed. Runtime uses only unenhanced meanY; never image names, GT, confidence, outputs or object presence.',
      invariants='Original sameCBmodel, identical7viewcount, detectorconfidence.25,IoU.5,NMS.6,refiner/geometryunchanged. Reuse exact stored predictions, not recomputed models.',
      gates='Against same-runRAW7 and acceptedRAW7 and prior matchedRAWglobalcontrol:AP+.5pp,P>=,R+.5pp,FP<=,F1+.5pp. Choose highestAPpassing. No threshold or route changes afterfresh.',
      fresh_policy='Only after frozen route and actual C proof: new unused240low+64bright, allactualC withsamegates andpaired99%APgainCI>0. No test-driven replacement.',
      source_prediction_sha256=sha(prior/'predictions.json'),hardware_access=False,sd_written=False))
    shutil.copy2(__file__,ROOT/'source'/Path(__file__).name);rows=read(prior/'development_manifest.json');pred=read(prior/'predictions.json');names=[r['name'] for r in rows];means=[];begin=time.monotonic()
    for r in rows:
        _,a=ac.sensor400(Path(r['data_root'])/'images'/r['name']);z=a.astype(np.uint64);means.append(float((54*z[:,:,0]+183*z[:,:,1]+19*z[:,:,2]).sum())/(256*96000))
    means=np.asarray(means);write(ROOT/'raw_exposure_features.json',[dict(name=n,mean_y=float(y)) for n,y in zip(names,means)])
    stats={m:statistics(pred[m]) for m in ['raw']+methods};counts={}
    for m in stats:
        assert [r['name'] for r in pred[m]]==names
        counts[m]=np.asarray([[evaluate([r])['classes']['car'][k] for k in ['tp','fp','fn']] for r in pred[m]])
    base=read(prior/'selected.json')['scores']['raw'];control=read(prior/'selected.json')['matched_raw_control'];assert abs(car_ap50(stats['raw'],np.arange(480))-base['ap50'])<1e-12
    candidates=[]
    for method in methods:
        for i,lo in enumerate(edges[:-1]):
            for hi in edges[i+1:]:
                on=(means>lo)&(means<=hi) if lo else (means>=0)&(means<=hi)
                if on.sum()<64:continue
                c=np.where(on[:,None],counts[method],counts['raw']).sum(0);tp,fp,fn=[int(x) for x in c];st=[stats[method if yes else 'raw'][j] for j,yes in enumerate(on)]
                m=dict(objects=tp+fn,ap50=car_ap50(st,np.arange(480)),tp=tp,fp=fp,fn=fn,precision=tp/(tp+fp),recall=tp/(tp+fn))
                gg=dict(accepted_raw7=gates(base,m),matched_raw_global=gates(control,m));qualified=all(all(v.values()) for v in gg.values());candidates.append(dict(method=method,lo=lo,hi=hi,routed_images=int(on.sum()),scores=m,gates=gg,qualified=qualified))
        print('EXPOSURE_ROUTE_SEARCH',method,len(candidates),round(time.monotonic()-begin),flush=True)
    good=[r for r in candidates if r['qualified']];chosen=max(good,key=lambda r:r['scores']['ap50']) if good else None
    if chosen:
        on=(means>chosen['lo'])&(means<=chosen['hi']) if chosen['lo'] else (means>=0)&(means<=chosen['hi']);actual=[pred[chosen['method'] if yes else 'raw'][j] for j,yes in enumerate(on)];full=evaluate(actual)['classes']['car'];assert abs(full['ap50']-chosen['scores']['ap50'])<1e-12;write(ROOT/'chosen_predictions.json',actual);chosen['scores_full']=full
    write(ROOT/'candidates.json',candidates);write(ROOT/'development_manifest.json',rows)
    result=dict(status='EXPOSURE_ROUTE_REQUIRES_C_AND_UNUSED_CONFIRMATION' if chosen else 'NO_EXPOSURE_ROUTE_PASSED_KEEP_ABI29',qualified=bool(chosen),chosen=chosen,baseline=base,matched_raw_control=control,best_descriptive=max(candidates,key=lambda r:r['scores']['ap50']),candidates=len(candidates),seconds=time.monotonic()-begin,new_independent_test_used=False,hardware_access=False,sd_written=False)
    write(ROOT/'selected.json',result);print('EXPOSURE_ROUTE_RESULT',result,flush=True)
if __name__=='__main__':main()
