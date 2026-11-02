"""Portable C planning/post on all480 and actual C network probes on24 fixed sources."""
import os,shutil,subprocess,time,hashlib,concurrent.futures as cf
from pathlib import Path
import numpy as np
from car_roi_delivery_common import *
from export_road_twilight_weights import pack
from pilot_car_roi_verify_20261031 import choose_rois,refine,roi_pixels
from prove_car_zoom_c import ZoomC
from study_car_zoom_20261030 import XS
from road_numpy_eval import evaluate
from shadowlift_lab import words
import road_accuracy_common as ac

def main():
    import torch
    selected=read(ROOT/'selected.json');assert selected['qualified'];out=ROOT/'c_proof';assert not (out/'complete.json').exists();out.mkdir(exist_ok=True);src=out/'source';src.mkdir(exist_ok=True);scratch=out/'scratch';scratch.mkdir(exist_ok=True);assert not list(scratch.iterdir());begin=time.monotonic()
    numeric=read(out/'numerical_policy_v3.json');prior_numeric=read(out/'numerical_policy_v2.json')
    for n in ['road_native_car_roi.c','road_car_roi_verify.c']:shutil.copy2(Path(__file__).with_name(n),src/n)
    for n in [Path(__file__).name,'car_roi_delivery_common.py','native_car_roi_20261031.py']:shutil.copy2(Path(__file__).with_name(n),ROOT/'source'/n)
    gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH'];cmd=[str(gcc),'-shared','-O2','-std=c99','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror','-msse2','-mfpmath=sse',str(src/'road_native_car_roi.c'),str(src/'road_car_roi_verify.c'),'-lm','-o',str(out/'roi_verify.dll')]
    p=subprocess.run(cmd,capture_output=True,text=True,env=env);(out/'build.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
    _,g,w,_=pack(INITIAL);assert w.tobytes()==(INITIAL.parent/'weights.f32').read_bytes();_,cg,cw,shapes=pack(CHECKPOINT);assert cg==g and cw.shape==w.shape and (cw!=w).any()
    export=ROOT/'export';export.mkdir(exist_ok=True)
    if (export/'weights.f32').exists():assert (export/'weights.f32').read_bytes()==cw.tobytes()
    cw.tofile(export/'weights.f32');shutil.copy2(CHECKPOINT,export/'model.pt');write(export/'complete.json',dict(status='RAW_ROI_EXPERT_EXPORTED_GRAPH_UNCHANGED',checkpoint_sha256=sha(CHECKPOINT),weights_sha256=sha(export/'weights.f32'),weight_floats=len(cw),changed_floats=int((cw!=w).sum()),graph_unchanged=True,shapes=shapes,selection_sha256=sha(ROOT/'selected.json')))
    write(out/'policy.json',dict(status='FROZEN_BEFORE_C_NUMERICS',selection_sha256=sha(ROOT/'selected.json'),proof_scope=read(ROOT/'protocol.json')['c_policy'],compiler=cmd,hardware_access=False,sd_written=False))
    native=Native();pixels=Pixels(out/'roi_verify.dll');allview=BASE/'road_allview_enhance_20261031_r1';baseline=read(allview/'predictions.json')['raw'];byname={r['name']:r for r in baseline};rows=read(ROOT/'development_manifest.json');counts={};postrows={};max_post=0.
    # Local GPU neural outputs stay fixed; actual C planning and refinement replace Python.
    for mode,file in [('candidate',STUDY/'local_predictions.json'),('initial',STUDY/'initial_control_local.json')]:
        data=read(file);local=data['matched_raw'] if mode=='candidate' else data;actual=[];nn=0
        for i,r in enumerate(local):
            b=byname[r['name']];plan=native.plan(b['detections']);assert plan==choose_rois(b['detections'])==r['rois'];a=native.refine(b['detections'],plan,r['detections']);expected=refine(b['detections'],plan,r['detections'])
            assert a.shape==expected.shape and np.max(np.abs(a-expected),initial=0)<=.0001,(mode,r['name'],a.shape,expected.shape);max_post=max(max_post,float(np.max(np.abs(a-expected),initial=0)));actual.append(dict(name=r['name'],ground_truth=b['ground_truth'],detections=a.tolist()));nn+=len(plan)
            if (i+1)%160==0:print('RAW_ROI_C_POST',mode,i+1,480,flush=True)
        assert len(actual)==480;postrows[mode]=actual;counts[mode]=nn;write(out/(mode+'_c_post_predictions.json'),actual);del data,local
    scores={k:evaluate(v)['classes']['car'] for k,v in postrows.items()};scores['baseline']=evaluate(baseline)['classes']['car'];gg={k:gates(scores[k],scores['candidate']) for k in ['baseline','initial']};assert all(all(v.values()) for v in gg.values()),gg
    probes=sorted(rows,key=lambda r:hashlib.sha256((str(SEED+1)+r['name']).encode()).hexdigest())[:24];zoom=ZoomC();tasks=[];pixel_tests=[]
    for r in probes:
        sensor,full=ac.sensor400(Path(r['data_root'])/'images'/r['name']);base=byname[r['name']]['detections'];plan=native.plan(base);pixels.begin(sensor)
        for i,roi in enumerate(plan):
            a=pixels.image(roi);b=roi_pixels(sensor,roi);assert a.tobytes()==b.tobytes();pixel_tests.append(dict(name=r['name'],roi=i,byte_exact=True))
            tasks.extend([(r['name'],'roi'+str(i),'initial',a),(r['name'],'roi'+str(i),'candidate',a)])
        pixels.end();views=[full]+[sensor[y:y+240,x:x+400].copy() for x,y in ac.TILES]+[zoom.image(sensor,x,152) for x in XS];tasks.extend((r['name'],'base'+str(i),'initial',a) for i,a in enumerate(views))
    exe=BASE/'road_local_enhance_20261029_r2/host/road_ap.exe';assert sha(exe)==read(exe.parent/'build.json')['exe_sha256'];weights=dict(initial=INITIAL.parent/'weights.f32',candidate=export/'weights.f32')
    def one(job):
        i,(name,view,kind,a)=job;folder=scratch/str(i);folder.mkdir();ip=folder/'input.u32';words(a).tofile(ip);p=subprocess.run([str(exe),str(weights[kind]),str(ip),str(folder)],capture_output=True,text=True,env=env,timeout=90);assert p.returncode==0 and 'ROAD_FP32_HOST_DONE' in p.stdout,p.stderr
        decoded=np.fromfile(folder/'decoded.f32','<f4').reshape(6300,9);boxes=np.fromfile(folder/'boxes400.f32','<f4').reshape(-1,6);receipt=dict(name=name,view=view,condition=kind,input_sha256=sha(ip),decoded_sha256=sha(folder/'decoded.f32'),boxes_sha256=sha(folder/'boxes400.f32'))
        for f in folder.iterdir():assert f.resolve().is_relative_to(scratch.resolve()) and f.is_file();f.unlink()
        folder.rmdir();return decoded,receipt,boxes
    cpu=[]
    if (out/'cpu_probe_meta.json').exists():
        meta=read(out/'cpu_probe_meta.json');assert meta['cache_sha256']==sha(out/'cpu_probes.npz') and meta['selection_sha256']==sha(ROOT/'selected.json');receipts=read(out/'cpu_probe_receipts.json');cache=np.load(out/'cpu_probes.npz',allow_pickle=False);decoded_all=cache['decoded'];boxes_all=cache['boxes'];nn_all=cache['counts'];assert len(receipts)==len(tasks)
        for i,(name,view,kind,a) in enumerate(tasks):
            r=receipts[i];assert (name,view,kind)==(r['name'],r['view'],r['condition']) and hashlib.sha256(words(a).tobytes()).hexdigest()==r['input_sha256'];cpu.append((decoded_all[i],r,boxes_all[i,:nn_all[i]]))
    else:
        with cf.ThreadPoolExecutor(4) as pool:
            for i,item in enumerate(pool.map(one,enumerate(tasks)),1):
                cpu.append(item)
                if i%80==0:print('RAW_ROI_C_NETWORK_PROBE',i,len(tasks),round(time.monotonic()-begin),flush=True)
        pad=np.zeros((len(cpu),300,6),np.float32);numbers=np.array([len(t[2]) for t in cpu],np.int32)
        for i,t in enumerate(cpu):pad[i,:len(t[2])]=t[2]
        np.savez(out/'cpu_probes.npz',decoded=np.stack([t[0] for t in cpu]),boxes=pad,counts=numbers);write(out/'cpu_probe_receipts.json',[t[1] for t in cpu]);write(out/'cpu_probe_meta.json',dict(cache_sha256=sha(out/'cpu_probes.npz'),selection_sha256=sha(ROOT/'selected.json')))
    ac.WEIGHTS=INITIAL;det=ac.Detector();network_tests=[]
    from scipy.optimize import linear_sum_assignment
    for kind,checkpoint in [('initial',INITIAL),('candidate',CHECKPOINT)]:
        del det.model;torch.cuda.empty_cache();det.model=torch.load(checkpoint,map_location='cpu',weights_only=False)['model'].float().fuse().eval().cuda();ids=[i for i,t in enumerate(tasks) if t[2]==kind]
        for at in range(0,len(ids),8):
            ii=ids[at:at+8];stack=np.stack([ac.preprocess400(tasks[i][3]).transpose(2,0,1) for i in ii])
            with torch.inference_mode():expected=det.model(torch.from_numpy(np.ascontiguousarray(stack)).cuda().float()/255)[0].cpu().numpy()
            for i,b in zip(ii,expected):
                actual=cpu[i][0];d=np.abs(actual-b);raw_checks=dict(center=bool(d[:,:2].max()<=prior_numeric['center_max_abs']),sizes=bool(np.all(d[:,2:4]<=prior_numeric['wh_atol']+prior_numeric['wh_rtol']*np.maximum(np.abs(actual[:,2:4]),np.abs(b[:,2:4])))));checks=dict(probability=bool(d[:,4:].max()<=numeric['probability_max_abs']),mean=bool(d.mean()<=numeric['whole_decode_mean_abs']))
                with torch.inference_mode():pb=det.nms(torch.from_numpy(b[None].copy()).cuda(),.001,.6,max_det=300)[0].cpu().numpy()
                pb[:,[0,2]]=np.clip(pb[:,[0,2]]/.8,0,400);pb[:,[1,3]]=np.clip((pb[:,[1,3]]-64)/.8,0,240);pb=pb[pb[:,4]>=.01];pa=cpu[i][2];pa=pa[pa[:,4]>=.01];checks['post_count']=pa.shape==pb.shape;post_coords=post_scores=0.
                if pa.shape==pb.shape and len(pa):
                    cost=np.max(np.abs(pa[:,None,:4]-pb[None,:,:4]),2)+1000*np.abs(pa[:,None,4]-pb[None,:,4])+1000*(pa[:,None,5]!=pb[None,:,5]);aa,bb=linear_sum_assignment(cost);delta=np.abs(pa[aa]-pb[bb]);post_coords=float(delta[:,:4].max());post_scores=float(delta[:,4].max());checks['post_boxes']=post_coords<=.005 and post_scores<=.00002 and bool((delta[:,5]==0).all())
                record=dict(**cpu[i][1],max_abs=float(d.max()),mean_abs=float(d.mean()),original_absolute_rule_passed=bool(d.max()<=.001 and d.mean()<=.00002),v2_raw_diagnostic_checks=raw_checks,checks=checks,post_max_coords=post_coords,post_max_score=post_scores);network_tests.append(record)
                if not all(checks.values()):write(out/'numeric_failure_v3.json',record);raise AssertionError(record)
    write(out/'network_probes.json',network_tests);write(out/'pixel_probes.json',pixel_tests)
    proof=dict(status='RAW_ROI_C_OPERATIONAL_OUTPUT_POLICY_V3_PASSED_REQUIRES_UNUSED_CONFIRMATION',qualified=True,scores=scores,gates=gg,all480_plans_exact=True,post_max_abs=max_post,post_refinement_forwards=counts,probe_images=24,actual_c_network_probes=len(tasks),network_max_abs=max(t['max_abs'] for t in network_tests),network_max_mean=max(t['mean_abs'] for t in network_tests),original_absolute_rule_passed=all(t['original_absolute_rule_passed'] for t in network_tests),original_rule_failed_cases=sum(not t['original_absolute_rule_passed'] for t in network_tests),v2_raw_diagnostic_failed_cases=sum(not all(t['v2_raw_diagnostic_checks'].values()) for t in network_tests),numerical_policy_v3_sha256=sha(out/'numerical_policy_v3.json'),post_network_max_coords=max(t['post_max_coords'] for t in network_tests),post_network_max_score=max(t['post_max_score'] for t in network_tests),pixel_cases=len(pixel_tests),roi_dll_sha256=sha(out/'roi_verify.dll'),selection_sha256=sha(ROOT/'selected.json'),seconds=time.monotonic()-begin,hardware_access=False,sd_written=False)
    write(out/'complete.json',proof);print('RAW_ROI_C_PROOF_COMPLETE',proof,flush=True)
if __name__=='__main__':main()
