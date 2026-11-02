"""All7views enhanced equally;originalmodel/geometry/thresholds/refiner frozen."""
from pathlib import Path
import shutil,threading,concurrent.futures as cf,time
import numpy as np
import road_accuracy_common as ac
from road_numpy_eval import evaluate
from road_retinex_project import paper_reference,illumination
from road_task_gate_common import make_model
from prove_student_fusion_20261031 import Engine
from prove_car_zoom_c import ZoomC
from prove_balanced_car_c import RefinerC
from study_car_zoom_20261030 import map_zoom,XS
from evaluate_car_boxrefine import eligible,fuse_refined
from road_enhanced_detection_common import BASE,INITIAL,read,write,sha,gates
ROOT=BASE/'road_allview_enhance_20261031_r1'

def finish(pred,sensor,params,refiner):
    a=ac.fuse(pred[0],[ac.map_tile(pred[j+1],*ac.TILES[j]) for j in range(3)],.75);a=a[a[:,5]==1];strong=a[a[:,4]>=.25]
    mapped=[map_zoom(pred[4+j],x,152) for j,x in enumerate(XS)];outputs=[np.zeros((len(p),5),np.float32) for p in mapped];refiner.begin(sensor)
    for j,pp in enumerate(mapped):
        for i,b in enumerate(pp):
            if not eligible(b,strong):continue
            im,meta=refiner.crop(b);outputs[j][i]=refiner.predict(im,meta)
    refiner.end();return fuse_refined(a,mapped,outputs,params['strength'],params['cap'],params['class_gate'])

