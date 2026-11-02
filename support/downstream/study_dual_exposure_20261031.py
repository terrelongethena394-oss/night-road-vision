"""Complementary RAW/ENH box fusion, fairly controlled by RAW/flip-RAW fusion."""
import os,sys,ctypes as ct,subprocess,time,shutil,itertools
from pathlib import Path
import numpy as np
from road_enhanced_detection_common import BASE,INITIAL,read,write,sha,gates
import road_accuracy_common as ac
from road_numpy_eval import evaluate,correct
from confirm_road_viewadapt import statistics,car_ap50
from prove_car_zoom_c import ZoomC
from study_car_zoom_20261030 import XS
from allview_enhance_native import Post
ROOT=BASE/'road_dual_exposure_20261031_r1'

class Fuser:
    def __init__(self):
        self.directory=os.add_dll_directory('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin');self.lib=ct.CDLL(str(ROOT/'fusion.dll'));self.fp=ct.POINTER(ct.c_float)
        self.fn=self.lib.road_dual_fuse;self.fn.argtypes=[self.fp,ct.c_int,self.fp,ct.c_int,ct.c_float,ct.c_float,ct.c_int,ct.c_int,self.fp];self.fn.restype=ct.c_int
    def run(self,a,b,config):
        a=np.asarray(a,np.float32).reshape(-1,6);b=np.asarray(b,np.float32).reshape(-1,6);aa=a.tobytes();bb=b.tobytes();o=np.full((302,6),np.float32(12345.25));p=ct.cast(ct.c_void_p(o.ctypes.data+24),self.fp)
        n=self.fn(a.ctypes.data_as(self.fp),len(a),b.ctypes.data_as(self.fp),len(b),config['iou'],config['unmatched'],config['score_mode'],config['coordinate_mode'],p)
        assert 0<=n<=300 and a.tobytes()==aa and b.tobytes()==bb and np.all(o[[0,-1]]==np.float32(12345.25));return o[1:1+n].copy()

