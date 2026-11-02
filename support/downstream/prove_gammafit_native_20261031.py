"""Actual portable C probes for a development-qualified gamma/allview expert."""
import os,shutil,subprocess,concurrent.futures as cf,hashlib,time
from pathlib import Path
import numpy as np
from train_allview_gamma_20261031 import ROOT
from road_enhanced_detection_common import BASE,INITIAL,read,write,sha,gates
from export_road_twilight_weights import pack
from shadowlift_lab import words
from prove_car_zoom_c import ZoomC
from study_car_zoom_20261030 import XS
import allview_enhance_native as native
import road_accuracy_common as ac
from road_numpy_eval import evaluate

def main():
    import torch
    sel=read(ROOT/'selected.json');assert sel['qualified'];out=ROOT/'c_proof';assert not out.exists();out.mkdir();src=out/'source';src.mkdir();scratch=out/'scratch';scratch.mkdir()
    native.ROOT=ROOT;start=time.monotonic();gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH']
    shutil.copy2(BASE/'road_student_fusion_20261031_r1/source/road_retinex_c.h',src/'road_retinex_c.h')
    shutil.copy2(Path(__file__).with_name('road_gamma_paper_detection.c'),src/'road_gamma_paper_detection.c')
    (src/'road_allview_config.h').write_text('#define ROAD_ALLVIEW_KIND 0\n#define ROAD_ALLVIEW_GAMMA .8f\n',encoding='ascii')
    cmd=[str(gcc),'-shared','-O2','-std=c99','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror','-msse2','-mfpmath=sse','-I'+str(src),str(src/'road_gamma_paper_detection.c'),'-lm','-o',str(out/'enhance.dll')]
    p=subprocess.run(cmd,env=env,capture_output=True,text=True);(out/'build.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
    _,graph,old,_=pack(INITIAL);assert old.tobytes()==(INITIAL.parent/'weights.f32').read_bytes();exports={}
    for kind,r in [('enhanced',sel['chosen']),('raw_control',sel['raw_control'])]:
        ck=Path(r['checkpoint']);assert sha(ck)==r['checkpoint_sha256'];_,gg,w,ss=pack(ck);assert gg==graph and w.shape==old.shape and (w!=old).any()
        dest=ROOT/'export'/kind;dest.mkdir(parents=True);w.tofile(dest/'weights.f32');shutil.copy2(ck,dest/'model.pt')
        meta=dict(status='MATCHED_ALLVIEW_EXPERT_EXPORTED',checkpoint_sha256=sha(ck),weights_sha256=sha(dest/'weights.f32'),changed_floats=int((w!=old).sum()),weight_floats=len(w),shapes=ss,graph_unchanged=True,selection_sha256=sha(ROOT/'selected.json'))
        write(dest/'complete.json',meta);exports[kind]=dest
    write(out/'policy.json',dict(status='FROZEN_BEFORE_C_PROBES',selection_sha256=sha(ROOT/'selected.json'),probes='24 development images by fixedhash, all7views, RAWcontrol and ENHcheckpoint on bothRAW and enhanced. Actual CPU-C vs GPU sameCinput max.001mean.00002. Cpost vs NumPy all480 selectedGPU results. Not a480image actualCaccuracy test; fresh304 must be allactualC.',hardware_access=False,sd_written=False))
    rows=[r for r in read(ROOT/'development_manifest.json') if r['cohort']=='low'];probes=sorted(rows,key=lambda r:hashlib.sha256(('2026103163'+r['name']).encode()).hexdigest())[:24]
    engine=native.Engine();zoom=ZoomC();tests=[];tasks=[]
    def inputs(a,name):
        b=engine.run(a);q=a.astype(np.uint32);mean=float(((54*q[:,:,0]+183*q[:,:,1]+19*q[:,:,2])/256).mean());ref=ac.gamma(a,'gamma080') if mean<=48 and np.any(a) else a.copy();d=np.abs(b.astype(np.int16)-ref.astype(np.int16));assert d.max()<=1 and d.mean()<.005,(name,d.max(),d.mean())
        tests.append(dict(name=name,max_abs=int(d.max()),mean_abs=float(d.mean())));return b
    for r in probes:
        sensor,full=ac.sensor400(Path(r['data_root'])/'images'/r['name']);views=[full]+[sensor[y:y+240,x:x+400] for x,y in ac.TILES]+[zoom.image(sensor,x,152) for x in XS]
        for j,a in enumerate(views):
            b=inputs(a,r['name']+'_'+str(j))
            tasks.extend([(r['name'],j,'raw_control',a),(r['name'],j,'same_enh_raw',a),(r['name'],j,'enhanced',b)])
    for k in [0,1,16,47,48,49,96,255]:inputs(np.full((240,400,3),k,np.uint8),'gray'+str(k))
    exe=BASE/'road_local_enhance_20261029_r2/host/road_ap.exe';assert sha(exe)==read(exe.parent/'build.json')['exe_sha256']
    def one(job):
        i,(name,view,kind,a)=job;folder=scratch/str(i);folder.mkdir();ip=folder/'input.u32';words(a).tofile(ip);weight=exports['raw_control' if kind=='raw_control' else 'enhanced']/'weights.f32'
        p=subprocess.run([str(exe),str(weight),str(ip),str(folder)],capture_output=True,text=True,env=env,timeout=90);assert p.returncode==0 and 'ROAD_FP32_HOST_DONE' in p.stdout,p.stderr
        decoded=np.fromfile(folder/'decoded.f32','<f4').reshape(6300,9);receipt=dict(name=name,view=view,condition=kind,input_sha256=sha(ip),decoded_sha256=sha(folder/'decoded.f32'),boxes_sha256=sha(folder/'boxes400.f32'))
        for f in folder.iterdir():assert f.resolve().is_relative_to(scratch.resolve()) and f.is_file();f.unlink()
        folder.rmdir();return decoded,receipt
    cpu=[]
    with cf.ThreadPoolExecutor(4) as pool:
        for i,item in enumerate(pool.map(one,enumerate(tasks)),1):
            cpu.append(item)
            if i%84==0:print('GAMMAFIT_ACTUAL_C_PROBES',i,len(tasks),round(time.monotonic()-start),flush=True)
    proofs=[];ac.WEIGHTS=INITIAL;det=ac.Detector()
    for kind in ['raw_control','same_enh_raw','enhanced']:
        ck=exports['raw_control' if kind=='raw_control' else 'enhanced']/'model.pt';del det.model;torch.cuda.empty_cache();det.model=torch.load(ck,map_location='cpu',weights_only=False)['model'].float().fuse().eval().cuda()
        ids=[i for i,t in enumerate(tasks) if t[2]==kind]
        for at in range(0,len(ids),8):
            ii=ids[at:at+8];x=np.stack([ac.preprocess400(tasks[i][3]).transpose(2,0,1) for i in ii])
            with torch.inference_mode():gpu=det.model(torch.from_numpy(np.ascontiguousarray(x)).cuda().float()/255)[0].cpu().numpy()
            for i,b in zip(ii,gpu):
                d=np.abs(cpu[i][0]-b);assert d.max()<=.001 and d.mean()<=.00002,(tasks[i][:3],d.max(),d.mean());proofs.append(dict(**cpu[i][1],max_abs=float(d.max()),mean_abs=float(d.mean())))
    post=native.Post();cresults={};gates_result={}
    for kind,record in [('raw_control',sel['raw_control']),('same_enh_raw',sel['chosen']),('enhanced',sel['chosen'])]:
        folder=ROOT/'development'/f"{record['branch']}{record['epoch']}";mode='enh' if kind=='enhanced' else 'raw';vpred=read(folder/'view_predictions.json')[mode];pred=read(folder/'predictions.json')[mode];actual=[]
        assert len(vpred)==480
        for i,(v,r) in enumerate(zip(vpred,pred),1):
            m=rows[i-1];assert m['name']==v['name']==r['name'];sensor,_=ac.sensor400(Path(m['data_root'])/'images'/m['name']);b,_=post.run(v['detections'],sensor,prove_numpy=True);ref=np.asarray(r['detections'],np.float32).reshape(-1,6)
            assert b.shape==ref.shape and np.max(np.abs(b-ref),initial=0)<=.0001,(kind,r['name']);actual.append(dict(name=r['name'],ground_truth=r['ground_truth'],detections=b.tolist()))
            if i%160==0:print('GAMMAFIT_C_POST',kind,i,480,flush=True)
        write(out/(kind+'_gpu_inputs_c_post.json'),actual);cresults[kind]=evaluate(actual)['classes']['car']
    m=cresults['enhanced'];gg=dict(accepted=gates(sel['accepted_baseline'],m),matched=gates(cresults['raw_control'],m),attribution=dict(ap=m['ap50']>=cresults['same_enh_raw']['ap50']+.002,tp=m['tp']>=cresults['same_enh_raw']['tp'],fp=m['fp']<=cresults['same_enh_raw']['fp']))
    accepted=all(all(x.values()) for x in gg.values());write(out/'pixel_probes.json',tests);write(out/'network_probes.json',proofs)
    proof=dict(status='GAMMAFIT_C_PROBES_PASSED_REQUIRES_FULL_ACTUAL_C_FRESH' if accepted else 'GAMMAFIT_C_PROBES_REJECTED',qualified=accepted,scores=cresults,gates=gg,actual_c_forwards=len(tasks),pixel_tests=len(tests),network_max_abs=max(x['max_abs'] for x in proofs),network_max_mean=max(x['mean_abs'] for x in proofs),enhance_dll_sha256=sha(out/'enhance.dll'),selection_sha256=sha(ROOT/'selected.json'),seconds=time.monotonic()-start,hardware_access=False,sd_written=False)
    write(out/'complete.json',proof);print('GAMMAFIT_C_COMPLETE',proof,flush=True)
if __name__=='__main__':main()
