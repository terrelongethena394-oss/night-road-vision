"""Fixed detector;compare spatial task enhancement to RAW and uniform controls."""
import shutil,threading,concurrent.futures as cf,time
import numpy as np
from road_task_gate_common import *
from road_enhanced_detection_common import gates
from road_retinex_project import illumination
from prove_student_fusion_20261031 import Engine
from evaluate_matched_enhanced_detectors_20261031 import post
from road_numpy_eval import evaluate
import road_accuracy_common as ac

def main():
    import torch
    assert (ROOT/'training_complete.json').exists() and not (ROOT/'selected.json').exists()
    out=ROOT/'development';out.mkdir();(out/'examples').mkdir();shutil.copy2(__file__,ROOT/'source'/Path(__file__).name)
    prior=BASE/'road_enhanced_detection_20261031_r1';helpers=read(prior/'helper_cache.json');manifest={r['name']:r for r in read(prior/'development_manifest.json')}
    params=read(BASE/'road_car_balanced_20261030_r1/selected.json')['chosen']['source'];local=threading.local();begin=time.monotonic()
    def prepare(h):
        if not hasattr(local,'engine'):local.engine=Engine()
        r=manifest[h['name']];_,a=ac.sensor400(Path(r['data_root'])/'images'/r['name']);return a,local.engine.run(a),illumination(a)
    with cf.ThreadPoolExecutor(4) as pool:cache=list(pool.map(prepare,helpers))
    print('TASK_GATE_DEV_PIXELS_READY',len(cache),round(time.monotonic()-begin),flush=True)
    ac.WEIGHTS=INITIAL;det=ac.Detector();models={}
    for epoch in [4,8,12]:
        folder=ROOT/'frozen'/f'epoch{epoch}';meta=read(folder/'frozen.json');assert sha(folder/'model.pt')==meta['sha256']
        net=make_model().cuda().eval();net.load_state_dict(torch.load(folder/'model.pt',map_location='cpu',weights_only=True));models['gate'+str(epoch)]=net
    names=['raw','uniform2','uniform7','uniform11','uniform20',*models];records={name:[] for name in names};global_predictions={name:[] for name in names};mask_means={name:[] for name in models}
    for at,(h,(a,b,f)) in enumerate(zip(helpers,cache)):
        v=a.astype(np.uint32);z=b.astype(np.uint32);images={'raw':a,**{'uniform'+str(k):((v*(20-k)+z*k+10)//20).astype(np.uint8) for k in [2,7,11,20]}}
        x=torch.from_numpy(a.transpose(2,0,1).copy()).cuda().float()[None]/255;y=torch.from_numpy(b.transpose(2,0,1).copy()).cuda().float()[None]/255;ff=torch.from_numpy(f.copy()).cuda()[None,None]
        with torch.inference_mode():
            for name,model in models.items():
                image,mask=model(x,y,ff);images[name]=np.floor(image[0].permute(1,2,0).cpu().numpy()*255+.5).astype(np.uint8);mask_means[name].append(float(mask.mean()))
        predictions=det.run(list(images.values()))
        for name,p in zip(images,predictions):
            pred=post(p,h,params);records[name].append(dict(name=h['name'],ground_truth=h['ground_truth'],detections=pred.tolist()));global_predictions[name].append(dict(name=h['name'],detections=p))
        if (at+1)%80==0:print('TASK_GATE_DEVELOPMENT',at+1,len(helpers),round(time.monotonic()-begin),flush=True)
    scores={name:evaluate(rows)['classes']['car'] for name,rows in records.items()}
    accepted=read(prior/'selected.json')['accepted_baseline'];raw_control=read(prior/'selected.json')['raw_control']['scores']['raw']
    rows=[]
    for name in names[1:]:
        gg=dict(accepted_raw7=gates(accepted,scores[name]),matched_raw7=gates(raw_control,scores[name]),same_run_raw=gates(scores['raw'],scores[name]))
        rows.append(dict(name=name,score=scores[name],gates=gg,qualified=all(all(v.values()) for v in gg.values()),mean_mask=float(np.mean(mask_means[name])) if name in mask_means else int(name.replace('uniform',''))/20))
    good=[r for r in rows if r['qualified']];chosen=max(good,key=lambda r:(r['score']['ap50'],r['name'].startswith('uniform'))) if good else None
    write(out/'predictions.json',records);write(out/'global_predictions.json',global_predictions)
    selected=dict(status='TASK_ENHANCED_DETECTION_REQUIRES_C_AND_UNUSED_CONFIRMATION' if chosen else 'NO_TASK_GATE_CANDIDATE_PASSED_KEEP_ABI29',qualified=bool(chosen),chosen=chosen,scores=scores,candidates=rows,accepted_baseline=accepted,matched_raw_control=raw_control,
        protocol_sha256=sha(ROOT/'protocol.json'),prior_study_sha256=sha(prior/'selected.json'),new_independent_test_used=False,hardware_access=False,sd_written=False)
    write(ROOT/'selected.json',selected)
    print('TASK_GATE_SELECTION',selected,flush=True)
if __name__=='__main__':main()
