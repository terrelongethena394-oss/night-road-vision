"""All actual-C unused304 confirmation of frozen RAW ROI delivery candidate."""
from pathlib import Path
import os,time,subprocess,threading,shutil,hashlib,concurrent.futures as cf
import numpy as np
from car_roi_delivery_common import *
from shadowlift_lab import words,mean_y
from prove_car_zoom_c import ZoomC
from study_car_zoom_20261030 import XS
from allview_enhance_native import Post
from confirm_car_zoom_native import BaseFusion
from road_numpy_eval import evaluate
from confirm_road_viewadapt import statistics,car_ap50
import road_accuracy_common as ac

def main():
    sel=read(ROOT/'selected.json');proof=read(ROOT/'c_proof/complete.json');assert sel['qualified'] and proof['qualified'];out=ROOT/'confirmation';data=out/'fresh';assert not (out/'fresh_result.json').exists();manifest=read(data/'manifest.json');assert len(manifest)==304 and sum(r['cohort']=='low' for r in manifest)==240
    ledger=read(out/'holdout_exclusions.json');assert not {r['group'] for r in manifest}&set(ledger['groups']) and not {r['image_sha256'] for r in manifest}&set(ledger['image_hashes'])
    for r in manifest:assert sha(data/'images'/r['name'])==r['image_sha256'] and sha(data/'labels'/(Path(r['name']).stem+'.txt'))==r['label_sha256']
    weights=dict(initial=INITIAL.parent/'weights.f32',candidate=ROOT/'export/weights.f32')
    for p in weights.values():assert sha(p)==read(p.parent/'complete.json')['weights_sha256']
    exe=BASE/'road_local_enhance_20261029_r2/host/road_ap.exe';assert sha(exe)==read(exe.parent/'build.json')['exe_sha256']
    policy=dict(status='FROZEN_BEFORE_ANY_NEW304_ACTUAL_C_INFERENCE',selection_sha256=sha(ROOT/'selected.json'),c_proof_sha256=sha(ROOT/'c_proof/complete.json'),fresh_protocol_sha256=sha(out/'protocol.json'),manifest_sha256=sha(data/'manifest.json'),weights_sha256={k:sha(p) for k,p in weights.items()},exe_sha256=sha(exe),bootstrap_seed=SEED+3,bootstrap_replicates=2000,no_test_driven_reselection=True,enhancement_at_detection_inference=False,hardware_access=False,sd_written=False)
    if (out/'inference_policy.json').exists():assert read(out/'inference_policy.json')==policy
    else:write(out/'inference_policy.json',policy)
    cache=out/'actual_c_cache';cache.mkdir(exist_ok=True);scratch=out/'actual_c_scratch';scratch.mkdir(exist_ok=True);env=dict(os.environ);env['PATH']='E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin;'+env['PATH'];local=threading.local();lock=threading.Lock();begin=time.monotonic()
    def one(job):
        at,r=job;name=r['name'];saved=cache/(Path(name).stem+'.json')
        if saved.exists():
            d=read(saved);assert d['policy_sha256']==sha(out/'inference_policy.json') and d['image_sha256']==r['image_sha256'];return d
        if not hasattr(local,'native'):
            local.native=Native();local.pixels=Pixels(ROOT/'c_proof/roi_verify.dll');local.zoom=ZoomC();local.post=Post();local.base=BaseFusion()
        sensor,full=ac.sensor400(data/'images'/name);low=mean_y(full)<=48;assert low==(r['cohort']=='low');views=[full]+[sensor[y:y+240,x:x+400].copy() for x,y in ac.TILES]
        if low:views +=[local.zoom.image(sensor,x,152) for x in XS]
        evidence=[]
        def infer(a,kind,tag):
            folder=scratch/f'{at}_{tag}';folder.mkdir();ip=folder/'input.u32';words(a).tofile(ip);p=subprocess.run([str(exe),str(weights[kind]),str(ip),str(folder)],capture_output=True,text=True,env=env,timeout=90)
            assert p.returncode==0 and 'ROAD_FP32_HOST_DONE' in p.stdout,(name,tag,p.stderr)
            boxes=np.fromfile(folder/'boxes400.f32','<f4').reshape(-1,6);assert np.isfinite(boxes).all();evidence.append(dict(view=tag,weights=kind,input_sha256=sha(ip),decoded_sha256=sha(folder/'decoded.f32'),boxes_sha256=sha(folder/'boxes400.f32')))
            for f in folder.iterdir():assert f.resolve().is_relative_to(scratch.resolve()) and f.is_file();f.unlink()
            folder.rmdir();return boxes
        pp=[infer(a,'initial','base'+str(i)) for i,a in enumerate(views)]
        with lock:
            if low:base,refiner_calls=local.post.run(pp,sensor,prove_numpy=True)
            else:
                base=local.base.run(pp[0],pp[1:4],.75);base=base[base[:,5]==1];refiner_calls=0
        if low:
            plan=local.native.plan(base);local.pixels.begin(sensor);images=[local.pixels.image(v) for v in plan];local.pixels.end();verified={}
            for kind in weights:
                boxes=[infer(a,kind,kind+'_roi'+str(i)) for i,a in enumerate(images)]
                with lock:verified[kind]=local.native.refine(base,plan,boxes)
            candidate=verified['candidate'];control=verified['initial']
        else:plan=[];candidate=base.copy();control=base.copy();assert candidate.tobytes()==control.tobytes()==base.tobytes()
        gt=ac.truth(data/'labels'/(Path(name).stem+'.txt'));gt=gt[gt[:,0]==1]
        d=dict(name=name,cohort=r['cohort'],image_sha256=r['image_sha256'],policy_sha256=sha(out/'inference_policy.json'),ground_truth=gt.tolist(),baseline=base.tolist(),same_roi_initial=control.tolist(),candidate=candidate.tolist(),rois=plan,network_forwards=len(evidence),refiner_calls=refiner_calls,receipts=evidence)
        write(saved,d);return d
    results=[]
    with cf.ThreadPoolExecutor(4) as pool:
        for i,d in enumerate(pool.map(one,enumerate(manifest)),1):
            results.append(d)
            if i%16==0:print('RAW_ROI_UNUSED304_ACTUAL_C',i,304,round(time.monotonic()-begin),flush=True);write(out/'inference_progress.json',dict(done=i,total=304,seconds=time.monotonic()-begin))
    predictions={k:[dict(name=r['name'],ground_truth=r['ground_truth'],detections=r[k]) for r in results] for k in ['baseline','same_roi_initial','candidate']};low_names={r['name'] for r in manifest if r['cohort']=='low'};splits={co:{k:[r for r in rr if (r['name'] in low_names)==(co=='low')] for k,rr in predictions.items()} for co in ['low','brighter']};scores={co:{k:evaluate(rr)['classes']['car'] for k,rr in methods.items()} for co,methods in splits.items()}
    checks={k:gates(scores['low'][k],scores['low']['candidate']) for k in ['baseline','same_roi_initial']};stats={k:statistics(rr) for k,rr in splits['low'].items()};ids=np.arange(240)
    for k in predictions:assert abs(car_ap50(stats[k],ids)-scores['low'][k]['ap50'])<1e-12
    rng=np.random.default_rng(policy['bootstrap_seed']);gains={k:[] for k in checks}
    for at in range(policy['bootstrap_replicates']):
        sample=rng.integers(0,240,240);a=car_ap50(stats['candidate'],sample)
        for k in gains:gains[k].append(a-car_ap50(stats[k],sample))
        if (at+1)%500==0:print('RAW_ROI_PAIRED_BOOTSTRAP',at+1,2000,flush=True)
    ci={k:np.quantile(v,[.005,.995]).tolist() for k,v in gains.items()}
    for k in checks:checks[k]['ap_gain_ci99_positive']=ci[k][0]>0
    for k in predictions:assert splits['brighter'][k]==splits['brighter']['baseline']
    accepted=all(all(v.values()) for v in checks.values());receipts=[dict(name=r['name'],**e) for r in results for e in r['receipts']]
    for k,rr in predictions.items():write(out/(k+'_predictions.json'),rr)
    write(out/'receipts.json',receipts);result=dict(status='RAW_ROI_UNUSED304_ACTUAL_C_ACCEPTED' if accepted else 'RAW_ROI_UNUSED304_ACTUAL_C_REJECTED_KEEP_ABI29',accepted=accepted,scores=scores,gates=checks,car_ap50_difference_interval99=ci,bootstrap_replicates=2000,brighter_outputs_byte_exact=True,actual_c_network_forwards=len(receipts),actual_c_refiner_calls=sum(r['refiner_calls'] for r in results),verification_rois=sum(len(r['rois']) for r in results),selection_sha256=sha(ROOT/'selected.json'),manifest_sha256=sha(data/'manifest.json'),inference_policy_sha256=sha(out/'inference_policy.json'),no_test_driven_reselection=True,enhancement_at_detection_inference=False,seconds=time.monotonic()-begin,hardware_access=False,sd_written=False)
    write(out/'fresh_result.json',result);shutil.copy2(__file__,ROOT/'source'/Path(__file__).name);print('RAW_ROI_UNUSED304_RESULT',result,flush=True)
if __name__=='__main__':main()
