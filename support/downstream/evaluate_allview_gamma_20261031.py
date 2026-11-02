"""Frozen all-view matched study evaluation on exposed development data only."""
import gc,time,shutil,sys,concurrent.futures as cf
import numpy as np
import road_accuracy_common as ac
from road_numpy_eval import evaluate
from road_enhanced_detection_common import BASE,INITIAL,read,write,sha,gates
from train_allview_gamma_20261031 import ROOT,CHECKPOINTS
from study_allview_enhancement_20261031 import finish
from prove_car_zoom_c import ZoomC
from prove_balanced_car_c import RefinerC
from study_car_zoom_20261030 import XS
from pathlib import Path

def main():
    import torch
    streaming='--stream' in sys.argv
    if not streaming and (ROOT/'streaming_evaluation_active.flag').exists():
        start_wait=time.monotonic()
        while not (ROOT/'selected.json').exists():
            assert time.monotonic()-start_wait<1800,'Streaming evaluator did not finish; retain ABI29.'
            time.sleep(10)
    if (ROOT/'selected.json').exists():
        saved=read(ROOT/'selected.json');assert saved['protocol_sha256']==sha(ROOT/'protocol.json')
        print('ALLVIEW_GAMMA_PREVIOUS_COMPLETE',saved['status'],flush=True);return
    assert (ROOT/'training_complete.json').exists() or streaming
    if streaming:torch.cuda.set_per_process_memory_fraction(.18)
    shutil.copy2(__file__,ROOT/'source'/Path(__file__).name)
    prior=read(BASE/'road_allview_enhance_20261031_r1/selected.json');base=prior['scores']['raw']
    rows=[r for r in read(ROOT/'development_manifest.json') if r['cohort']=='low'];assert len(rows)==480
    params=read(BASE/'road_car_balanced_20261030_r1/selected.json')['chosen']['source'];refiner=RefinerC();begin=time.monotonic()
    import threading
    local=threading.local()
    def prep(r):
        if not hasattr(local,'zoom'):local.zoom=ZoomC()
        sensor,full=ac.sensor400(Path(r['data_root'])/'images'/r['name']);views=[full]+[sensor[y:y+240,x:x+400].copy() for x,y in ac.TILES]+[local.zoom.image(sensor,x,152) for x in XS]
        enhanced=[]
        for a in views:
            q=a.astype(np.uint32);on=float(((54*q[:,:,0]+183*q[:,:,1]+19*q[:,:,2])/256).mean())<=48
            enhanced.append(ac.gamma(a,'gamma080') if on else a)
        gt=ac.truth(Path(r['data_root'])/'labels'/(Path(r['name']).stem+'.txt'));gt=gt[gt[:,0]==1]
        return sensor,views,enhanced,gt
    ac.WEIGHTS=INITIAL;det=ac.Detector();results=[]
    def assess(branch,epoch):
        folder=ROOT/'frozen'/f'{branch}{epoch}'
        while not (folder/'frozen.json').exists():
            assert streaming
            print('ALLVIEW_GAMMA_WAIT_CHECKPOINT',branch,epoch,flush=True);time.sleep(30)
        meta=read(folder/'frozen.json');assert sha(folder/'model.pt')==meta['sha256']
        dest=ROOT/'development'/f'{branch}{epoch}'
        if (dest/'result.json').exists():
            cached=read(dest/'result.json');assert cached['checkpoint_sha256']==meta['sha256'] and (dest/'predictions.json').exists() and (dest/'view_predictions.json').exists();return cached
        del det.model;gc.collect();torch.cuda.empty_cache();det.model=torch.load(folder/'model.pt',map_location='cpu',weights_only=False)['model'].float().fuse().eval().cuda()
        modes=['raw'] if branch=='raw' else ['raw','enh'];records={m:[] for m in modes};vrecords={m:[] for m in modes}
        with cf.ThreadPoolExecutor(4) as pool:
            for start in range(0,len(rows),8):
                chunk=rows[start:start+8];prepared=list(pool.map(prep,chunk))
                for r,(sensor,raw,enh,gt) in zip(chunk,prepared):
                    pp=det.run(raw if branch=='raw' else raw+enh)
                    for j,m in enumerate(modes):
                        views=pp[j*7:(j+1)*7];boxes=finish(views,sensor,params,refiner)
                        records[m].append(dict(name=r['name'],ground_truth=gt.tolist(),detections=boxes.tolist()));vrecords[m].append(dict(name=r['name'],detections=views))
                if (start+len(chunk))%120==0:print('ALLVIEW_GAMMA_DEV',branch,epoch,start+len(chunk),480,round(time.monotonic()-begin),flush=True)
        dest.mkdir(parents=True,exist_ok=True);write(dest/'predictions.json',records);write(dest/'view_predictions.json',vrecords)
        score={m:evaluate(v)['classes']['car'] for m,v in records.items()}
        result=dict(branch=branch,epoch=epoch,checkpoint=str(folder/'model.pt'),checkpoint_sha256=meta['sha256'],scores=score)
        write(dest/'result.json',result);print('ALLVIEW_GAMMA_SCORE',branch,epoch,score,flush=True);return result
    controls=[assess('raw',e) for e in CHECKPOINTS];control=max(controls,key=lambda r:r['scores']['raw']['ap50']);write(ROOT/'raw_control_selected.json',dict(chosen=control,selection='Strongest matchedRAW by AP50 before ENHselection.'))
    for e in CHECKPOINTS:
        r=assess('enh',e);m=r['scores']['enh'];same=r['scores']['raw'];gg=dict(accepted_raw7=gates(base,m),matched_raw7=gates(control['scores']['raw'],m),same_checkpoint_raw=dict(ap=m['ap50']>=same['ap50']+.002,tp=m['tp']>=same['tp'],fp=m['fp']<=same['fp']))
        r.update(gates=gg,qualified=all(all(v.values()) for v in gg.values()));results.append(r);write(ROOT/'selection_progress.json',results)
    good=[r for r in results if r['qualified']];chosen=max(good,key=lambda r:r['scores']['enh']['ap50']) if good else None
    selected=dict(status='ONE_MATCHED_ALLVIEW_ENHANCED_DETECTOR_REQUIRES_C_AND_UNUSED_CONFIRMATION' if chosen else 'NO_MATCHED_ALLVIEW_ENHANCED_DETECTOR_PASSED_KEEP_ABI29',qualified=bool(chosen),chosen=chosen,raw_control=control,records=results,accepted_baseline=base,seconds=time.monotonic()-begin,new_independent_test_used=False,hardware_access=False,sd_written=False,protocol_sha256=sha(ROOT/'protocol.json'))
    write(ROOT/'selected.json',selected);print('ALLVIEW_GAMMA_SELECTION',selected,flush=True)
if __name__=='__main__':main()
