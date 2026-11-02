"""Freeze arithmetic/ports, audit MACs, generate independently referenced layer fixtures."""
from pathlib import Path
import os,shutil,subprocess,collections,time
import numpy as np
from road_arm_common import ROOT as NN,read,write,sha
ROOT=Path('E:/FPGA_Enhance_Work/road_conv_hls_20261027')
HERE=Path(__file__).resolve().parent
GCC=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe')

def main():
    ROOT.mkdir(exist_ok=False);start=time.monotonic();g=read(NN/'graph.json');rows=[]
    for t in g['tensors'][1:]:
        if t['kind']!=1:continue
        p=g['tensors'][t['inputs'][0]];mac=t['h']*t['w']*t['c']*p['c']*t['k']**2
        rows.append(dict(id=t['id'],name=t['name'],height=p['h'],width=p['w'],ic=p['c'],ic4=p['c4'],oc=t['c'],oc4=t['c4'],oh=t['h'],ow=t['w'],kernel=t['k'],stride=t['s'],mac=mac,
           input_bytes=p['elements']*4,output_bytes=t['elements']*4,weights_bytes=t['k']**2*p['c4']*t['c4']*4))
    total=sum(r['mac'] for r in rows);byk={str(k):sum(r['mac'] for r in rows if r['kernel']==k) for k in [1,3,6]};assert total==517657600 and byk['3']==309657600
    eligible=[r for r in rows if r['kernel']==3 and r['ic4']<=128 and r['oc4']%8==0 and r['oh']<=80 and r['ow']<=80];assert sum(r['mac'] for r in eligible)==byk['3']
    write(ROOT/'layer_budget.json',dict(status='STATIC_MAC_AUDIT_NOT_LAYER_WALLTIME_PROFILE',total_conv_mac=total,by_kernel_mac=byk,prototype_coverage_mac=byk['3'],coverage_fraction=byk['3']/total,layers=sorted(rows,key=lambda r:r['mac'],reverse=True),
       current_routed_resource=dict(LUT=40115,LUT_total=53200,DSP=163,DSP_total=220,BRAM36_tiles=71,BRAM36_total=140,occupied_slices=13224,slices_total=13300),
       warning='HLS estimates do not prove placement alongside current nearly-fullSlice design. MACfraction is not runtimefraction. No board profiling or modification in this phase.'))
    write(ROOT/'protocol.json',dict(status='FROZEN_BEFORE_HLS_SIMULATION_AND_SYNTHESIS',target='xc7z020clg400-2',clock_ns=10,variants=[8,4],primary=8,
       arithmetic='FP32 separate multiply/add helperfunctions, bias-first ordered ky,kx,ic4 reduction. No quantization. IPproduces pre-SiLU outputs; originalCPU SiLU remains outside.',
       shape='3x3 pad1, stride1/2, IH/IW1..160, OH/OW<=80, IC4<=128 divisible4, OC4<=256 divisiblePE. Invalidconfig returns withoutwriting output.',
       tiling='16horizontal positions interleaved tohideFPadditionrecurrence; input3x33x128 patchcache, peroutputblock packed bias+weights.',
       selection='EvaluateP8 first; P4 is lowerresource fallback if P8 fails scheduling/resource feasibility. No quality tuning; same model tensors.',
       numerical_tolerance='2e-5 +2e-5*abs(reference), count bitdifferences. Finite normal-range modeldata; no completeIEEEexception/subnormal claim.',
       references=['https://docs.amd.com/r/2023.1-English/ug1399-vitis-hls/pragma-HLS-dependence','https://docs.amd.com/api/khub/documents/5LkZXrIZ66WTiiJ~nfh5~A/content'],
       source_weights_sha256=sha(NN/'weights.f32'),sd_write=False,hardware_access=False))
    shutil.copy2(HERE/'road_conv3_reference.c',ROOT/'road_conv3_reference.c');env=os.environ.copy();env['PATH']=str(GCC.parent)+os.pathsep+env.get('PATH','')
    cmd=[str(GCC),'-O3','-std=c99','-msse2','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror',str(ROOT/'road_conv3_reference.c'),'-o',str(ROOT/'reference.exe'),'-lm']
    run=subprocess.run(cmd,env=env,capture_output=True,text=True);(ROOT/'reference_build.log').write_text(run.stdout+run.stderr);assert run.returncode==0,run.stderr
    fullweights=np.fromfile(NN/'weights.f32','<f4');fixtures=[];rng=np.random.default_rng(2026102717);base=ROOT/'fixtures';base.mkdir()
    def one(name,a,w,b,s,origin=None,after=None,rtl=False):
        h,ww,ic=a.shape;oc=len(b);assert w.shape==(3,3,ic,oc) and oc%8==0
        f=base/name;f.mkdir();a.astype('<f4').tofile(f/'input.f32');w.astype('<f4').tofile(f/'weights.f32');b.astype('<f4').tofile(f/'bias.f32')
        (f/'shape.txt').write_text(f'{h} {ww} {ic} {oc} {s}\n',encoding='ascii')
        for pe in [8,4]:
            packed=np.empty((oc//pe,9*ic+1,pe),'<f4')
            for block in range(oc//pe):packed[block,0]=b[block*pe:block*pe+pe];packed[block,1:]=w.reshape(9*ic,oc)[:,block*pe:block*pe+pe]
            packed.tofile(f/f'packed_p{pe}.f32')
            restored=np.empty_like(w).reshape(9*ic,oc)
            for block in range(oc//pe):restored[:,block*pe:block*pe+pe]=packed[block,1:]
            assert restored.tobytes()==w.tobytes()
        args=[str(ROOT/'reference.exe'),str(h),str(ww),str(ic),str(oc),str(s),str(f/'input.f32'),str(f/'weights.f32'),str(f/'bias.f32'),str(f/'expected.f32')]
        if after is not None:args.append(str(f/'expected_silu.f32'))
        p=subprocess.run(args,capture_output=True,text=True,check=True);assert 'SCALAR_FP32_SINGLE_CONV_REFERENCE_DONE' in p.stdout
        delta=None
        if after is not None:
            got=np.fromfile(f/'expected_silu.f32','<f4');delta=float(abs(got-after.ravel()).max());assert np.array_equal(got,after.ravel()),(name,delta)
        row=dict(name=name,h=h,w=ww,ic4=ic,oc4=oc,stride=s,rtl=rtl,origin=origin,scalar_reference_stdout=p.stdout.strip(),post_silu_original_tensor_bytes_exact=after is not None,post_silu_max_abs=delta,
           files={p.name:sha(p) for p in f.iterdir() if p.is_file()});fixtures.append(row);print('CONV3_REFERENCE_FIXTURE_READY',name,delta,flush=True)
    def rnd(h,w,ic,oc,s,name,rtl=True):one(name,rng.uniform(-1,1,(h,w,ic)).astype(np.float32),rng.uniform(-.15,.15,(3,3,ic,oc)).astype(np.float32),rng.uniform(-.2,.2,oc).astype(np.float32),s,rtl=rtl)
    one('zero_bias',np.zeros((3,5,4),np.float32),rng.normal(0,.1,(3,3,4,8)).astype(np.float32),np.linspace(-.5,.5,8,dtype=np.float32),1,rtl=False)
    rnd(5,19,4,16,1,'cross_tile',True);rnd(7,9,8,8,2,'odd_stride2',True);rnd(3,3,128,8,1,'max_input_channels',True);rnd(1,1,4,256,1,'max_output_channels',True)
    fixture_names=[r['name'] for r in read(NN/'export_complete.json')['fixtures'] if r['kind']=='validation']
    for node in [2,10,21,35,5,79]:
        t=g['tensors'][node];p=g['tensors'][t['inputs'][0]];which=fixture_names[0];a=np.fromfile(NN/'host_r2'/which/'trace'/f'{p["id"]:03d}.f32','<f4').reshape(p['h'],p['w'],p['c4'])
        w=fullweights[t['woff']:t['woff']+9*p['c4']*t['c4']].reshape(3,3,p['c4'],t['c4']);b=fullweights[t['boff']:t['boff']+t['c4']]
        after=np.fromfile(NN/'host_r2'/which/'trace'/f'{node:03d}.f32','<f4');one(f'real_node{node:02d}',a,w,b,t['s'],origin=dict(model_node=node,photo=which),after=after)
    write(ROOT/'fixtures.json',fixtures);(ROOT/'cases_all.txt').write_text('\n'.join(f['name'] for f in fixtures)+'\n');(ROOT/'cases_rtl.txt').write_text('\n'.join(f['name'] for f in fixtures if f['rtl'])+'\n')
    shutil.copy2(NN/'YOLOv5_LICENSE',ROOT/'YOLOv5_LICENSE')
    for pe in [8,4]:
        d=ROOT/f'p{pe}';d.mkdir()
        for name in ['road_conv3_hls.cpp','road_conv3_hls.h','tb_road_conv3.cpp']:shutil.copy2(HERE/name,d/name)
        for name in ['cases_all.txt','cases_rtl.txt']:shutil.copy2(ROOT/name,d/name)
        shutil.copytree(base,d/'fixtures')
        init=f'''set root [file dirname [file normalize [info script]]]
cd $root
open_project conv_project
set_top road_conv3_fp32
add_files road_conv3_hls.cpp -cflags "-std=c++14 -DRC_PE={pe} -ffp-contract=off -fno-fast-math"
add_files road_conv3_hls.h
add_files -tb tb_road_conv3.cpp -cflags "-std=c++14 -DRC_PE={pe} -ffp-contract=off -fno-fast-math"
open_solution solution_100mhz -flow_target vivado
set_part {{xc7z020clg400-2}}
create_clock -period 10 -name default
'''
        (d/'csim.tcl').write_text(init+'csim_design -argv "all"\nputs "ROAD_CONV3_CSIM_COMPLETE_P'+str(pe)+'"\nexit\n',encoding='ascii')
        (d/'synth.tcl').write_text(init+'csynth_design\nputs "ROAD_CONV3_SYNTH_COMPLETE_P'+str(pe)+'"\nexit\n',encoding='ascii')
        (d/'cosim.tcl').write_text('set root [file dirname [file normalize [info script]]]\ncd $root\nopen_project conv_project\nopen_solution solution_100mhz\ncosim_design -rtl verilog -tool xsim -trace_level none -argv "rtl"\nputs "ROAD_CONV3_COSIM_COMPLETE_P'+str(pe)+'"\nexit\n',encoding='ascii')
        (d/'export.tcl').write_text('set root [file dirname [file normalize [info script]]]\ncd $root\nopen_project conv_project\nopen_solution solution_100mhz\nexport_design -format ip_catalog -rtl verilog -vendor fpga.user -library hls -version 1.0 -ipname road_conv3_p'+str(pe)+'\nputs "ROAD_CONV3_EXPORT_COMPLETE_P'+str(pe)+'"\nexit\n',encoding='ascii')
    write(ROOT/'prepare_complete.json',dict(status='FP32_LAYER_REFERENCES_AND_P8_P4_HLS_PROJECTS_READY',fixtures=len(fixtures),rtl_fixtures=4,seconds=time.monotonic()-start,hardware_access=False))
    print('ROAD_CONV3_HLS_PROJECTS_PREPARED',len(fixtures),flush=True)
if __name__=='__main__':main()
