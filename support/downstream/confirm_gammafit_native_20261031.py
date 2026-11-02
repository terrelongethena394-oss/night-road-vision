"""Frozen unused304 confirmation: actual C allview inputs/networks/postprocessing."""
from pathlib import Path
import os,time,subprocess,shutil,threading,concurrent.futures as cf
import numpy as np
from train_allview_gamma_20261031 import ROOT,SEED
from road_enhanced_detection_common import BASE,INITIAL,read,write,sha,gates,f1
from shadowlift_lab import words,mean_y
from prove_car_zoom_c import ZoomC
from confirm_car_zoom_native import BaseFusion
from study_car_zoom_20261030 import XS
import allview_enhance_native as native
import road_accuracy_common as ac
from road_numpy_eval import evaluate
from confirm_road_viewadapt import statistics,car_ap50

def main():
    selection=read(ROOT/'selected.json');proof=read(ROOT/'c_proof/complete.json');assert selection['qualified'] and proof['qualified'] and proof['selection_sha256']==sha(ROOT/'selected.json')
    out=ROOT/'confirmation';assert not (out/'fresh_result.json').exists();data=out/'fresh';manifest=read(data/'manifest.json');assert len(manifest)==304 and sum(r['cohort']=='low' for r in manifest)==240
    ledger=read(out/'holdout_exclusions.json');assert not {r['group'] for r in manifest}&set(ledger['groups']) and not {r['image_sha256'] for r in manifest}&set(ledger['image_hashes'])
    for r in manifest:
        assert sha(data/'images'/r['name'])==r['image_sha256'] and sha(data/'labels'/(Path(r['name']).stem+'.txt'))==r['label_sha256']
    weights=dict(accepted=INITIAL.parent/'weights.f32',matched=ROOT/'export/raw_control/weights.f32',attribution=ROOT/'export/enhanced/weights.f32',enhanced=ROOT/'export/enhanced/weights.f32')
    for kind,p in weights.items():assert sha(p)==read(p.parent/'complete.json')['weights_sha256']
    exe=BASE/'road_local_enhance_20261029_r2/host/road_ap.exe';assert sha(exe)==read(exe.parent/'build.json')['exe_sha256']
    policy=dict(status='FROZEN_BEFORE_UNUSED304_ACTUAL_C_INFERENCE',selection_sha256=sha(ROOT/'selected.json'),c_proof_sha256=sha(ROOT/'c_proof/complete.json'),manifest_sha256=sha(data/'manifest.json'),weights_sha256={k:sha(p) for k,p in weights.items()},protocol_sha256=sha(out/'protocol.json'),bootstrap_seed=SEED+11,bootstrap_replicates=2000,no_test_driven_reselection=True,hardware_access=False,sd_written=False)
    if (out/'inference_policy.json').exists():assert read(out/'inference_policy.json')==policy
    else:write(out/'inference_policy.json',policy)
    native.ROOT=ROOT;local=threading.local();scratch=out/'native_scratch';scratch.mkdir(exist_ok=True);env=dict(os.environ);env['PATH']='E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin;'+env['PATH'];begin=time.monotonic();views={};receipts=[]
    def one(job):
        at,r,kind,v=job
        if not hasattr(local,'zoom'):local.zoom=ZoomC();local.enhance=native.Engine()
        sensor,full=ac.sensor400(data/'images'/r['name'])
        if v==0:a=full
        elif v<4:x,y=ac.TILES[v-1];a=sensor[y:y+240,x:x+400].copy()
        else:a=local.zoom.image(sensor,XS[v-4],152)
        if kind=='enhanced':a=local.enhance.run(a)
        folder=scratch/f'{kind}_{v}_{at}';folder.mkdir();ip=folder/'input.u32';words(a).tofile(ip)
        p=subprocess.run([str(exe),str(weights[kind]),str(ip),str(folder)],capture_output=True,text=True,env=env,timeout=90);assert p.returncode==0 and 'ROAD_FP32_HOST_DONE' in p.stdout,p.stderr
        b=np.fromfile(folder/'boxes400.f32','<f4').reshape(-1,6);assert np.isfinite(b).all();record=dict(name=r['name'],detections=b.tolist());receipt=dict(name=r['name'],condition=kind,view=v,input_sha256=sha(ip),decoded_sha256=sha(folder/'decoded.f32'),boxes_sha256=sha(folder/'boxes400.f32'))
        for f in folder.iterdir():assert f.resolve().is_relative_to(scratch.resolve()) and f.is_file();f.unlink()
        folder.rmdir();return record,receipt
    for kind in weights:
        for v in range(7):
            rows=[r for r in manifest if r['cohort']=='low' or (kind=='accepted' and v<4)]
            cache=out/f'{kind}_view{v}_actual_c.json';rc=out/f'{kind}_view{v}_receipts.json'
            if cache.exists():records=read(cache);receipts.extend(read(rc))
            else:
                records=[];evidence=[]
                with cf.ThreadPoolExecutor(4) as pool:
                    for i,(record,receipt) in enumerate(pool.map(one,[(j,r,kind,v) for j,r in enumerate(rows)]),1):
                        records.append(record);evidence.append(receipt)
                        if i%80==0:print('GAMMAFIT_FRESH_ACTUAL_C',kind,v,i,len(rows),round(time.monotonic()-begin),flush=True)
                write(cache,records);write(rc,evidence);receipts.extend(evidence)
            assert [r['name'] for r in records]==[r['name'] for r in rows];views[kind,v]={r['name']:r['detections'] for r in records}
    post=native.Post();base=BaseFusion();predictions={k:[] for k in weights};refiner_calls=0
    for at,r in enumerate(manifest):
        name=r['name'];sensor,full=ac.sensor400(data/'images'/name);assert (mean_y(full)<=48)==(r['cohort']=='low')
        gt=ac.truth(data/'labels'/(Path(name).stem+'.txt'));gt=gt[gt[:,0]==1]
        if r['cohort']=='low':
            for kind in weights:
                b,calls=post.run([views[kind,v][name] for v in range(7)],sensor,prove_numpy=True);refiner_calls+=calls;predictions[kind].append(dict(name=name,ground_truth=gt.tolist(),detections=b.tolist()))
        else:
            b=base.run(views['accepted',0][name],[views['accepted',v][name] for v in range(1,4)],.75);b=b[b[:,5]==1]
            assert native.Engine().run(full).tobytes()==full.tobytes()
            for kind in weights:predictions[kind].append(dict(name=name,ground_truth=gt.tolist(),detections=b.tolist()))
        if (at+1)%60==0:print('GAMMAFIT_FRESH_C_POST',at+1,304,flush=True)
    low_names={r['name'] for r in manifest if r['cohort']=='low'};splits={co:{k:[r for r in rr if (r['name'] in low_names)==(co=='low')] for k,rr in predictions.items()} for co in ['low','brighter']}
    scores={co:{k:evaluate(rr)['classes']['car'] for k,rr in groups.items()} for co,groups in splits.items()};m=scores['low']['enhanced'];gg={k:gates(scores['low'][k],m) for k in ['accepted','matched']};same=scores['low']['attribution'];gg['attribution']=dict(ap=m['ap50']>=same['ap50']+.002,tp=m['tp']>=same['tp'],fp=m['fp']<=same['fp'])
    stats={k:statistics(rr) for k,rr in splits['low'].items()};ids=np.arange(240)
    for kind in weights:assert abs(car_ap50(stats[kind],ids)-scores['low'][kind]['ap50'])<1e-12
    rng=np.random.default_rng(policy['bootstrap_seed']);gain={k:[] for k in ['accepted','matched']}
    for _ in range(policy['bootstrap_replicates']):
        draw=rng.integers(0,240,240);a=car_ap50(stats['enhanced'],draw)
        for k in gain:gain[k].append(a-car_ap50(stats[k],draw))
    ci={k:np.quantile(v,[.005,.995]).tolist() for k,v in gain.items()}
    for k in ci:gg[k]['ap_gain_ci99_positive']=ci[k][0]>0
    bright=[splits['brighter'][k] for k in weights];assert all(r==bright[0] for r in bright)
    accepted=all(all(v.values()) for v in gg.values())
    for kind,rr in predictions.items():write(out/(kind+'_predictions.json'),rr)
    write(out/'receipts.json',receipts)
    result=dict(status='GAMMAFIT_UNUSED304_ACTUAL_C_ACCEPTED' if accepted else 'GAMMAFIT_UNUSED304_ACTUAL_C_REJECTED_KEEP_ABI29',accepted=accepted,scores=scores,gates=gg,car_ap50_difference_interval99=ci,brighter_outputs_byte_exact=True,actual_c_detector_forwards=len(receipts),actual_c_refiner_calls=refiner_calls,selection_sha256=sha(ROOT/'selected.json'),inference_policy_sha256=sha(out/'inference_policy.json'),no_test_driven_reselection=True,seconds=time.monotonic()-begin,hardware_access=False,sd_written=False)
    write(out/'fresh_result.json',result);shutil.copy2(__file__,ROOT/'source'/Path(__file__).name);print('GAMMAFIT_FRESH_RESULT',result,flush=True)
if __name__=='__main__':main()
