"""Counterfactual task labels on original training split; frozen ENH8 detector."""
import hashlib,shutil,time
from pathlib import Path
import numpy as np
from road_task_router_common import *
import road_accuracy_common as ac
from allview_enhance_native import Post
from prove_car_zoom_c import ZoomC
from study_car_zoom_20261030 import XS
from road_numpy_eval import evaluate
def main():
    import torch
    assert not ROOT.exists();ROOT.mkdir();(ROOT/'source').mkdir();train=BASE/'road_allview_gammafit_20261031_r1';assert read(train/'selected.json')['qualified'] is False
    assert sha(MAIN)==read(MAIN.with_name('frozen.json'))['sha256']
    write(ROOT/'protocol.json',dict(status='TASK_ROUTER_FROZEN_BEFORE_TRAIN_COUNTERFACTUALS_AND_ROUTER_GRADIENTS',seed=SEED,main_checkpoint=str(MAIN),main_checkpoint_sha256=sha(MAIN),
      architecture='1155parameter68->16ReLU/dropout.2->3classMLP. Features32blockmeanY+32blockvarianceY+globalRminusG,BminusG,gradientmean,blackfraction. Standardize using FITsources only. No input filename, detection predictions, GT or imageID at runtime.',
      training='Original1060dark TRAIN sources only. Prefixgroup hash80%fit/20%internal validation. Frozen ENH8 main, identical7views/refiner RAW and gamma0.8. Target beneficial if deltaTP-deltaFP>0 anddeltaTP>=0;harmful ifutility<0 ordeltaTP<0;neutral otherwise. No newsource or testlabels.',
      optimization='80epochs,batch64,AdamW.001cosine.0001,weightdecay.05,balanced sqrt-inverse-frequency CE,clip5,no imageaugment. Checkpoints20/40/80. Internalvalidation diagnostic only.',
      inference='One MLP decision from full400RAW only; choose entire7view RAW or gamma0.8 withsame frozen ENH8 model. Crop ownmean>48 bypassunchanged. Bright overall>48 originalCB4RAW exactidentity. Same7forwards ascontrols; no extra detector or class changes.',
      development='Alreadyexposed480low, checkpoints and six scorethresholds0/.1/.2/.3/.4/.5 where score=Pbeneficial-Pharmful. HighestAPpassingcandidate. Runtime decision never uses development labels. Oracle diagnosis explicitly nondeployable and never a modelresult.',
      gates='Vs acceptedCBRAW7 AND strongest matchedRAW8:AP+.5pp,P>=,R+.5pp,FP<=,F1+.5pp. Samecheckpoint ENH8-RAW7 attribution:AP+.2pp,TP>=,FP<=. No detector threshold change.',
      fresh_policy='One frozen choice only afteractualCproof. New unused240low+64bright excluding allpriorgroups/hashes. AllactualC, samegates andpaired99%APgainCI>0 vsboth RAWcontrols. No holdout-driven reselection.',hardware_access=False,sd_written=False))
    for n in [Path(__file__).name,'road_task_router_common.py']:shutil.copy2(Path(__file__).with_name(n),ROOT/'source'/n)
    # Nondeployable oracle is a diagnostic headroom check, not a proposed algorithm.
    devpred=read(train/'development/enh8/predictions.json');oracle=[]
    for a,b in zip(devpred['raw'],devpred['enh']):
        ca,cb=counts(a),counts(b);delta=cb-ca;on=delta[0]>=0 and delta[0]-delta[1]>0;oracle.append(b if on else a)
    write(ROOT/'oracle_diagnostic_NOT_DEPLOYABLE.json',dict(status='GT_DEPENDENT_ORACLE_NOT_MODEL_NOT_DEPLOYABLE',scores=evaluate(oracle)['classes']['car']))
    rows=[r for r in read(BASE/'road_enhanced_detection_20261031_r1/training_manifest.json') if r['mean_raw']<=48];assert len(rows)==1060
    for r in rows:r['router_split']='fit' if int(hashlib.sha256((str(SEED)+r['group']).encode()).hexdigest()[:8],16)<.8*2**32 else 'internal'
    assert not {r['group'] for r in rows if r['router_split']=='fit'}&{r['group'] for r in rows if r['router_split']=='internal'}
    write(ROOT/'training_manifest.json',rows);del devpred,oracle
    torch.cuda.set_per_process_memory_fraction(.18);ac.WEIGHTS=MAIN;det=ac.Detector();pixels=ZoomC();post=Post();outcomes=[];feat=[];start=time.monotonic()
    for at,r in enumerate(rows):
        image=BASE/'road_detection_20261026/dataset/images/train'/r['name'];assert sha(image)==r['image_sha256'];sensor,full=ac.sensor400(image);vv=[full]+[sensor[y:y+240,x:x+400].copy() for x,y in ac.TILES]+[pixels.image(sensor,x,152) for x in XS];ee=[]
        for a in vv:
            z=a.astype(np.uint64);mean=float((54*z[:,:,0]+183*z[:,:,1]+19*z[:,:,2]).sum())/(256*96000);ee.append(ac.gamma(a,'gamma080') if mean<=48 else a)
        pp=det.run(vv+ee);gt=ac.truth(image.parent.parent.parent/'labels/train'/(image.stem+'.txt'));gt=gt[gt[:,0]==1];cc=[];receipts=[]
        for mode,j in [('raw',0),('enh',7)]:
            boxes,_=post.run(pp[j:j+7],sensor);rec=dict(ground_truth=gt.tolist(),detections=boxes.tolist());cc.append(counts(rec));receipts.append(hashlib.sha256(b''.join(np.asarray(p,np.float32).tobytes() for p in pp[j:j+7])).hexdigest())
        delta=cc[1]-cc[0];label=2 if delta[0]>=0 and delta[0]-delta[1]>0 else 0 if delta[0]<0 or delta[0]-delta[1]<0 else 1
        feat.append(features(full));outcomes.append(dict(name=r['name'],group=r['group'],split=r['router_split'],raw_counts=cc[0].tolist(),enhanced_counts=cc[1].tolist(),label=label,view_predictions_sha256=receipts))
        if (at+1)%100==0:print('TASK_ROUTER_TRAIN_COUNTERFACTUALS',at+1,1060,round(time.monotonic()-start),flush=True);write(ROOT/'preparation_progress.json',dict(done=at+1,total=1060,seconds=time.monotonic()-start))
    np.asarray(feat,np.float32).tofile(ROOT/'features.f32');write(ROOT/'training_outcomes.json',outcomes);write(ROOT/'prepared.json',dict(status='ORIGINAL_TRAIN_ONLY_COUNTERFACTUALS_READY',images=1060,features_sha256=sha(ROOT/'features.f32'),outcomes_sha256=sha(ROOT/'training_outcomes.json'),main_sha256=sha(MAIN),seconds=time.monotonic()-start,hardware_access=False,sd_written=False));print('TASK_ROUTER_DATA_COMPLETE',flush=True)
if __name__=='__main__':main()