def main():
    import torch
    assert not ROOT.exists();ROOT.mkdir();(ROOT/'source').mkdir();prior=BASE/'road_allview_enhance_20261031_r1';assert read(prior/'selected.json')['qualified'] is False
    configs=[dict(iou=i,unmatched=q,score_mode=s,coordinate_mode=c) for i,q,s,c in itertools.product([.3,.45,.6],[.6,.8,1.],[0,1],[0,1])];methods=['gamma080','gamma065','paper_reference','abi29mix10','task_gate12']
    write(ROOT/'protocol.json',dict(status='FROZEN_BEFORE_ANY_DUAL_BRANCH_OR_FLIPPED_PREDICTIONS',
      purpose='Single enhanced paths have failed. Test complementary RAW+ENH two-branch detection. This doubles main forwards to14 per lowframe; not enhanced-only or realtime detection.',
      controls='OriginalRAW7; strongest RAW7+horizontal-flippedRAW7 fusion among same36configs. Both two-branch routes have14same-model forwards, same7geometries/refiner. Only second-branch image processing differs.',
      fusion='Greedy sameclasscar matching RAW scoreorder,bestIoU; matched boxes weighted/equal coordinates,geometric/arithmetic meanconfidence;unmatchedconfidence fixedweight;finalNMS.6,max300. No labels/imagesnames at runtime.',
      configs=configs,methods=methods,gates='Vs BOTH originalRAW7 and strongest14forward RAW+flipcontrol:AP+.5pp,P>=,R+.5pp,FP<=,F1+.5pp. HighestAPpassingcandidate, no tuningafterfresh.',
      development='Exposed480low only, originalcandidate predictions reused; no newindependentdata. Bright>48 keeps original4RAW.',
      fresh_policy='Only afterCverification freezeone candidate, new unused240low+64bright actualC for all3primitive7view branches. Samegates plus paired99%APgainCI>0 vsbothRAWcontrols. No fresh-driven replacement.',
      initial_sha256=sha(INITIAL),prior_prediction_sha256=sha(prior/'predictions.json'),hardware_access=False,sd_written=False))
    for n in [Path(__file__).name,'road_dual_exposure_fuse.c']:shutil.copy2(Path(__file__).with_name(n),ROOT/'source'/n)
    gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH'];cmd=[str(gcc),'-shared','-O2','-std=c99','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror',str(ROOT/'source/road_dual_exposure_fuse.c'),'-lm','-o',str(ROOT/'fusion.dll')]
    p=subprocess.run(cmd,capture_output=True,text=True,env=env);(ROOT/'build.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
    torch.cuda.set_per_process_memory_fraction(.15);ac.WEIGHTS=INITIAL;det=ac.Detector();torch.set_num_threads(2);pixels=ZoomC();post=Post();rows=read(prior/'development_manifest.json');write(ROOT/'development_manifest.json',rows);flipped=[];local_views=[];begin=time.monotonic()
    for at,r in enumerate(rows):
        sensor,raw=ac.sensor400(Path(r['data_root'])/'images'/r['name']);sensor=sensor[:,::-1].copy();raw=raw[:,::-1].copy();views=[raw]+[sensor[y:y+240,x:x+400].copy() for x,y in ac.TILES]+[pixels.image(sensor,x,152) for x in XS]
        pp=det.run(views);a,_=post.run(pp,sensor);xx=a[:,0].copy();a[:,0]=400-a[:,2];a[:,2]=400-xx
        gt=ac.truth(Path(r['data_root'])/'labels'/(Path(r['name']).stem+'.txt'));gt=gt[gt[:,0]==1];flipped.append(dict(name=r['name'],ground_truth=gt.tolist(),detections=a.tolist()));local_views.append(dict(name=r['name'],detections=pp))
        if (at+1)%80==0:print('DUAL_EXPOSURE_FLIPPED_RAW',at+1,480,round(time.monotonic()-begin),flush=True)
    write(ROOT/'flipped_raw_predictions.json',flipped);write(ROOT/'flipped_raw_view_predictions.json',local_views)
    del det;torch.cuda.empty_cache();pred=read(prior/'predictions.json');raw=pred['raw'];assert [r['name'] for r in raw]==[r['name'] for r in flipped];fuser=Fuser();base=read(prior/'selected.json')['scores']['raw']
    def assess(second,config):
        rr=[dict(name=r['name'],ground_truth=r['ground_truth'],detections=fuser.run(r['detections'],s['detections'],config).tolist()) for r,s in zip(raw,second)]
        # Fast one-IoU metrics; exact agreement with full evaluator asserted for selected route.
        stats=statistics(rr);tp=fp=fn=0
        for r in rr:
            p=np.asarray(r['detections'],np.float32).reshape(-1,6);p=p[p[:,4]>=.25];g=np.asarray(r['ground_truth'],np.float32).reshape(-1,5);t=int(correct(p,g,np.array([.5],np.float32))[0][:,0].sum());tp+=t;fp+=len(p)-t;fn+=len(g)-t
        return dict(objects=tp+fn,ap50=car_ap50(stats,np.arange(480)),tp=tp,fp=fp,fn=fn,precision=tp/(tp+fp),recall=tp/(tp+fn)),rr
    controls=[]
    for config in configs:
        m,_=assess(flipped,config);controls.append(dict(config=config,scores=m))
    control=max(controls,key=lambda r:r['scores']['ap50']);write(ROOT/'raw_flip_control_selected.json',dict(chosen=control,all_controls=controls));print('DUAL_EXPOSURE_RAWFLIP_CONTROL',control,flush=True)
    candidates=[]
    for method in methods:
        for config in configs:
            m,_=assess(pred[method],config);gg=dict(accepted_raw7=gates(base,m),matched_raw_flip14=gates(control['scores'],m));qualified=all(all(v.values()) for v in gg.values());candidates.append(dict(method=method,config=config,scores=m,gates=gg,qualified=qualified))
        print('DUAL_EXPOSURE_SEARCH',method,len(candidates),round(time.monotonic()-begin),flush=True)
    good=[r for r in candidates if r['qualified']];chosen=max(good,key=lambda r:r['scores']['ap50']) if good else None
    if chosen:
        m,rr=assess(pred[chosen['method']],chosen['config']);full=evaluate(rr)['classes']['car'];assert abs(full['ap50']-m['ap50'])<1e-12;chosen['scores_full']=full;write(ROOT/'chosen_predictions.json',rr)
    write(ROOT/'candidates.json',candidates);result=dict(status='DUAL_EXPOSURE_REQUIRES_C_AND_UNUSED_CONFIRMATION' if chosen else 'NO_DUAL_EXPOSURE_PASSED_KEEP_ABI29',qualified=bool(chosen),chosen=chosen,raw_flip_control=control,accepted_baseline=base,best_descriptive=max(candidates,key=lambda r:r['scores']['ap50']),candidates=len(candidates),seconds=time.monotonic()-begin,new_independent_test_used=False,hardware_access=False,sd_written=False)
    write(ROOT/'selected.json',result);print('DUAL_EXPOSURE_RESULT',result,flush=True)
if __name__=='__main__':main()
