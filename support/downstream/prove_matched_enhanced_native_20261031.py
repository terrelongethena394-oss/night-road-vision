"""Frozen choice:actual C global networks + C fusion/refiner on480dev images."""
import ctypes as ct,concurrent.futures as cf,os,shutil,subprocess,time
import numpy as np
from road_enhanced_detection_common import *
from road_classwise_native import Box
from prove_car_zoom_c import ZoomC
from prove_balanced_car_c import RefinerC
from evaluate_matched_enhanced_detectors_20261031 import post
from road_numpy_eval import evaluate
from prove_student_fusion_20261031 import Engine
from shadowlift_lab import words
import road_accuracy_common as ac

class MappedFusion(ZoomC):
    def __init__(self):
        self.lib=ct.CDLL(str(ROOT/'native_proof/fusion.dll'));self.bp=ct.POINTER(Box);self.fuse=self.lib.road_vehicle_mapped
        self.fuse.argtypes=[self.bp,ct.c_int,self.bp,ct.POINTER(ct.c_int),ct.c_float,self.bp,ct.c_int];self.fuse.restype=ct.c_int

def cpost(global_pred,h,params,mapped,refiner):
    b=mapped.run(global_pred,h['tiles_mapped'],.75);b=b[b[:,5]==1]
    return refiner.fuse(b,h['zoom_local'],h['refiner_outputs'],params)

