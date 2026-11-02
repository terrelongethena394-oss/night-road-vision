"""Original-training annotations select shared hard examples for BOTH branches."""
import shutil,time
import numpy as np
from PIL import Image
import road_accuracy_common as ac
from road_numpy_eval import correct
from road_enhanced_detection_common import *
def main():
    assert (ROOT/'prepared.json').exists() and not (ROOT/'hard_training_selection.json').exists()
    shutil.copy2(__file__,ROOT/'source'/Path(__file__).name);ac.WEIGHTS=INITIAL;det=ac.Detector();rows=read(ROOT/'training_manifest.json');scores=[];begin=time.monotonic()
    for at in range(0,len(rows),8):
        rr=rows[at:at+8];ims=[]
        for r in rr:
            _,raw=ac.sensor400(BASE/'road_detection_20261026/dataset/images/train'/r['name'])
            if r['enhanced_global']:
                padded=np.asarray(Image.open(r['enhanced_global']['image']));enh=None
                # Detector.run expects400x240;reuse the exact sourceC output
                # stored as detector input to avoid inverse-resize artifacts.
                ims.append((raw,padded))
            else:ims.append((raw,ac.preprocess400(raw)))
        import torch
        t=det.torch;batch=np.stack([x.transpose(2,0,1) for raw,pad in ims for x in [ac.preprocess400(raw),pad]])
        x=t.from_numpy(np.ascontiguousarray(batch)).cuda().float()/255
        with t.inference_mode():pp=det.nms(det.model(x)[0],.001,.6,max_det=300)
        for i,r in enumerate(rr):
            gt=ac.truth(BASE/'road_detection_20261026/dataset/labels/train'/(Path(r['name']).stem+'.txt'));s=[]
            for p in pp[2*i:2*i+2]:
                a=p.cpu().numpy();a[:,[0,2]]=np.clip(a[:,[0,2]]/.8,0,400);a[:,[1,3]]=np.clip((a[:,[1,3]]-64)/.8,0,240);a=a[(a[:,4]>=.25)&(a[:,5]==1)]
                ok=correct(a,gt,np.array([.5],np.float32))[0][:,0];s.append(dict(tp=int(ok.sum()),fp=int((~ok).sum())))
            scores.append(dict(name=r['name'],mean_raw=r['mean_raw'],raw=s[0],enhanced=s[1],rank_tie=__import__('hashlib').sha256((str(SEED)+r['name']).encode()).hexdigest()))
        if (at+len(rr))%240==0:print('ENHANCED_TRAIN_HARDCASE_MINE',at+len(rr),len(rows),round(time.monotonic()-begin),flush=True)
    low=[r for r in scores if r['mean_raw']<=48]
    chosen=sorted(low,key=lambda r:(-(r['enhanced']['fp']-r['raw']['fp']),-r['enhanced']['fp'],r['rank_tie']))[:480];assert len(chosen)==480
    write(ROOT/'train_mining_results.json',scores);write(ROOT/'hard_training_selection.json',dict(status='TRAIN_ONLY_SHARED_HARD_EXAMPLES_FROZEN',chosen=chosen,
      selection='Top480dark TRAIN frames by enhancedFP-rawFP,then enhancedFP,tiehash. Both branches get identicalextra frames with full originalGT.',protocol_sha256=sha(ROOT/'protocol.json'),hardware_access=False,sd_written=False))
    print('ENHANCED_SHARED_HARDCASES_FROZEN',len(chosen),flush=True)
if __name__=='__main__':main()
