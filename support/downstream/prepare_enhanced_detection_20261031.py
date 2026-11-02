"""Freeze matched raw/enhanced detector study and prepare actual deployed pixels."""
import concurrent.futures as cf,threading,shutil,time
import numpy as np,cv2
from PIL import Image
from road_enhanced_detection_common import *
import road_accuracy_common as ac
from prove_student_fusion_20261031 import Engine

def main():
    assert not ROOT.exists();ROOT.mkdir();(ROOT/'source').mkdir();(ROOT/'enhanced_train').mkdir();(ROOT/'enhanced_dev').mkdir();(ROOT/'frozen').mkdir()
    assert sha(ENHANCER)==read(BASE/'road_student_fusion_20261031_r1/complete.json')['dll_sha256']
    training=read(BASE/'road_enhanceadapt_20261030_r1/training_manifest.json');assert len(training)==2400
    development=[]
    for root,key in [(BASE/'road_brightness_route_20261030_r1/fresh','reused320'),(BASE/'road_car_zoom_20261030_r1/confirmation/fresh','reused160')]:
        for r in read(root/'manifest.json'):development.append(dict(r,data_root=str(root),development_group=key))
    assert len(development)==640 and len({r['name'] for r in development})==640
    assert not {r['group'] for r in training}&{r['group'] for r in development}
    assert not {r['image_sha256'] for r in training}&{r['image_sha256'] for r in development}
    write(ROOT/'protocol.json',dict(status='FROZEN_BEFORE_NEW_ENHANCED_DETECTOR_TRAINING',seed=SEED,
      purpose='Improve vehicle detection after enhancement;no visual-brightness substitution for detection accuracy.',
      enhancer='Frozen actual ABI29C display fusion. Only global400 view enhanced when rawmean<=48;6detail views remain originalRAW, identical in all conditions. This is enhancedglobal+RAWdetail assistance,not all inputs enhanced.',
      enhancer_sha256=sha(ENHANCER),initial_sha256=sha(INITIAL),
      training='Original2400 annotated train sources only. Matched RAW control vs ENH global detector;identical original images/labels/initial weights/optimizer/epochs/random draws. Both use same480extra hard-example global draws per epoch,selected on TRAIN ONLY by ENHfalsepositive excess under originalGT. All GT retained;no empty pseudolabels.',
      optimization='12epochs each,FP32,batch32,AdamW1e-4 cosine1e-5wd1e-4,BNstatistics updated,anchors unchanged,flip.5only. EMAweights with current branch BNbuffers. Checkpoints4/8/12. Detection graph unchanged. Helpers always originalcb model,6sameRAWviews;refiner unchanged.',
      development='Explicitly reused640(480low+160brighter);all selection developmental. Choose strongestRAWcontrol checkpoint by pooledlowAP50,then ENHcheckpoint must pass gates vs that control AND acceptedABI29RAW7. SameENHcheckpoint RAWglobal is an additional attribution control.',
      gates='Vs BOTH acceptedRAW7 and matched-trainedRAW7:AP>=+.5pp,precision no lower,recall>=+.5pp,FP no higher,F1>=+.5pp. SameENHcheckpoint RAWglobal comparison:AP>=+.2pp,FP no higher,TP no lower. Brighter route exact original model unchanged.',
      selection='Highest pooledlowAP50 among passing ENHcheckpoints;freeze one before new holdout. No threshold or ROI geometry search;confidence.25,IoU.5,NMS.6,all existing helperweights/post unchanged.',
      fresh_policy='Only after one passes development and actualC development proof:unused240low+64brighter,exclude all recorded training/development/confirmation/screenedprefixgroups and exact hashes,including prior304. Frozen candidate and RAWcontrols;all gates plus paired99%APgain interval lower>0 against acceptedRAW7 and matched-trainedRAW7. No holdout-driven reselection.',
      previous_failure='Previous6epochlowLR50%enhancedglobal BNfrozen experiment failed and remains failed. This matches actualnewenhancer,updates BN,and has matchedRAWtraining +trainhardexamples.',
      board_policy='Preserve actualABI29/SD. Only deploy a candidate with independent confirmation;report missingproof/failures honestly.',hardware_access=False,sd_written=False))
    for n in [Path(__file__).name,'road_enhanced_detection_common.py']:shutil.copy2(Path(__file__).with_name(n),ROOT/'source'/n)
    write(ROOT/'development_manifest.json',development)
    local=threading.local();begin=time.monotonic();cv2.setNumThreads(1)
    def one(item):
        r,split=item
        if not hasattr(local,'engine'):local.engine=Engine()
        ip=BASE/'road_detection_20261026/dataset/images/train'/r['name'] if split=='train' else Path(r['data_root'])/'images'/r['name']
        assert sha(ip)==r['image_sha256'];_,full=ac.sensor400(ip);mean=ac.read if False else float((full.astype(np.float64)*np.array([54,183,19])).sum()/(256*96000))
        dest=ROOT/('enhanced_train' if split=='train' else 'enhanced_dev')/(Path(r['name']).stem+'.png')
        if mean<=48:
            z=local.engine.run(full);im=ac.preprocess400(z);Image.fromarray(im).save(dest,compress_level=1)
            enhanced=dict(image=str(dest),sha256=sha(dest))
        else:enhanced=None
        return dict(r,enhanced_global=enhanced,mean_raw=mean)
    for split,rows in [('train',training),('dev',development)]:
        result=[]
        with cf.ThreadPoolExecutor(4) as pool:
            for i,r in enumerate(pool.map(one,[(r,split) for r in rows]),1):
                result.append(r)
                if i%160==0:print('ENHANCED_DETECTION_PREP',split,i,len(rows),round(time.monotonic()-begin),flush=True)
        write(ROOT/('training_manifest.json' if split=='train' else 'development_manifest.json'),result)
    write(ROOT/'prepared.json',dict(status='ACTUAL_C_ENHANCED_GLOBAL_PIXELS_PREPARED',train=2400,development=640,
      train_manifest_sha256=sha(ROOT/'training_manifest.json'),development_manifest_sha256=sha(ROOT/'development_manifest.json'),seconds=time.monotonic()-begin,hardware_access=False,sd_written=False))
    print('ENHANCED_DETECTION_PREPARED',flush=True)
if __name__=='__main__':main()