def main():
    selected=read(ROOT/'selected.json');assert selected['qualified'];assert not (ROOT/'native_proof').exists()
    out=ROOT/'native_proof';out.mkdir();src=out/'source';src.mkdir();scratch=out/'scratch';scratch.mkdir()
    old=BASE/'road_car_balanced_20261030_r1/board_candidate/firmware/source'
    s=(old/'road_vehicle_multiview.c').read_text()
    boundary='if(b.cls==0||b.score<.05f||!(b.x1>1.f&&b.y1>1.f&&b.x2<399.f&&b.y2<239.f))continue;'
    mapping='b.x1=b.x1*.5f+(float)t*100.f;b.x2=b.x2*.5f+(float)t*100.f;b.y1=b.y1*.5f+60.f;b.y2=b.y2*.5f+60.f;'
    assert s.count(boundary)==s.count(mapping)==1
    s=s.replace(boundary,'if(b.cls==0||b.score<.05f)continue;').replace(mapping,'').replace('int road_vehicle_multiview(','int road_vehicle_mapped(')
    (src/'road_vehicle_mapped.c').write_text(s,encoding='ascii')
    for name in ['road_vehicle_multiview.h','road_fp32.h','road_graph.h']:shutil.copy2(old/name,src/name)
    gcc=BASE.parent/'Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe';env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH']
    cmd=[str(gcc),'-shared','-O2','-std=c99','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror','-static-libgcc','-Wl,--export-all-symbols',str(src/'road_vehicle_mapped.c'),'-lm','-o',str(out/'fusion.dll')]
    p=subprocess.run(cmd,capture_output=True,text=True,env=env);(out/'build.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
    shutil.copy2(__file__,ROOT/'source'/Path(__file__).name)
    helpers=read(ROOT/'helper_cache.json');manifest={r['name']:r for r in read(ROOT/'development_manifest.json')};params=read(BASE/'road_car_balanced_20261030_r1/selected.json')['chosen']['source']
    exe=BASE/'road_local_enhance_20261029_r2/host/road_ap.exe';assert sha(exe)==read(exe.parent/'build.json')['exe_sha256']
    weights={m:ROOT/'export'/m/'weights.f32' for m in ['enhanced','raw_control']}
    for name,path in weights.items():assert sha(path)==read(path.parent/'complete.json')['weights_sha256']
    write(out/'policy.json',dict(status='FROZEN_BEFORE_ACTUAL_C_DEVELOPMENT',selection_sha256=sha(ROOT/'selected.json'),weights_sha256={k:sha(p) for k,p in weights.items()},enhancer_sha256=sha(ENHANCER),accuracy_gates_unchanged=True,source_mapped_fusion='Same originalRAWfusion except accepts already edge-filtered andmapped cached tile boxes;source mapping performed identically before this stage. Final fresh confirmation uses full local-input C fusion.',hardware_access=False,sd_written=False))
    begin=time.monotonic();receipts=[];views={}
    # C engines own their scratch arrays;one per task to avoid data races.
    import threading
    local=threading.local()
    def one(task):
        i,h,kind=task;r=manifest[h['name']];sensor,raw=ac.sensor400(Path(r['data_root'])/'images'/r['name'])
        if kind=='enhanced':
            if not hasattr(local,'engine'):local.engine=Engine()
            im=local.engine.run(raw)
            from PIL import Image
            assert np.array_equal(ac.preprocess400(im),np.asarray(Image.open(r['enhanced_global']['image'])))
            weight=weights['enhanced']
        else:im=raw;weight=weights['raw_control'] if kind=='raw_control' else weights['enhanced']
        folder=scratch/f'{kind}_{i}';folder.mkdir();ip=folder/'input.u32';words(im).tofile(ip)
        p=subprocess.run([str(exe),str(weight),str(ip),str(folder)],capture_output=True,text=True,env=env,timeout=90);assert p.returncode==0 and 'ROAD_FP32_HOST_DONE' in p.stdout,p.stderr
        pred=np.fromfile(folder/'boxes400.f32','<f4').reshape(-1,6)
        evidence=dict(name=h['name'],condition=kind,input_sha256=sha(ip),decoded_sha256=sha(folder/'decoded.f32'),boxes_sha256=sha(folder/'boxes400.f32'))
        for p in folder.iterdir():assert p.resolve().is_relative_to(scratch.resolve()) and p.is_file();p.unlink()
        folder.rmdir();return dict(name=h['name'],detections=pred.tolist()),evidence
    for kind in ['raw_control','same_enh_raw','enhanced']:
        records=[]
        with cf.ThreadPoolExecutor(4) as pool:
            for i,(r,receipt) in enumerate(pool.map(one,[(i,h,kind) for i,h in enumerate(helpers)]),1):
                records.append(r);receipts.append(receipt)
                if i%80==0:print('ENHANCED_DEV_ACTUAL_C',kind,i,len(helpers),round(time.monotonic()-begin),flush=True)
        write(out/(kind+'_global.json'),records);views[kind]={r['name']:r['detections'] for r in records}
    mapped=MappedFusion();refiner=RefinerC();rows={k:[] for k in ['accepted','raw_control','same_enh_raw','enhanced']};maxdiff=0.
    for h in helpers:
        for kind in rows:
            g=h['global_raw'] if kind=='accepted' else views[kind][h['name']]
            a=cpost(g,h,params,mapped,refiner);b=post(g,h,params)
            assert a.shape==b.shape and np.max(np.abs(a-b),initial=0)<=.0001,(h['name'],kind,a.shape,b.shape)
            maxdiff=max(maxdiff,float(np.max(np.abs(a-b),initial=0)))
            rows[kind].append(dict(name=h['name'],ground_truth=h['ground_truth'],detections=a.tolist()))
    scores={k:evaluate(v)['classes']['car'] for k,v in rows.items()};m=scores['enhanced'];gg=dict(accepted=gates(scores['accepted'],m),raw_control=gates(scores['raw_control'],m),same_checkpoint_raw=dict(ap=m['ap50']>=scores['same_enh_raw']['ap50']+.002,fp=m['fp']<=scores['same_enh_raw']['fp'],tp=m['tp']>=scores['same_enh_raw']['tp']))
    qualified=all(all(v.values()) for v in gg.values())
    for kind,v in rows.items():write(out/(kind+'_predictions.json'),v)
    write(out/'receipts.json',receipts)
    proof=dict(status='MATCHED_ENHANCED_ACTUAL_C_DEVELOPMENT_ACCEPTED' if qualified else 'MATCHED_ENHANCED_ACTUAL_C_DEVELOPMENT_REJECTED_KEEP_ABI29',qualified=qualified,scores=scores,gates=gg,actual_c_global_forwards=len(receipts),post_c_numpy_max_abs=maxdiff,selection_sha256=sha(ROOT/'selected.json'),fusion_dll_sha256=sha(out/'fusion.dll'),seconds=time.monotonic()-begin,hardware_access=False,sd_written=False)
    write(out/'complete.json',proof);print('ENHANCED_ACTUAL_C_DEV_COMPLETE',proof,flush=True)
if __name__=='__main__':main()
