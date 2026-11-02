"""Prespecified small-car ROI verification pilot on64 already-exposed images.
Common RAW7 proposals and identical ROI budget/geometry in all conditions.
No ground truth or image IDs used by proposal/refinement at inference.
"""
import time,hashlib,shutil,gc
from pathlib import Path
import numpy as np
from road_enhanced_detection_common import BASE,read,write,sha,gates
from road_numpy_eval import evaluate
import road_accuracy_common as ac
ROOT=BASE/'road_car_roi_verify_20261031_r1'
TRAIN=BASE/'road_allview_gammafit_20261031_r1'
SEED=2026103181

def overlap(a,b):
    if not len(b):return np.zeros(0,np.float32)
    it=np.maximum(0,np.minimum(a[2:],b[:,2:])-np.maximum(a[:2],b[:,:2])).prod(1)
    return it/(np.maximum(0,a[2:]-a[:2]).prod()+np.maximum(0,b[:,2:]-b[:,:2]).prod(1)-it+1e-7)

def choose_rois(base):
    p=np.asarray(base,np.float32).reshape(-1,6);indices=np.where((p[:,5]==1)&(p[:,4]>=.15)&(p[:,4]<.65)&(p[:,3]-p[:,1]>=3)&(p[:,3]-p[:,1]<20)&(p[:,2]-p[:,0]>=4))[0]
    indices=indices[np.argsort(-p[indices,4],kind='stable')];rois=[];seen=set()
    for i in indices:
        b=p[i];cx=float(b[0]+b[2]);cy=float(b[1]+b[3]);x=int(np.clip(np.floor(cx-80+.5),0,640));y=int(np.clip(np.floor(cy-48+.5),0,384))
        if (x,y) in seen:continue
        seen.add((x,y));rois.append(dict(index=int(i),x=x,y=y,width=160,height=96))
        if len(rois)==8:break
    return rois

