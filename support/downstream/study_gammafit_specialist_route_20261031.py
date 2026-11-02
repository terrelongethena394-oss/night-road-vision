"""Predeclared exposure-conditioned RAW/ENH expert study, same7forwards per image."""
from pathlib import Path
import sys,time,shutil
import numpy as np
from train_allview_gamma_20261031 import ROOT as TRAIN,CHECKPOINTS
from road_enhanced_detection_common import BASE,read,write,sha,gates
from confirm_road_viewadapt import statistics,car_ap50
from road_numpy_eval import correct,evaluate
ROOT=BASE/'road_gamma_specialist_route_20261031_r1'
EDGES=[0,8,16,24,32,40,48]
def freeze():
    assert not ROOT.exists();ROOT.mkdir();(ROOT/'source').mkdir();assert not (TRAIN/'selected.json').exists()
    write(ROOT/'protocol.json',dict(status='FROZEN_BEFORE_MATCHED_ALLVIEW_DEVELOPMENT_RESULTS',training_protocol_sha256=sha(TRAIN/'protocol.json'),
      rules='Strongest matchedRAW checkpoint bydevelopmentAP50. Outside a single rawmean exposureband use RAWexpert+RAWpixels;inside use one ENHcheckpoint4/8/12+gamma0.8 pixels. Same7views,no additional forwards. Runtime only rawmeanY; no GT/predictions/image names. Bright>48 keep originalCB4RAW.',
      grid=dict(edges=EDGES,min_routed_development_images=64,enhanced_checkpoints=CHECKPOINTS),
      controls='CurrentacceptedCBRAW7 andstrongestmatchedRAW7. Attributionroute:identical expert selection but ENHexpert receivesRAW pixels inside band. This controls extra modelcapacity and expert routing when measuring enhancement effect.',
      gates='Against BOTH RAWcontrols AP+.5pp,P>=,R+.5pp,FP<=,F1+.5pp. Against sameexpert RAWroute AP+.2pp,TP>=,FP<=. HighestAPpassingcandidate only.',
      development='Already exposed480low only; all selection exploratory. No extra gradients or new data. Prespecified while matched model training ongoing.',
      fresh_policy='Only after actualCproof freezecandidate and consume new untouched240low+64bright. Samegates,paired99%APgainCI lower>0 vsbothRAWcontrols. No test-driven re-selection.',hardware_access=False,sd_written=False))
    shutil.copy2(__file__,ROOT/'source'/Path(__file__).name);print('GAMMA_SPECIALIST_ROUTE_PROTOCOL_FROZEN',flush=True)
def counts(rr):
    out=[]
    for r in rr:
        p=np.asarray(r['detections'],np.float32).reshape(-1,6);p=p[(p[:,4]>=.25)&(p[:,5]==1)];g=np.asarray(r['ground_truth'],np.float32).reshape(-1,5);g=g[g[:,0]==1];tp=int(correct(p,g,np.array([.5],np.float32))[0][:,0].sum());out.append([tp,len(p)-tp,len(g)-tp])
    return np.asarray(out)
def main():
    assert (ROOT/'protocol.json').exists() and not (ROOT/'selected.json').exists();sel=read(TRAIN/'selected.json');assert sel['qualified'] is False
    begin=time.monotonic();control=sel['raw_control'];folder=TRAIN/'development'/f"raw{control['epoch']}";raw=read(folder/'predictions.json')['raw'];stats_raw=statistics(raw);cnt_raw=counts(raw);base=sel['accepted_baseline'];mraw=control['scores']['raw'];assert abs(car_ap50(stats_raw,np.arange(480))-mraw['ap50'])<1e-12
    features=read(BASE/'road_exposure_route_20261031_r1/raw_exposure_features.json');names=[r['name'] for r in raw];assert [r['name'] for r in features]==names;means=np.array([r['mean_y'] for r in features]);candidates=[]
    def score(stats,cnt):
        tp,fp,fn=[int(v) for v in cnt.sum(0)];return dict(objects=tp+fn,ap50=car_ap50(stats,np.arange(480)),tp=tp,fp=fp,fn=fn,precision=tp/(tp+fp),recall=tp/(tp+fn))
    for epoch in CHECKPOINTS:
        pp=read(TRAIN/'development'/f'enh{epoch}'/'predictions.json');assert [r['name'] for r in pp['enh']]==names;ss={k:statistics(pp[k]) for k in ['raw','enh']};cc={k:counts(pp[k]) for k in ['raw','enh']}
        for i,lo in enumerate(EDGES[:-1]):
            for hi in EDGES[i+1:]:
                on=(means>lo)&(means<=hi) if lo else (means>=0)&(means<=hi)
                if on.sum()<64:continue
                scores={k:score([ss[k][j] if yes else stats_raw[j] for j,yes in enumerate(on)],np.where(on[:,None],cc[k],cnt_raw)) for k in ['raw','enh']};m=scores['enh'];same=scores['raw'];gg=dict(accepted_raw7=gates(base,m),matched_raw7=gates(mraw,m),attribution=dict(ap=m['ap50']>=same['ap50']+.002,tp=m['tp']>=same['tp'],fp=m['fp']<=same['fp']));qualified=all(all(v.values()) for v in gg.values());candidates.append(dict(enhanced_epoch=epoch,lo=lo,hi=hi,routed_images=int(on.sum()),scores=scores,gates=gg,qualified=qualified))
        print('GAMMA_SPECIALIST_SEARCH',epoch,len(candidates),round(time.monotonic()-begin),flush=True)
    good=[r for r in candidates if r['qualified']];chosen=max(good,key=lambda r:r['scores']['enh']['ap50']) if good else None
    write(ROOT/'candidates.json',candidates);result=dict(status='GAMMA_SPECIALIST_REQUIRES_C_AND_UNUSED_CONFIRMATION' if chosen else 'NO_GAMMA_SPECIALIST_PASSED_KEEP_ABI29',qualified=bool(chosen),chosen=chosen,raw_control=control,accepted_baseline=base,best_descriptive=max(candidates,key=lambda r:r['scores']['enh']['ap50']),candidates=len(candidates),training_selection_sha256=sha(TRAIN/'selected.json'),seconds=time.monotonic()-begin,new_independent_test_used=False,hardware_access=False,sd_written=False)
    write(ROOT/'selected.json',result);print('GAMMA_SPECIALIST_RESULT',result,flush=True)
if __name__=='__main__':freeze() if '--freeze' in sys.argv else main()
