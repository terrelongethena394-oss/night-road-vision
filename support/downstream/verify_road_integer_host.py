"""Compile actual int32/NEON-compatible C; compare every tensor to CUDA integer reference."""
import os,shutil,subprocess,time,sys
from pathlib import Path
import numpy as np
from road_integer_common import ROOT,FLOAT,read,write,sha
from road_integer_reference import IntegerReference,torch
HERE=Path(__file__).resolve().parent
GCC=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe')

def main():
    tag=sys.argv[1] if len(sys.argv)>1 else 'm110';folder=ROOT/tag
    source=folder/'source';source.mkdir(exist_ok=False);host=folder/'host';host.mkdir()
    old=(FLOAT/'source_r2/road_fp32.c').read_text()
    prefix=old[old.index('static float sigmoid'):old.index('void road_input320')]
    suffix=old[old.index('void road_decode'):]
    code='/* GPL-3.0; YOLOv5 v7.0 lowered integer Conv/A8 with FP32 decode. */\n#include "road_fp32.h"\n#include <math.h>\n#include <stdlib.h>\n#include <string.h>\n'+prefix+(HERE/'road_q8_kernel.inc').read_text()+suffix
    (source/'road_q8.c').write_text(code,encoding='ascii')
    for name in ['road_graph.h','road_q8_tables.h']:shutil.copy2(folder/name,source/name)
    shutil.copy2(FLOAT/'source_r2/road_fp32.h',source/'road_fp32.h')
    for name in ['road_fp32_host.c','road_fp32_unit.c']:shutil.copy2(HERE/name,source/name)
    env=os.environ.copy();env['PATH']=str(GCC.parent)+os.pathsep+env.get('PATH','');commands=[]
    flags=['-O3','-std=c99','-msse2','-ffp-contract=off','-fno-fast-math','-Wall','-Wextra','-Werror','-I'+str(source)]
    for tag2,extras in [('simd',[]),('scalar',['-DROAD_FORCE_SCALAR=1']),('ap',['-DROAD_HOST_CONFIDENCE=.001f']),('unit',[])]:
        exe=host/('road_'+tag2+'.exe');harness='road_fp32_unit.c' if tag2=='unit' else 'road_fp32_host.c'
        cmd=[str(GCC),*flags,*extras,str(source/'road_q8.c'),str(source/harness),'-o',str(exe),'-lm']
        p=subprocess.run(cmd,env=env,capture_output=True,text=True);(host/('build_'+tag2+'.log')).write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr;commands.append(cmd)
    p=subprocess.run([str(host/'road_unit.exe')],capture_output=True,text=True,check=True);assert 'FIXTURES_PASS' in p.stdout
    write(host/'unit_complete.json',dict(stdout=p.stdout,status='UNCHANGED_NMS_AND_COORDINATE_UNIT_CONTROLS_PASS'))
    model=IntegerReference(folder);g=model.g;fixtures=read(FLOAT/'export_complete.json')['fixtures'];proofs=[]
    for fixture in fixtures:
        name=fixture['name'];case=FLOAT/'cases'/name;out=host/name;out.mkdir();tr=out/'trace';tr.mkdir();gold=out/'gold';gold.mkdir();start=time.monotonic()
        rgb=np.fromfile(case/'input320.rgb',np.uint8).reshape(320,320,3)
        def trace(i,v):
            t=g['tensors'][i];a=v.cpu().numpy()[0].transpose(1,2,0);dtype='<f4' if i in g['heads'] else 'u1' if i==0 else 'i1'
            padded=np.zeros((t['h'],t['w'],t['c4']),dtype);padded[:,:,:t['c']]=a;padded.tofile(gold/f'{i:03d}.bin')
        decoded=model.forward(torch.from_numpy(rgb.transpose(2,0,1)[None].copy()),trace).cpu().numpy()[0]
        decoded.astype('<f4').tofile(gold/'decoded.f32')
        p=subprocess.run([str(host/'road_simd.exe'),str(folder/'qmodel.bin'),str(case/'input400.u32'),str(out),str(tr)],capture_output=True,text=True)
        assert p.returncode==0 and 'ROAD_FP32_HOST_DONE' in p.stdout,(p.returncode,p.stdout,p.stderr)
        assert (out/'input320.rgb').read_bytes()==(case/'input320.rgb').read_bytes();checks=[]
        for t in g['tensors']:
            i=t['id'];got=(tr/f'{i:03d}.f32').read_bytes();expected=(gold/f'{i:03d}.bin').read_bytes()
            assert len(got)==len(expected),i
            if i not in g['heads']:assert got==expected,(name,i,int(np.count_nonzero(np.frombuffer(got,np.uint8)!=np.frombuffer(expected,np.uint8))));checks.append(dict(id=i,bytes_exact=True,bytes=len(got)))
            else:
                a=np.frombuffer(got,'<f4');b=np.frombuffer(expected,'<f4');delta=abs(a-b);assert np.all(delta<=2e-5+2e-6*abs(b)),(name,i,float(delta.max()))
                checks.append(dict(id=i,max_abs=float(delta.max())))
        got=np.fromfile(out/'decoded.f32','<f4').reshape(-1,9);delta=abs(got-decoded)
        assert delta[:,:4].max()<.003 and delta[:,4:].max()<2e-5,(name,delta.max())
        # Independent PyTorch NMS against unchanged C NMS at operating threshold.
        from road_integer_reference import non_max_suppression,scale_boxes
        from verify_road_arm_host import compare_boxes
        pred=non_max_suppression(torch.from_numpy(decoded[None].copy()),.25,.6,max_det=300)[0]
        if len(pred):scale_boxes((320,320),pred[:,:4],(240,400),ratio_pad=((.8,.8),(0.,64.)))
        actual=np.fromfile(out/'boxes400.f32','<f4').reshape(-1,6);boxproof=compare_boxes(actual,pred.numpy(),.004)
        proofs.append(dict(name=name,all_tensors=checks,decoded_coordinate_max_abs=float(delta[:,:4].max()),decoded_confidence_max_abs=float(delta[:,4:].max()),boxes=boxproof,host_stdout=p.stdout.strip(),seconds=time.monotonic()-start))
        write(out/'proof.json',proofs[-1]);print('INTEGER_C_ALL86_PASS',tag,name,boxproof['count'],flush=True)
    scalar=[]
    for name in [fixtures[0]['name'],'control_random']:
        out=host/(name+'_scalar');out.mkdir();p=subprocess.run([str(host/'road_scalar.exe'),str(folder/'qmodel.bin'),str(FLOAT/'cases'/name/'input400.u32'),str(out)],capture_output=True,text=True,check=True)
        assert (out/'decoded.f32').read_bytes()==(host/name/'decoded.f32').read_bytes();scalar.append(dict(name=name,decoded_bytes_exact=True))
    write(folder/'host_complete.json',dict(status='INTEGER_C_ALL86_TENSORS_AND_FLOAT_DECODE_NMS_PROVEN_ON_HOST',fixtures=proofs,scalar_vs_sse2=scalar,commands=commands,
           model_sha256=sha(folder/'qmodel.bin'),source_sha256={p.name:sha(p) for p in source.iterdir()},arm_neon_not_executed=True,no_hardware_access=True,no_sd_write=True))
    print('INTEGER_C_HOST_COMPLETE',tag,flush=True)
if __name__=='__main__':main()
