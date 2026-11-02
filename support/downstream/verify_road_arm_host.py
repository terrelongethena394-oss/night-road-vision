"""Compile real C and check all86 tensors, decoder, NMS and preprocessing."""
import os,shutil,subprocess,time,sys
from pathlib import Path
import numpy as np
from road_arm_common import ROOT,read,write,sha
HERE=Path(__file__).resolve().parent
GCC=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe')

def compare_boxes(actual,expected,coordinate_atol):
    assert actual.shape==expected.shape,(actual.shape,expected.shape)
    remaining=set(range(len(actual)));maxcoord=0.;maxscore=0.
    for e in expected:
        candidates=[i for i in remaining if actual[i,5]==e[5]];assert candidates
        i=min(candidates,key=lambda j:float(np.abs(actual[j,:4]-e[:4]).max()));a=actual[i];remaining.remove(i)
        coord=float(np.abs(a[:4]-e[:4]).max());score=float(abs(a[4]-e[4]));assert coord<=coordinate_atol and score<=2e-4,(a.tolist(),e.tolist(),coord,score)
        maxcoord=max(maxcoord,coord);maxscore=max(maxscore,score)
    return dict(count=len(actual),max_coordinate_error=maxcoord,max_score_error=maxscore,classes_exact=True)

def main():
    export=read(ROOT/'export_complete.json');graph=read(ROOT/'graph.json')
    assert sha(ROOT/'weights.f32')==export['weights_sha256']
    revision=('_'+sys.argv[1]) if len(sys.argv)>1 and sys.argv[1] in ['r1','r2'] else ''
    host=ROOT/('host'+revision);host.mkdir(exist_ok=False);source=ROOT/('source'+revision);source.mkdir(exist_ok=True)
    for name in ['road_fp32.h','road_fp32.c','road_fp32_host.c','road_fp32_unit.c']:shutil.copy2(HERE/name,source/name)
    shutil.copy2(ROOT/'road_graph.h',source/'road_graph.h')
    env=os.environ.copy();env['PATH']=str(GCC.parent)+os.pathsep+env.get('PATH','');commands=[]
    flags=['-O3','-std=c99','-msse2','-ffp-contract=off','-fno-fast-math','-Wall','-Wextra','-Werror','-I'+str(source)]
    for name,extras in [('simd',[]),('scalar',['-DROAD_FORCE_SCALAR=1'])]:
        command=[str(GCC),*flags,*extras,str(source/'road_fp32.c'),str(source/'road_fp32_host.c'),'-o',str(host/('road_'+name+'.exe')),'-lm']
        p=subprocess.run(command,env=env,capture_output=True,text=True);(host/('build_'+name+'.log')).write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr;commands.append(command)
    command=[str(GCC),*flags,str(source/'road_fp32.c'),str(source/'road_fp32_unit.c'),'-o',str(host/'unit.exe'),'-lm']
    p=subprocess.run(command,env=env,capture_output=True,text=True);assert p.returncode==0,p.stderr;commands.append(command)
    p=subprocess.run([str(host/'unit.exe')],capture_output=True,text=True,check=True);assert 'FIXTURES_PASS' in p.stdout
    write(host/'unit_complete.json',dict(status='CLASS_AWARE_NMS_SCORE_THRESHOLD_AND_COORDINATE_CLIP_FIXTURES_PASS',stdout=p.stdout.strip()))
    records=[]
    for fixture in export['fixtures']:
        name=fixture['name'];case=ROOT/'cases'/name;out=host/name;out.mkdir();trace=out/'trace';trace.mkdir();start=time.monotonic()
        p=subprocess.run([str(host/'road_simd.exe'),str(ROOT/'weights.f32'),str(case/'input400.u32'),str(out),str(trace)],capture_output=True,text=True)
        assert p.returncode==0 and 'ROAD_FP32_HOST_DONE' in p.stdout,(p.returncode,p.stderr,p.stdout)
        assert (out/'input320.rgb').read_bytes()==(case/'input320.rgb').read_bytes()
        errors=[]
        for t in graph['tensors']:
            got=np.fromfile(trace/f'{t["id"]:03d}.f32',dtype='<f4');gold=np.fromfile(case/'golden'/f'{t["id"]:03d}.f32',dtype='<f4')
            assert got.size==gold.size==t['elements'] and np.isfinite(got).all()
            err=np.abs(got-gold);maximum=float(err.max(initial=0));bad=err>(1e-4+1e-4*np.abs(gold))
            assert not bad.any(),(name,t['id'],t['name'],maximum,int(bad.sum()))
            errors.append(dict(id=t['id'],name=t['name'],max_abs=maximum,mae=float(err.mean())))
        decoded=np.fromfile(out/'decoded.f32',dtype='<f4').reshape(-1,9);gold=np.fromfile(case/'decoded.f32',dtype='<f4').reshape(-1,9)
        delta=np.abs(decoded-gold);assert delta[:,:4].max()<=.02 and delta[:,4:].max()<=2e-4
        boxes={suffix:compare_boxes(np.fromfile(out/(suffix+'.f32'),'<f4').reshape(-1,6),np.fromfile(case/(suffix+'.f32'),'<f4').reshape(-1,6),.04 if suffix=='boxes400' else .03) for suffix in ['boxes320','boxes400']}
        row=dict(name=name,all_layers=errors,preprocessing_bytes_exact=True,decoded_box_max_abs=float(delta[:,:4].max()),decoded_score_max_abs=float(delta[:,4:].max()),boxes=boxes,host_wall_seconds=time.monotonic()-start)
        records.append(row);write(out/'proof.json',row)
        print('ROAD_HOST_ALL86_TENSORS_PASS',name,'max',max(x['max_abs'] for x in errors),'boxes',boxes['boxes400']['count'],flush=True)
    # Independent scalar C accumulation against vectorized SSE2 on real and random inputs.
    scalar=[]
    for name in [export['fixtures'][0]['name'],'control_random']:
        case=ROOT/'cases'/name;out=host/(name+'_scalar');out.mkdir()
        p=subprocess.run([str(host/'road_scalar.exe'),str(ROOT/'weights.f32'),str(case/'input400.u32'),str(out)],capture_output=True,text=True,check=True)
        assert 'ROAD_FP32_HOST_DONE' in p.stdout
        a=np.fromfile(out/'decoded.f32','<f4');b=np.fromfile(host/name/'decoded.f32','<f4');assert np.array_equal(a,b),(name,float(abs(a-b).max()))
        scalar.append(dict(name=name,decoded_floats=len(a),all_bytes_exact=True))
    write(ROOT/('host_complete'+revision+'.json'),dict(status='C_FP32_ALL_LAYERS_DECODER_NMS_COORDINATES_VERIFIED',fixtures=records,scalar_simd=scalar,
          commands=commands,source_sha256={p.name:sha(p) for p in source.iterdir() if p.is_file()},weights_sha256=sha(ROOT/'weights.f32'),
          dtype='CPU FP32',host_vector='SSE2',arm_neon_run=False,board_downloaded=False,sd_written=False))
    print('ROAD_HOST_VERIFICATION_COMPLETE',len(records),flush=True)
if __name__=='__main__':main()
