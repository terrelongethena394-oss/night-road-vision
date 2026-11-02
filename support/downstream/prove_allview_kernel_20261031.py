"""Only a qualified frozen candidate proceeds to portableC and fresh tests."""
import shutil,subprocess,os,hashlib,concurrent.futures as cf,time
import numpy as np
from road_enhanced_detection_common import BASE,read,write,sha
from allview_enhance_native import ROOT,Engine,Post
from shadowlift_lab import words
from road_retinex_project import paper_reference,illumination
from study_car_zoom_20261030 import XS
from prove_car_zoom_c import ZoomC
import road_accuracy_common as ac

def main():
    import torch
    selection=read(ROOT/'selected.json');assert selection['qualified'];chosen=selection['chosen']['method'];out=ROOT/'c_proof';assert not out.exists();out.mkdir();src=out/'source';src.mkdir();scratch=out/'scratch';scratch.mkdir()
    old=BASE/'road_student_fusion_20261031_r1/source';shutil.copy2(old/'road_retinex_c.h',src/'road_retinex_c.h')
    files=[];mask=None
    if chosen in ['gamma080','gamma065','paper_reference']:
        kind=1 if chosen=='paper_reference' else 0
        (src/'road_allview_config.h').write_text('#define ROAD_ALLVIEW_KIND '+str(kind)+'\n#define ROAD_ALLVIEW_GAMMA '+('.8f' if chosen=='gamma080' else '.65f')+'\n',encoding='ascii')
        shutil.copy2(Path(__file__).with_name('road_gamma_paper_detection.c'),src/'road_gamma_paper_detection.c');files=['road_gamma_paper_detection.c']
    else:
        for n in ['road_retinex_c.c','road_shadowlift.c','road_shadowlift.h','road_student_restore.c','road_student_weights.h']:shutil.copy2(old/n,src/n)
        s=(old/'road_student_fusion.c').read_text();(src/'road_task_bright.c').write_text(s.replace('int road_retinex_c(','int road_fusion_bright('),encoding='ascii')
        shutil.copy2(Path(__file__).with_name('road_detection_task_gate.c'),src/'road_detection_task_gate.c')
        config='#define ROAD_TASK_GATE_KIND '+str(int(chosen=='task_gate12'))+'\n'
        if chosen=='abi29mix10':config+='#define ROAD_TASK_GATE_K 2U\n'
        else:
            from road_task_gate_common import make_model
            p=BASE/'road_task_gate_20261031_r1/frozen/epoch12/model.pt';assert sha(p)==read(p.with_name('frozen.json'))['sha256'];state=torch.load(p,map_location='cpu',weights_only=True)
            mask=make_model().cuda().eval();mask.load_state_dict(state);keys=['first.weight','first.bias','depth.weight','depth.bias','head.weight','head.bias'];w=np.concatenate([state[k].numpy().reshape(-1) for k in keys]).astype('<f4');assert len(w)==153;w.tofile(out/'mask_weights.f32');config+='static const float road_task_gate_weights[153]={'+','.join(float(v).hex()+'f' for v in w)+'};\n'
        (src/'road_task_gate_config.h').write_text(config,encoding='ascii');files=['road_retinex_c.c','road_shadowlift.c','road_student_restore.c','road_task_bright.c','road_detection_task_gate.c']
    gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH']
    cmd=[str(gcc),'-shared','-O2','-std=c99','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror','-msse2','-mfpmath=sse','-I'+str(src),*[str(src/n) for n in files],'-lm','-o',str(out/'enhance.dll')]
    p=subprocess.run(cmd,capture_output=True,text=True,env=env);(out/'build.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
    write(out/'policy.json',dict(status='FROZEN_BEFORE_C_PROBES',selection_sha256=sha(ROOT/'selected.json'),chosen=chosen,
        probes='24development sources by fixedhash before examining outputs,all7views plus8uniformcontrols;Cenhance vsoriginalPython <=1gray/mean.005;mainnetwork CPU CvsGPU on exactCinput,max.001mean.00002. CpostvsNumPy onall480chosenCUDA outputs. Not480image actualCaccuracy confirmation;new304 must be entirely actualC.',hardware_access=False,sd_written=False))
    rows=read(ROOT/'development_manifest.json');selected=sorted(rows,key=lambda r:hashlib.sha256(('2026103151'+r['name']).encode()).hexdigest())[:24]
    engine=Engine();zoom=ZoomC();tests=[];network_inputs=[]
    from prove_student_fusion_20261031 import Engine as Bright
    bright=Bright() if chosen in ['abi29mix10','task_gate12'] else None
    def expected(a):
        q=a.astype(np.uint64);total=int((54*q[:,:,0]+183*q[:,:,1]+19*q[:,:,2]).sum())
        if total==0 or total>48*256*96000:return a.copy()
        if chosen.startswith('gamma'):return ac.gamma(a,chosen)
        if chosen=='paper_reference':return paper_reference(a)[0]
        b=bright.run(a)
        if chosen=='abi29mix10':return ((a.astype(np.uint32)*18+b.astype(np.uint32)*2+10)//20).astype(np.uint8)
        with torch.inference_mode():z,_=mask(torch.from_numpy(a.transpose(2,0,1).copy()).cuda().float()[None]/255,torch.from_numpy(b.transpose(2,0,1).copy()).cuda().float()[None]/255,torch.from_numpy(illumination(a)).cuda()[None,None])
        return np.floor(z[0].permute(1,2,0).cpu().numpy()*255+.5).astype(np.uint8)
    cases=[]
    for r in selected:
        sensor,full=ac.sensor400(Path(r['data_root'])/'images'/r['name']);views=[full]+[sensor[y:y+240,x:x+400] for x,y in ac.TILES]+[zoom.image(sensor,x,152) for x in XS]
        cases.extend((r['name']+'_'+str(i),a) for i,a in enumerate(views))
    cases.extend(('gray'+str(k),np.full((240,400,3),k,np.uint8)) for k in [0,1,16,47,48,49,96,255])
    for name,a in cases:
        actual=engine.run(a);ref=expected(a);d=np.abs(actual.astype(np.int16)-ref.astype(np.int16));assert d.max()<=1 and d.mean()<.005,(name,d.max(),d.mean());tests.append(dict(name=name,max_abs=int(d.max()),mean_abs=float(d.mean())))
        if not name.startswith('gray'):network_inputs.append((name,actual))
    exe=BASE/'road_local_enhance_20261029_r2/host/road_ap.exe';weights=BASE/'road_viewadapt_20261030_r1/export/weights.f32';assert sha(weights)==read(weights.parent/'complete.json')['weights_sha256'];receipts=[]
    def one(task):
        i,(name,a)=task;folder=scratch/str(i);folder.mkdir();ip=folder/'input.u32';words(a).tofile(ip)
        p=subprocess.run([str(exe),str(weights),str(ip),str(folder)],capture_output=True,text=True,env=env,timeout=90);assert p.returncode==0 and 'ROAD_FP32_HOST_DONE' in p.stdout
        decoded=np.fromfile(folder/'decoded.f32','<f4').reshape(6300,9);receipt=dict(name=name,input_sha256=sha(ip),decoded_sha256=sha(folder/'decoded.f32'))
        for p in folder.iterdir():assert p.resolve().is_relative_to(scratch.resolve()) and p.is_file();p.unlink()
        folder.rmdir();return decoded,receipt
    with cf.ThreadPoolExecutor(4) as pool:cpu=list(pool.map(one,enumerate(network_inputs)))
    ac.WEIGHTS=BASE/'road_viewadapt_20261030_r1/export/model.pt';det=ac.Detector();nn=[]
    for at in range(0,len(network_inputs),8):
        stack=np.stack([ac.preprocess400(a).transpose(2,0,1) for name,a in network_inputs[at:at+8]])
        with torch.inference_mode():gpu=det.model(torch.from_numpy(np.ascontiguousarray(stack)).cuda().float()/255)[0].cpu().numpy()
        for j,g in enumerate(gpu):
            c,r=cpu[at+j];d=np.abs(c-g);assert d.max()<=.001 and d.mean()<=.00002,(r['name'],d.max(),d.mean());nn.append(dict(**r,max_abs=float(d.max()),mean_abs=float(d.mean())))
    posts=Post();views=read(ROOT/'view_predictions.json')[chosen];manifest={r['name']:r for r in rows};post_calls=0
    for r in views:
        m=manifest[r['name']];sensor,full=ac.sensor400(Path(m['data_root'])/'images'/r['name']);p,calls=posts.run(r['detections'],sensor,prove_numpy=True);post_calls+=calls
    result=dict(status='ALLVIEW_KERNEL_AND_NETWORK_PORTABLE_C_PROVED',chosen=chosen,selection_sha256=sha(ROOT/'selected.json'),kernel_tests=tests,actual_c_network_probes=nn,
        c_post_regression_cases=len(views),actual_refiner_calls=post_calls,all_buffer_canaries_source_immutable=True,dll_sha256=sha(out/'enhance.dll'),source_sha256={p.name:sha(p) for p in src.iterdir()},commands=[cmd],hardware_access=False,sd_written=False)
    write(out/'complete.json',result);shutil.copy2(__file__,ROOT/'source'/Path(__file__).name);print('ALLVIEW_PORTABLE_C_PROOF_COMPLETE',chosen,len(nn),len(views),flush=True)
from pathlib import Path
if __name__=='__main__':main()