def main():
    import torch
    assert not ROOT.exists();ROOT.mkdir();(ROOT/'source').mkdir()
    prior=BASE/'road_enhanced_detection_20261031_r1';task=BASE/'road_task_gate_20261031_r1';assert read(task/'selected.json')['qualified'] is False
    methods=['raw','gamma080','gamma065','paper_reference','abi29mix10','task_gate12']
    write(ROOT/'protocol.json',dict(status='ALL7VIEW_ENHANCEMENT_FROZEN_BEFORE_PREDICTIONS',
      reason='Prior enhancements changed only global input while6detail views remainedRAW. Test enhancement in every detectorview with equal7forwards andfrozenmodel.',
      methods=methods,geometry='Same400global+3RAWsensor400crops+3integer280x168to400zoomcrops,y152,x0/260/520. Enhance eachcrop independently only if its ownrawmean<=48;overall scene must be low. Brighteroverall scenes stay original4RAWviews.',
      transformations='gamma080/065:existing maxRGB hue-preservinggamma,cap3,highlightfade.65to.98;paper:float equations2-12,11window,sigma4;ABI29mix10:rational2/20ofactualCbright;taskgate:finalepoch12fixed,not chosen by new outputs.',
      invariants='Originalcbmain model,all7sameviewcounts,IoU.5,conf.25,NMS.6,helperweights.75/.65,refinerfixed. Raw sensor forrefinerunchanged.',
      development='Exposed480lowonly. No newindependent data. Samegates vs acceptedRAW7 andstrongestmatchedtrainedRAWcontrol andsame-runRAW7. HighestAPpassingcandidate;no tuning afterfresh.',
      fresh_policy='Only one candidate afteractualCdevproof;new240low+64bright excluding all prior sources. Samegates andpaired99%APgain positive against both RAWcontrols. No holdout-driven replacement.',
      gates='AP+.5pp,precision no lower,recall+.5pp,FP no higher,F1+.5pp. No threshold tuning.',
      source_prior_failures=dict(matched=sha(prior/'selected.json'),task=sha(task/'selected.json')),hardware_access=False,sd_written=False))
    for n in [Path(__file__).name]:shutil.copy2(Path(__file__).with_name(n),ROOT/'source'/n)
    manifest=read(prior/'development_manifest.json');rows=[r for r in manifest if r['cohort']=='low'];assert len(rows)==480
    write(ROOT/'development_manifest.json',rows)
    local=threading.local();cv2=__import__('cv2');cv2.setNumThreads(1);begin=time.monotonic()
    def prep(r):
        if not hasattr(local,'engine'):local.engine=Engine();local.zoom=ZoomC()
        sensor,full=ac.sensor400(Path(r['data_root'])/'images'/r['name']);views=[full]+[sensor[y:y+240,x:x+400].copy() for x,y in ac.TILES]+[local.zoom.image(sensor,x,152) for x in XS]
        bright=[];ff=[];active=[]
        for a in views:
            z=a.astype(np.uint64);mean=float((54*z[:,:,0]+183*z[:,:,1]+19*z[:,:,2]).mean()/256);on=mean<=48;active.append(on)
            bright.append(local.engine.run(a) if on else a.copy());ff.append(illumination(a) if on else np.zeros((240,400),np.float32))
        return sensor,views,bright,ff,active
    ac.WEIGHTS=INITIAL;det=ac.Detector();gate=make_model().cuda().eval();ck=task/'frozen/epoch12/model.pt';assert sha(ck)==read(ck.with_name('frozen.json'))['sha256'];gate.load_state_dict(torch.load(ck,map_location='cpu',weights_only=True))
    params=read(BASE/'road_car_balanced_20261030_r1/selected.json')['chosen']['source'];refiner=RefinerC();records={m:[] for m in methods};allviews={m:[] for m in methods}
    with cf.ThreadPoolExecutor(4) as pool:
        for start in range(0,len(rows),8):
            chunk=rows[start:start+8];prepared=list(pool.map(prep,chunk))
            for r,(sensor,views,bright,ff,active) in zip(chunk,prepared):
                imgs={m:[] for m in methods}
                for j,(a,b,f,on) in enumerate(zip(views,bright,ff,active)):
                    imgs['raw'].append(a)
                    for m in ['gamma080','gamma065']:imgs[m].append(ac.gamma(a,m) if on else a)
                    imgs['paper_reference'].append(paper_reference(a)[0] if on else a)
                    imgs['abi29mix10'].append(((a.astype(np.uint32)*18+b.astype(np.uint32)*2+10)//20).astype(np.uint8) if on else a)
                    if on:
                        with torch.inference_mode():z,_=gate(torch.from_numpy(a.transpose(2,0,1).copy()).cuda().float()[None]/255,torch.from_numpy(b.transpose(2,0,1).copy()).cuda().float()[None]/255,torch.from_numpy(f.copy()).cuda()[None,None])
                        imgs['task_gate12'].append(np.floor(z[0].permute(1,2,0).cpu().numpy()*255+.5).astype(np.uint8))
                    else:imgs['task_gate12'].append(a)
                pp=det.run([im for m in methods for im in imgs[m]])
                gt=ac.truth(Path(r['data_root'])/'labels'/(Path(r['name']).stem+'.txt'));gt=gt[gt[:,0]==1]
                for mi,m in enumerate(methods):
                    pred=pp[7*mi:7*mi+7];p=finish(pred,sensor,params,refiner)
                    records[m].append(dict(name=r['name'],ground_truth=gt.tolist(),detections=p.tolist()));allviews[m].append(dict(name=r['name'],detections=pred))
            if (start+len(chunk))%80==0:
                print('ALLVIEW_ENHANCED_DEV',start+len(chunk),len(rows),round(time.monotonic()-begin),flush=True)
                write(ROOT/'progress.json',dict(done=start+len(chunk),total=480,seconds=time.monotonic()-begin))
    scores={m:evaluate(rr)['classes']['car'] for m,rr in records.items()};previous=read(prior/'selected.json');base=previous['accepted_baseline'];control=previous['raw_control']['scores']['raw']
    candidates=[]
    for m in methods[1:]:
        gg=dict(accepted_raw7=gates(base,scores[m]),matched_raw7=gates(control,scores[m]),same_run_raw=gates(scores['raw'],scores[m]));candidates.append(dict(method=m,score=scores[m],gates=gg,qualified=all(all(g.values()) for g in gg.values())))
    good=[c for c in candidates if c['qualified']];chosen=max(good,key=lambda c:c['score']['ap50']) if good else None
    write(ROOT/'predictions.json',records);write(ROOT/'view_predictions.json',allviews)
    selection=dict(status='ONE_ALLVIEW_ENHANCED_CANDIDATE_REQUIRES_C_AND_UNUSED_CONFIRMATION' if chosen else 'NO_ALLVIEW_ENHANCEMENT_PASSED_KEEP_ABI29',qualified=bool(chosen),chosen=chosen,scores=scores,candidates=candidates,accepted_baseline=base,matched_raw_control=control,protocol_sha256=sha(ROOT/'protocol.json'),new_independent_test_used=False,seconds=time.monotonic()-begin,hardware_access=False,sd_written=False)
    write(ROOT/'selected.json',selection);print('ALLVIEW_ENHANCED_SELECTION',selection,flush=True)
if __name__=='__main__':main()