def roi_pixels(sensor,r):
    crop=sensor[r['y']:r['y']+96,r['x']:r['x']+160]
    # Exact half-pixel bilinear arithmetic, integer denominators800x480.
    xn=np.clip((2*np.arange(400)+1)*160-400,0,159*800);yn=np.clip((2*np.arange(240)+1)*96-240,0,95*480)
    x,fx=xn//800,xn%800;y,fy=yn//480,yn%480;x1=np.minimum(x+1,159);y1=np.minimum(y+1,95);a=crop.astype(np.uint64)
    z=a[y[:,None],x]*(480-fy)[:,None,None]*(800-fx)[None,:,None]+a[y[:,None],x1]*(480-fy)[:,None,None]*fx[None,:,None]+a[y1[:,None],x]*fy[:,None,None]*(800-fx)[None,:,None]+a[y1[:,None],x1]*fy[:,None,None]*fx[None,:,None]
    return ((z+192000)//384000).astype(np.uint8)

def refine(base,rois,local):
    result=np.asarray(base,np.float32).reshape(-1,6).copy()
    for r,pp in zip(rois,local):
        i=r['index'];original=result[i].copy();p=np.asarray(pp,np.float32).reshape(-1,6).copy();p=p[(p[:,5]==1)&(p[:,0]>1)&(p[:,1]>1)&(p[:,2]<399)&(p[:,3]<239)]
        if len(p):
            p[:,[0,2]]=p[:,[0,2]]*np.float32(.2)+np.float32(r['x']*.5);p[:,[1,3]]=p[:,[1,3]]*np.float32(.2)+np.float32(r['y']*.5)
            valid=overlap(original[:4],p[:,:4])>=.2;p=p[valid]
        if len(p):
            iou=overlap(original[:4],p[:,:4]);j=int(np.argmax(iou*(np.float32(.5)+np.float32(.5)*p[:,4])));chosen=p[j]
            result[i,4]=np.float32(np.sqrt(np.float32(original[4]*chosen[4])))
            if chosen[4]>=.25:result[i,:4]=chosen[:4]
        else:result[i,4]*=np.float32(.5)
    return ac.nms_numpy(result,.6,300)

def main():
    import torch
    assert not ROOT.exists();ROOT.mkdir();(ROOT/'source').mkdir();allview=BASE/'road_allview_enhance_20261031_r1'
    raw_checkpoint=TRAIN/'frozen/raw8/model.pt';enh_checkpoint=TRAIN/'frozen/enh8/model.pt'
    write(ROOT/'protocol.json',dict(status='FROZEN_BEFORE_ROI_PILOT_PREDICTIONS',seed=SEED,
      objective='Fix nearby small-car box errors using more native source detail, not more global brightness. Candidate enhances only verificationROIs; common full/zoom proposalstage stays RAW.',
      geometry='Common frozen acceptedCBRAW7 proposals, car score[.15,.65),height[3,20),width>=4 at400proxy. Descendingproposalconfidence,atmost8 unique croporigins. Raw800source160x96crop centered on proposal,clampedinsideimage;exacthalf-pixelinteger resize400x240. SameROIs andcount allconditions, no labels/imageIDs for runtime decisions.',
      refinement='Only associated carpreds withlocalinterioredges andoriginal-proposalIoU>=.2;choosemaxIoU*(.5+.5score). Verifiedscore=sqrt(oldscore*ROIscore);replacebox onlywhenROIscore>=.25;nomatchhalvesoldscore. FinalsameclassNMS.6/max300. No otherchanges or thresholdsearch.',
      controls='Baseline acceptedRAW7;RAW7+matchedtrainedRAW8ROIverification;RAW7+sameENH8weightsRAWROIverification. CandidateRAW7+ENH8gamma0.8ROIverification, cropownmean>48bypass. Allverificationroutes same7+Kforwards whereK<=8, RAWproposaloverhead included.',
      models=dict(raw=str(raw_checkpoint),raw_sha256=sha(raw_checkpoint),enhanced=str(enh_checkpoint),enhanced_sha256=sha(enh_checkpoint)),
      pilot='64alreadyexposeddevelopment sources chosenbyfixedhash, no image/detection/label filters. Not independent. Only ifsameaccuracygates vsbaseline andmatchedRAW plusattribution pass,promote unchangedalgorithm toall480development. No retune afterpilot;reject iffails.',
      gates='Vsbaseline andmatchedRAW:AP+.5pp,P>=,R+.5pp,FP<=,F1+.5pp. SamedetectorRAW attributionAP+.2pp,TP>=,FP<=.',
      fresh_policy='Only after full480andportableCqualification one frozen candidate seesnewunused240low+64bright,strictsamegates+paired99%APgainCI>0 vsbothRAWcontrols. No test-driven re-selection.',hardware_access=False,sd_written=False))
    shutil.copy2(__file__,ROOT/'source'/Path(__file__).name)
    manifest=read(allview/'development_manifest.json');rows=sorted(manifest,key=lambda r:hashlib.sha256((str(SEED)+r['name']).encode()).hexdigest())[:64];write(ROOT/'pilot_manifest.json',rows)
    names={r['name'] for r in rows};raw=read(allview/'predictions.json')['raw'];base={r['name']:r for r in raw if r['name'] in names};del raw
    prepared=[]
    for r in rows:
        sensor,_=ac.sensor400(Path(r['data_root'])/'images'/r['name']);rois=choose_rois(base[r['name']]['detections']);images=[roi_pixels(sensor,v) for v in rois];prepared.append((r,rois,images))
    ac.WEIGHTS=raw_checkpoint;det=ac.Detector();records={};forwards={};local_predictions={};begin=time.monotonic()
    for mode,checkpoint in [('matched_raw',raw_checkpoint),('same_main_raw',enh_checkpoint),('enhanced',enh_checkpoint)]:
        del det.model;gc.collect();torch.cuda.empty_cache();det.model=torch.load(checkpoint,map_location='cpu',weights_only=False)['model'].float().fuse().eval().cuda();result=[];views=[];nn=0
        for i,(r,rois,images) in enumerate(prepared):
            inputs=[]
            for a in images:
                z=a.astype(np.uint64);mean=float((54*z[:,:,0]+183*z[:,:,1]+19*z[:,:,2]).sum())/(256*96000)
                inputs.append(ac.gamma(a,'gamma080') if mode=='enhanced' and mean<=48 else a)
            pred=det.run(inputs) if inputs else [];nn+=len(inputs);b=base[r['name']];p=refine(b['detections'],rois,pred);result.append(dict(name=r['name'],ground_truth=b['ground_truth'],detections=p.tolist()));views.append(dict(name=r['name'],rois=rois,detections=pred))
            if (i+1)%16==0:print('CAR_ROI_PILOT',mode,i+1,64,round(time.monotonic()-begin),flush=True)
        records[mode]=result;local_predictions[mode]=views;forwards[mode]=nn;print('CAR_ROI_PILOT_BRANCH',mode,evaluate(result)['classes']['car'],flush=True)
    records['baseline']=[base[r['name']] for r in rows];scores={k:evaluate(v)['classes']['car'] for k,v in records.items()};m=scores['enhanced'];same=scores['same_main_raw'];gg=dict(baseline=gates(scores['baseline'],m),matched_raw=gates(scores['matched_raw'],m),same_main_raw=dict(ap=m['ap50']>=same['ap50']+.002,tp=m['tp']>=same['tp'],fp=m['fp']<=same['fp']));accepted=all(all(v.values()) for v in gg.values())
    write(ROOT/'pilot_predictions.json',records);write(ROOT/'pilot_local_predictions.json',local_predictions);result=dict(status='ROI_PILOT_PASSED_REQUIRES_UNCHANGED_FULL480' if accepted else 'ROI_PILOT_REJECTED_KEEP_ABI29',qualified=accepted,scores=scores,gates=gg,verification_forwards=forwards,common_proposal_forwards=7*64,scope='64alreadyexposeddevelopmentONLY',new_independent_test_used=False,hardware_access=False,sd_written=False,seconds=time.monotonic()-begin);write(ROOT/'pilot_result.json',result);print('CAR_ROI_PILOT_RESULT',result,flush=True)
if __name__=='__main__':main()
