"""Read-only predictions audit for next-stage work; no training or device writes."""
from pathlib import Path
from collections import Counter
import numpy as np
from road_enhanced_detection_common import BASE,read,write
from road_numpy_eval import correct
from study_dual_exposure_20261031 import Fuser
import road_accuracy_common as ac

def overlap(a,b):
    if not len(b):return np.zeros(0,np.float32)
    area=np.maximum(0,a[2:]-a[:2]).prod();other=np.maximum(0,b[:,2:]-b[:,:2]).prod(1)
    inter=np.maximum(0,np.minimum(a[2:],b[:,2:])-np.maximum(a[:2],b[:,:2])).prod(1)
    return inter/(area+other-inter+1e-7)

def main():
    train=BASE/'road_allview_gammafit_20261031_r1';tta=BASE/'road_gammafit_tta_20261031_r1'
    chosen=read(tta/'selected.json')['best_descriptive'];config=chosen['config']
    source=read(train/'development/enh8/predictions.json');flips={m:read(tta/(tag+'_flipped_predictions.json')) for m,tag in [('raw','attribution'),('enh','enhanced')]}
    manifest={r['name']:r for r in read(tta/'development_manifest.json')};engine=Fuser();summary={};changed=Counter();per_image=[]
    for mode in ['raw','enh']:
        cats=Counter();sizes=Counter();confidence=Counter();tp=fp=fn=0;predictions=[]
        for a,b in zip(source[mode],flips[mode]):
            assert a['name']==b['name'];p=engine.run(a['detections'],b['detections'],config);p=p[p[:,4]>=.25]
            r=manifest[a['name']];gt=ac.truth(Path(r['data_root'])/'labels'/(Path(r['name']).stem+'.txt'));cars=gt[gt[:,0]==1];ok=correct(p,cars,np.array([.5],np.float32))[0][:,0]
            tp+=int(ok.sum());fp+=int((~ok).sum());fn+=len(cars)-int(ok.sum());predictions.append((p,ok,cars))
            for box in p[~ok]:
                iou=overlap(box[:4],cars[:,1:]);best=float(iou.max(initial=0));other=float(overlap(box[:4],gt[gt[:,0]!=1,1:]).max(initial=0))
                category='duplicate_iou_ge50' if best>=.5 else 'near_car_iou10_to50' if best>=.1 else 'other_class_iou_ge30' if other>=.3 else 'background_iou_lt10';cats[category]+=1
                height=box[3]-box[1];sizes['h_lt8' if height<8 else 'h8_to20' if height<20 else 'h_ge20']+=1
                confidence['score25_to35' if box[4]<.35 else 'score35_to50' if box[4]<.5 else 'score_ge50']+=1
        summary[mode]=dict(tp=tp,fp=fp,fn=fn,false_positive_categories=dict(cats),false_positive_sizes=dict(sizes),false_positive_confidence=dict(confidence))
        if mode=='raw':raw_predictions=predictions
        else:
            for name,(p,ok,_),(q,oldok,_) in zip([r['name'] for r in source[mode]],predictions,raw_predictions):
                for box in p[~ok]:
                    ious=overlap(box[:4],q[:,:4]);j=int(ious.argmax()) if len(ious) else -1
                    tag='not_matched_to_raw_at_iou30' if j<0 or ious[j]<.3 else 'matched_raw_true_positive' if oldok[j] else 'matched_raw_false_positive'
                    changed[tag]+=1
                per_image.append(dict(name=name,raw_tp=int(oldok.sum()),enhanced_tp=int(ok.sum()),raw_fp=int((~oldok).sum()),enhanced_fp=int((~ok).sum())))
    assert summary['enh']['tp']==chosen['scores']['tp'] and summary['enh']['fp']==chosen['scores']['fp']
    out=Path(__file__).resolve().parents[2]/'增强识别优化验证_20261031'
    result=dict(status='NEXT_STAGE_DIAGNOSTIC_ONLY',scope='Existing exposed480low. Same ENH8 checkpoint, same14views and identical fusionconfig; RAW/ENH imageinput comparison only. Proximity categories are diagnostic, not proof every nearby box is the correct object.',fusion_config=config,summary=summary,enhanced_fp_previous_raw_status=dict(changed),new_independent_test_used=False,hardware_access=False,sd_written=False)
    write(out/'下一阶段误检诊断.json',result);write(out/'误检逐图记录.json',per_image);print(result)
if __name__=='__main__':main()
