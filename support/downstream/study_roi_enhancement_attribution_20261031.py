"""Finite development-only enhancement ablation with identical RAW proposal ROIs."""
from pathlib import Path
import sys,ast
import gc, time, shutil, threading, concurrent.futures as cf
import numpy as np
import cv2
from road_enhanced_detection_common import BASE,read,write,sha,gates
import road_accuracy_common as ac
from road_numpy_eval import evaluate
from pilot_car_roi_verify_20261031 import choose_rois,roi_pixels,refine
from prove_student_fusion_20261031 import Engine

ROOT=BASE/'road_roi_enhancement_attribution_20261031_r1'
MODELS={b:BASE/f'road_allview_gammafit_20261031_r1/frozen/{b}8/model.pt' for b in ['raw','enh']}
METHODS=['raw','learned10','learned25','learned50','learned100','gamma090','gamma075','offset4','offset8','local_shadow']

def mean_y(a):
    z=a.astype(np.uint64)
    return float((54*z[:,:,0]+183*z[:,:,1]+19*z[:,:,2]).sum())/(256*96000)

def enhance(a,method,bright=None):
    assert a.shape==(240,400,3) and a.dtype==np.uint8
    if method=='raw' or mean_y(a)>48:return a.copy()
    if method.startswith('learned'):
        assert bright is not None
        n=int(method[7:]);return ((a.astype(np.uint32)*(100-n)+bright.astype(np.uint32)*n+50)//100).astype(np.uint8)
    z=a.astype(np.float32);v=z.max(2)/255
    fade=1-np.clip((v-.65)/.33,0,1)
    if method.startswith('gamma'):
        exponent=int(method[5:])/100
        g=np.divide(v**exponent,v,out=np.ones_like(v),where=v>1e-8)
        return np.floor(np.clip(z*(1+(np.minimum(g,3)-1)*fade)[:,:,None],0,255)+.5).astype(np.uint8)
    if method.startswith('offset'):
        delta=int(method[6:])*(1-v)*fade
    else:
        assert method=='local_shadow'
        y=(54*z[:,:,0]+183*z[:,:,1]+19*z[:,:,2])/256
        illumination=cv2.blur(y,(11,11),borderType=cv2.BORDER_REFLECT_101)
        # Mild local illumination correction; fixed maximum gain1.5, no sharpening.
        gain=1+.5*(1-np.clip(illumination/80,0,1))*fade
        delta=y*(gain-1)
    delta=np.minimum(delta,254-z.max(2));delta=np.maximum(delta,0)
    return np.floor(np.clip(z+delta[:,:,None],0,255)+.5).astype(np.uint8)

def main():
    import torch
    reuse='--equivalent-runtime' in sys.argv
    if reuse:
        assert (ROOT/'execution_restart_receipt.json').exists() and not (ROOT/'selected.json').exists()
        original=ast.parse((ROOT/'source'/Path(__file__).name).read_text(encoding='utf-8'))
        current=ast.parse(Path(__file__).read_text(encoding='utf-8'))
        for name in ['mean_y','enhance']:
            find=lambda tree:next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name==name)
            assert ast.dump(find(original),include_attributes=False)==ast.dump(find(current),include_attributes=False),name
    else:
        assert not ROOT.exists();ROOT.mkdir();(ROOT/'source').mkdir()
    prior=BASE/'road_allview_enhance_20261031_r1'
    rows=read(prior/'development_manifest.json');assert len(rows)==480
    base=read(prior/'predictions.json')['raw'];assert [r['name'] for r in rows]==[r['name'] for r in base]
    protocol=dict(status='FROZEN_BEFORE_NEW_ROI_ENHANCEMENT_PREDICTIONS',
      objective='Test causal effect of enhancing ONLY ROIverification inputs. Fullscene RAW7 proposalstage unchanged. This is not full-image enhanced-input detection.',
      scope='480 already exposed development images only. Previous304confirmation images never accessed. No inference on new images unless a candidate meets all frozen development gates.',
      methods=METHODS,method_source_sha256=sha(__file__),
      transforms='OwnROIrawmeanY>48 exactidentity. Learned mixtures10/25/50/100percent actual ABI29 C fusion. Gamma.90/.75 maxRGB huepreserving cap3 highlightfade.65..98. Offset4/8 additive delta=c*(1-maxRGB/255)*fade,headroom254. Localshadow delta=Y*.5*(1-clip(11x11meanY/80))*fade,headroom254. No image IDs/labels used by enhancement.',
      invariants='Exact same frozen commonCBRAW7 proposals,160x96nativeROI,choose_rois/roi_pixels/refine. Same ROI origins,count,networkarchitecture,NMS.6/conf.25,max300,andfixedweightswithin each raw/enh comparison. All routes7+Kforwards,K<=8. No confidence or box tuning.',
      models={b:dict(path=str(p),sha256=sha(p)) for b,p in MODELS.items()},
      selection='Run each of2fixed existing8epoch models with each of10methods. HighestAP candidate passingallgates, one candidate frozen beforeanynewtest. Finite19nontrivialcomparisons; all resultsreported includingfailures. Raw8ROI control, samecandidateweightsRAWROI attribution, originalCBsameROI control, andoriginalRAW7 all retained. No new gradients.',
      gates='Vs strongest rawROIcontrol among raw8/enh8/originalCB:AP+.5pp,P>=,R+.5pp,FP<=,F1+.5pp; vs samecandidateweights RAWROI:AP+.2pp,TP>=,FP<=. Vs oldRAW7 same strict gates.',
      fresh='Only if development qualifies, actualC enhancement/pixel andmodelpostproof, then newunused240night+64day excluding all prior groups/names/hashes including previous304. Primary comparebestRAWROI andsameweightsRAWROI with paired2000-groupbootstrap99%APgainCI>0 andsamepointgates. Freeze once; no test-driven new candidate. Otherwise report no proof, preservecurrentboard andSD.',
      hardware_access=False,sd_written=False)
    if not reuse:
        write(ROOT/'protocol.json',protocol)
        shutil.copy2(__file__,ROOT/'source'/Path(__file__).name);write(ROOT/'development_manifest.json',rows)
    else:
        frozen=read(ROOT/'protocol.json');assert frozen['methods']==METHODS and frozen['models']==protocol['models']
        assert read(ROOT/'development_manifest.json')==rows
        shutil.copy2(__file__,ROOT/'source'/'equivalent_execution.py')
    begin=time.monotonic();ac.WEIGHTS=MODELS['raw'];det=ac.Detector();params=threading.local();cv2.setNumThreads(1)
    records={};results={};forwards={}
    if reuse:
        from fast_roi_attribution_runtime_20261031 import audit
        from validate_roi_delivery_board import close_boxes
        fast,audit_result=audit();test_inputs=[]
        for r,b in zip(rows[:4],base[:4]):
            sensor,_=ac.sensor400(Path(r['data_root'])/'images'/r['name'])
            test_inputs.extend(roi_pixels(sensor,x) for x in choose_rois(b['detections']))
        assert len(test_inputs)>=8
        test_inputs=(test_inputs*4)[:24]
        old=[]
        for at in range(0,len(test_inputs),8):old.extend(det.run(test_inputs[at:at+8]))
        for a in test_inputs:assert np.array_equal(ac.preprocess400(a),fast(a))
        ac.preprocess400=fast
        new=det.run(test_inputs);errors=[]
        for a,b in zip(old,new):
            a=np.asarray(a,np.float32).reshape(-1,6);b=np.asarray(b,np.float32).reshape(-1,6)
            errors.append(close_boxes(a[a[:,4]>=.01],b[b[:,4]>=.01],permutation=True))
        write(ROOT/'execution_equivalence.json',dict(status='PIXEL_BYTE_EXACT_AND_GPU_BATCHING_OUTPUT_AUDITED',preprocess=audit_result,actual_development_rois=len(test_inputs),post_errors=errors,models_methods_roi_gates_selection_unchanged=True,hardware_access=False))
    def prepare(item):
        r,b=item
        if not hasattr(params,'engine'):params.engine=Engine()
        sensor,_=ac.sensor400(Path(r['data_root'])/'images'/r['name']);rois=choose_rois(b['detections']);images=[roi_pixels(sensor,x) for x in rois]
        bright=[params.engine.run(a) if mean_y(a)<=48 else a.copy() for a in images]
        return rois,images,bright
    for branch,ck in MODELS.items():
        del det.model;gc.collect();torch.cuda.empty_cache();det.model=torch.load(ck,map_location='cpu',weights_only=False)['model'].float().fuse().eval().cuda()
        branch_rows={m:[] for m in METHODS};nn=0
        with cf.ThreadPoolExecutor(4) as pool:
            for start in range(0,480,4):
                chunk=list(zip(rows[start:start+4],base[start:start+4]));prepared=list(pool.map(prepare,chunk))
                for (r,b),(rois,images,bright) in zip(chunk,prepared):
                    if reuse:
                        flat=[enhance(a,method,c) for method in METHODS for a,c in zip(images,bright)]
                        all_pred=[]
                        for at in range(0,len(flat),24):all_pred.extend(det.run(flat[at:at+24]))
                        nn+=len(flat)
                    for mi,method in enumerate(METHODS):
                        if reuse:
                            pp=all_pred[mi*len(images):(mi+1)*len(images)]
                        else:
                            inp=[enhance(a,method,c) for a,c in zip(images,bright)]
                            pp=det.run(inp) if inp else [];nn+=len(inp)
                        pred=refine(b['detections'],rois,pp)
                        branch_rows[method].append(dict(name=r['name'],ground_truth=b['ground_truth'],detections=pred.tolist()))
                if (start+len(chunk))%40==0:
                    write(ROOT/'progress.json',dict(branch=branch,done=start+len(chunk),total=480,seconds=time.monotonic()-begin,hardware_access=False))
                    print('ROI_ENHANCEMENT_DEV',branch,start+len(chunk),480,round(time.monotonic()-begin),flush=True)
        records[branch]=branch_rows;results[branch]={m:evaluate(v)['classes']['car'] for m,v in branch_rows.items()};forwards[branch]=nn
        write(ROOT/f'{branch}_predictions.json',branch_rows);write(ROOT/'scores_progress.json',results)
        print('ROI_ENHANCEMENT_BRANCH_SCORES',branch,results[branch],flush=True)
    cb=read(BASE/'road_car_roi_delivery_20261031_r1/c_proof/complete.json')['scores']['initial']
    raw_controls={'raw8':results['raw']['raw'],'enh8_same_raw':results['enh']['raw'],'originalCB':cb}
    strongest=max(raw_controls,key=lambda k:raw_controls[k]['ap50']);baseline=evaluate(base)['classes']['car'];candidates=[]
    for branch in MODELS:
        for m in METHODS[1:]:
            value=results[branch][m];same=results[branch]['raw']
            gg=dict(strongest_rawROI=gates(raw_controls[strongest],value),old_raw7=gates(baseline,value),same_weights_rawROI=dict(ap=value['ap50']>=same['ap50']+.002,tp=value['tp']>=same['tp'],fp=value['fp']<=same['fp']))
            candidates.append(dict(branch=branch,method=m,score=value,gates=gg,qualified=all(all(g.values()) for g in gg.values())))
    good=[c for c in candidates if c['qualified']];chosen=max(good,key=lambda c:c['score']['ap50']) if good else None
    result=dict(status='ROI_ENHANCEMENT_REQUIRES_C_AND_UNUSED_CONFIRMATION' if chosen else 'NO_ROI_ENHANCEMENT_PROOF_KEEP_CURRENT_BOARD',qualified=bool(chosen),chosen=chosen,
                scores=results,raw_controls=raw_controls,strongest_raw_control=strongest,baseline=baseline,candidates=candidates,verification_forwards=forwards,
                reused_development_images=480,new_independent_test_used=False,weights_unchanged=True,hardware_access=False,sd_written=False,seconds=time.monotonic()-begin,protocol_sha256=sha(ROOT/'protocol.json'))
    write(ROOT/'selected.json',result);print('ROI_ENHANCEMENT_DEVELOPMENT_RESULT',result,flush=True)

if __name__=='__main__':main()
