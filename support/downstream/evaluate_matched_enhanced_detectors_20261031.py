"""Select using reused640 only;matched RAWcontrol before ENHselection."""
import gc,shutil,time
import numpy as np
from PIL import Image
from road_enhanced_detection_common import *
import road_accuracy_common as ac
from road_numpy_eval import evaluate
from evaluate_car_boxrefine import fuse_refined

def post(global_pred,helper,params):
    p=ac.fuse(global_pred,[np.asarray(v,np.float32).reshape(-1,6) for v in helper['tiles_mapped']],.75);p=p[p[:,5]==1]
    return fuse_refined(p,helper['zoom_mapped'],helper['refiner_outputs'],params['strength'],params['cap'],params['class_gate'])

def main():
    import torch
    assert (ROOT/'training_complete.json').exists() and not (ROOT/'selected.json').exists()
    shutil.copy2(__file__,ROOT/'source'/Path(__file__).name);out=ROOT/'development';out.mkdir()
    helpers=read(ROOT/'helper_cache.json');assert len(helpers)==480
    assert sha(ROOT/'helper_cache.json')==read(ROOT/'helper_cache_proof.json')['cache_sha256']
    manifests={r['name']:r for r in read(ROOT/'development_manifest.json')};params=read(BASE/'road_car_balanced_20261030_r1/selected.json')['chosen']['source']
    baseline=[dict(name=h['name'],ground_truth=h['ground_truth'],detections=h['baseline_accepted']) for h in helpers]
    base=evaluate(baseline)['classes']['car'];write(out/'accepted_raw7_baseline.json',dict(scores=base,predictions=baseline))
    pads={};begin=time.monotonic()
    for h in helpers:
        r=manifests[h['name']];_,a=ac.sensor400(Path(r['data_root'])/'images'/r['name']);assert r['enhanced_global'] is not None
        pads[r['name']]=(ac.preprocess400(a),np.asarray(Image.open(r['enhanced_global']['image']).convert('RGB')))
    ac.WEIGHTS=INITIAL;det=ac.Detector();allrecords=[]
    def assess(branch,epoch):
        folder=ROOT/'frozen'/f'{branch}{epoch}';meta=read(folder/'frozen.json');assert sha(folder/'model.pt')==meta['sha256']
        del det.model;gc.collect();torch.cuda.empty_cache()
        det.model=torch.load(folder/'model.pt',map_location='cpu',weights_only=False)['model'].float().fuse().eval().cuda()
        records={'raw':[],'enh':[]};global_rows={'raw':[],'enh':[]}
        for at in range(0,len(helpers),8):
            hh=helpers[at:at+8];stack=np.stack([im.transpose(2,0,1) for h in hh for im in pads[h['name']]])
            x=torch.from_numpy(np.ascontiguousarray(stack)).cuda().float()/255
            with torch.inference_mode():pp=det.nms(det.model(x)[0],.001,.6,max_det=300)
            for j,h in enumerate(hh):
                for mode,p in zip(['raw','enh'],pp[2*j:2*j+2]):
                    a=p.cpu().numpy();a[:,[0,2]]=np.clip(a[:,[0,2]]/.8,0,400);a[:,[1,3]]=np.clip((a[:,[1,3]]-64)/.8,0,240)
                    fused=post(a,h,params);entry=dict(name=h['name'],ground_truth=h['ground_truth'],detections=fused.tolist())
                    records[mode].append(entry);global_rows[mode].append(dict(name=h['name'],detections=a.tolist()))
            if (at+len(hh))%120==0:print('MATCHED_DETECTOR_DEVELOPMENT',branch,epoch,at+len(hh),len(helpers),round(time.monotonic()-begin),flush=True)
        scores={mode:evaluate(rows)['classes']['car'] for mode,rows in records.items()}
        cohorts={key:{mode:evaluate([r for r in rows if manifests[r['name']]['development_group']==key])['classes']['car'] for mode,rows in records.items()} for key in ['reused320','reused160']}
        dest=out/f'{branch}{epoch}';dest.mkdir();write(dest/'predictions.json',records);write(dest/'global_predictions.json',global_rows)
        result=dict(branch=branch,epoch=epoch,checkpoint=str(folder/'model.pt'),checkpoint_sha256=meta['sha256'],scores=scores,cohorts=cohorts)
        write(dest/'result.json',result);print('MATCHED_DETECTOR_DEV_RESULT',branch,epoch,scores,flush=True);return result
    raw_records=[assess('raw',e) for e in CHECKPOINTS]
    raw_best=max(raw_records,key=lambda r:r['scores']['raw']['ap50'])
    write(ROOT/'raw_control_selected.json',dict(status='STRONGEST_MATCHED_RAW_CONTROL_FROZEN_BEFORE_ENH_SELECTION',chosen=raw_best,selection='Maximum pooledlow480AP50 amongRAW4/8/12,not chosen to makeENHcomparison easier.',hardware_access=False,sd_written=False))
    records=[]
    for epoch in CHECKPOINTS:
        rec=assess('enh',epoch);m=rec['scores']['enh'];raw_same=rec['scores']['raw']
        gg={'accepted_raw7':gates(base,m),'matched_raw7':gates(raw_best['scores']['raw'],m),
            'same_checkpoint_raw':dict(ap=m['ap50']>=raw_same['ap50']+.002,fp=m['fp']<=raw_same['fp'],tp=m['tp']>=raw_same['tp'])}
        rec.update(gates=gg,qualified=all(all(g.values()) for g in gg.values()));records.append(rec)
        write(ROOT/'selection_progress.json',records);print('ENHANCED_DETECTION_DEV_GATES',epoch,rec['qualified'],gg,flush=True)
    good=[r for r in records if r['qualified']];chosen=max(good,key=lambda r:r['scores']['enh']['ap50']) if good else None
    selected=dict(status='ONE_ENHANCED_DETECTOR_REQUIRES_ACTUAL_C_AND_UNUSED_CONFIRMATION' if chosen else 'NO_MATCHED_ENHANCED_DETECTOR_PASSED_KEEP_ABI29',qualified=chosen is not None,chosen=chosen,raw_control=raw_best,accepted_baseline=base,records=records,
        protocol_sha256=sha(ROOT/'protocol.json'),new_independent_test_used=False,hardware_access=False,sd_written=False)
    write(ROOT/'selected.json',selected);print('MATCHED_ENHANCED_SELECTION',selected,flush=True)
if __name__=='__main__':main()
