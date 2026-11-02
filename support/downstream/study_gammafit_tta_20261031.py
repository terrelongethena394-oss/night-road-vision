"""Same fourteen forwards for RAW and ENH experts; control stronger RAW-only TTA."""
from pathlib import Path
import sys,time,gc,shutil
import numpy as np
from road_enhanced_detection_common import BASE,INITIAL,read,write,sha,gates
from study_dual_exposure_20261031 import Fuser
from road_numpy_eval import correct,evaluate
from confirm_road_viewadapt import statistics,car_ap50
from allview_enhance_native import Post
from prove_car_zoom_c import ZoomC
from study_car_zoom_20261030 import XS
import road_accuracy_common as ac
ROOT=BASE/'road_gammafit_tta_20261031_r1'
TRAIN=BASE/'road_allview_gammafit_20261031_r1'
def counts(rr):
    out=[]
    for r in rr:
        p=np.asarray(r['detections'],np.float32).reshape(-1,6);p=p[p[:,4]>=.25];g=np.asarray(r['ground_truth'],np.float32).reshape(-1,5);tp=int(correct(p,g,np.array([.5],np.float32))[0][:,0].sum());out.append([tp,len(p)-tp,len(g)-tp])
    return np.asarray(out)
def main():
    import torch
    assert not ROOT.exists();ROOT.mkdir();(ROOT/'source').mkdir();prior=read(TRAIN/'selected.json');assert not prior['qualified']
    configs=read(BASE/'road_dual_exposure_20261031_r1/protocol.json')['configs'];raw_control=prior['raw_control'];enh_record=next(r for r in prior['records'] if r['epoch']==8)
    assert max(prior['records'],key=lambda r:r['scores']['enh']['ap50'])['epoch']==8
    cases=[('matched',Path(raw_control['checkpoint']),'raw',f"raw{raw_control['epoch']}"),('attribution',Path(enh_record['checkpoint']),'raw','enh8'),('enhanced',Path(enh_record['checkpoint']),'enh','enh8')]
    write(ROOT/'protocol.json',dict(status='FROZEN_BEFORE_TRAINED_EXPERT_FLIPPED_PREDICTIONS',
      purpose='7view trainedENH8 improvedAP butfailedstrictgates. Test identical horizontal-flip localization averaging for RAW and enhanced models; not an extra-TTA-vs-RAW7 attribution.',
      frozen_models=dict(raw_control=raw_control,enhanced=enh_record),configs=configs,
      controls='AcceptedCBRAW7, strongest originalCBRAW+flip14, strongest matchedtrainedRAW8+flip14. SameENH8weights onRAW+flip14 attribution with candidate SAMEfusionconfig. All14forwards,geometry/refiner/NMS fixed; comparestrongestRAWcontrols before candidate selection.',
      candidate='ENH8 model, gamma0.8 inboth orientations onall7views,eachcropmean>48exactRAW. Same rawsourceforrefiner. Bright overall>48 originalCB4RAWunchanged.',
      gates='Vs ALLthreeRAWcontrols AP+.5pp,P>=,R+.5pp,FP<=,F1+.5pp. SameENH8RAW14 attributionAP+.2pp,TP>=,FP<=. HighestAPpassingfusionconfig only.',
      development='Exposed480lowonly;model8 selectedonprior exposeddevelopment,never fresh. Fixed36fusionconfigs samefor RAW/ENH;no threshold changes.',
      fresh_policy='Onefrozenchoice afterCproof,newunused240low+64bright;allactualC samegates plus paired99%APgainCI>0 vsALLprimaryRAWcontrols;no test-drivenreplacement.',hardware_access=False,sd_written=False))
    shutil.copy2(__file__,ROOT/'source'/Path(__file__).name);rows=[r for r in read(TRAIN/'development_manifest.json') if r['cohort']=='low'];write(ROOT/'development_manifest.json',rows)
    ac.WEIGHTS=INITIAL;det=ac.Detector();pixels=ZoomC();post=Post();begin=time.monotonic();branches={};local_views={}
    for tag,checkpoint,mode,folder in cases:
        expected=read(checkpoint.with_name('frozen.json'))['sha256'];assert sha(checkpoint)==expected;del det.model;gc.collect();torch.cuda.empty_cache();det.model=torch.load(checkpoint,map_location='cpu',weights_only=False)['model'].float().fuse().eval().cuda();flipped=[];vv=[]
        for at,r in enumerate(rows):
            sensor,full=ac.sensor400(Path(r['data_root'])/'images'/r['name']);sensor=sensor[:,::-1].copy();full=full[:,::-1].copy();views=[full]+[sensor[y:y+240,x:x+400].copy() for x,y in ac.TILES]+[pixels.image(sensor,x,152) for x in XS]
            if mode=='enh':
                updated=[]
                for a in views:
                    z=a.astype(np.uint64);mean=float((54*z[:,:,0]+183*z[:,:,1]+19*z[:,:,2]).sum())/(256*96000);updated.append(ac.gamma(a,'gamma080') if mean<=48 else a)
                views=updated
            pp=det.run(views);b,_=post.run(pp,sensor);xx=b[:,0].copy();b[:,0]=400-b[:,2];b[:,2]=400-xx;gt=ac.truth(Path(r['data_root'])/'labels'/(Path(r['name']).stem+'.txt'));gt=gt[gt[:,0]==1];flipped.append(dict(name=r['name'],ground_truth=gt.tolist(),detections=b.tolist()));vv.append(dict(name=r['name'],detections=pp))
            if (at+1)%120==0:print('GAMMAFIT_TTA_FLIP',tag,at+1,480,round(time.monotonic()-begin),flush=True)
        write(ROOT/(tag+'_flipped_predictions.json'),flipped);write(ROOT/(tag+'_flipped_view_predictions.json'),vv);branches[tag]=(read(TRAIN/'development'/folder/'predictions.json')[mode],flipped)
    del det;torch.cuda.empty_cache();fuser=Fuser();scored={};all_records={}
    def assess(pair,config):
        a,b=pair;rr=[dict(name=x['name'],ground_truth=x['ground_truth'],detections=fuser.run(x['detections'],y['detections'],config).tolist()) for x,y in zip(a,b)];tp,fp,fn=[int(v) for v in counts(rr).sum(0)];return dict(objects=tp+fn,ap50=car_ap50(statistics(rr),np.arange(480)),tp=tp,fp=fp,fn=fn,precision=tp/(tp+fp),recall=tp/(tp+fn)),rr
    for tag in ['matched','attribution','enhanced']:
        scored[tag]=[]
        for i,c in enumerate(configs):
            m,_=assess(branches[tag],c);scored[tag].append(dict(index=i,config=c,scores=m))
        print('GAMMAFIT_TTA_GRID',tag,max(scored[tag],key=lambda r:r['scores']['ap50']),flush=True)
    matched=max(scored['matched'],key=lambda r:r['scores']['ap50']);cb14=read(BASE/'road_dual_exposure_20261031_r1/raw_flip_control_selected.json')['chosen'];base=prior['accepted_baseline'];candidates=[]
    for c in scored['enhanced']:
        m=c['scores'];same=scored['attribution'][c['index']]['scores'];gg=dict(accepted_raw7=gates(base,m),original_raw_flip14=gates(cb14['scores'],m),matched_raw_flip14=gates(matched['scores'],m),same_model_raw_flip14=dict(ap=m['ap50']>=same['ap50']+.002,tp=m['tp']>=same['tp'],fp=m['fp']<=same['fp']));c.update(attribution=same,gates=gg,qualified=all(all(v.values()) for v in gg.values()));candidates.append(c)
    good=[c for c in candidates if c['qualified']];chosen=max(good,key=lambda r:r['scores']['ap50']) if good else None
    if chosen:
        m,rr=assess(branches['enhanced'],chosen['config']);full=evaluate(rr)['classes']['car'];assert abs(full['ap50']-m['ap50'])<1e-12;chosen['scores_full']=full;write(ROOT/'chosen_predictions.json',rr)
    write(ROOT/'all_grid_scores.json',scored);result=dict(status='GAMMAFIT_TTA_REQUIRES_C_AND_UNUSED_CONFIRMATION' if chosen else 'NO_GAMMAFIT_TTA_PASSED_KEEP_ABI29',qualified=bool(chosen),chosen=chosen,candidates=candidates,matched_raw_flip_control=matched,original_raw_flip_control=cb14,accepted_raw7=base,best_descriptive=max(candidates,key=lambda r:r['scores']['ap50']),main_checkpoint_sha256=enh_record['checkpoint_sha256'],seconds=time.monotonic()-begin,new_independent_test_used=False,hardware_access=False,sd_written=False)
    write(ROOT/'selected.json',result);print('GAMMAFIT_TTA_RESULT',result,flush=True)
if __name__=='__main__':main()
