"""Prepare exact integer HLS fixtures independently from the frozen W8/A8 model."""
from pathlib import Path
import hashlib,json,shutil
import numpy as np
ROOT=Path('E:/FPGA_Enhance_Work/road_qconv_hls_20261027')
OLD=Path('E:/FPGA_Enhance_Work/road_integer_20261027/m125')
NN=Path('E:/FPGA_Enhance_Work/road_arm_prototype_20261026')
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    ROOT.mkdir(exist_ok=False);fixtures=ROOT/'fixtures';fixtures.mkdir();rows=[]
    for n in ['road_qconv_hls.h','road_qconv_hls.cpp','tb_road_qconv.cpp']:shutil.copy2(HERE/n,ROOT/n)
    q=json.loads((OLD/'quant_graph.json').read_text());g=json.loads((NN/'graph.json').read_text());arrays=np.load(OLD/'quant_arrays.npz')
    blob=(OLD/'qmodel.bin').read_bytes();table=np.frombuffer(blob,'<i4',offset=q['threshold_base'],count=(q['float_base']-q['threshold_base'])//4).copy();table.tofile(fixtures/'model_tables.i32')
    # Deliberately covers repeated transitions and signed branch boundaries.
    synth_table=np.array([-100,-20,-1,20,100,-20,-1,0,20,100],'<i4');synth_table.tofile(fixtures/'synth_tables.i32')
    def one(name,a,w,k,s,unsigned,head,meta,tab,tablefile,rtl=False,oldtrace=None,ws=None,bias=None):
        h,ww,ic=a.shape;oc=w.shape[-1];pad=2 if k==6 else 1 if k==3 else 0;oh=(h+2*pad-k)//s+1;ow=(ww+2*pad-k)//s+1
        folder=fixtures/name;folder.mkdir();a.tofile(folder/'input.u8');groups=(ic+7)//8;blocks=(oc+15)//16
        expanded=np.zeros((k,k,groups*8,blocks*16),np.int8);expanded[:,:,:ic,:oc]=w
        packed=expanded.reshape(k,k,groups,8,blocks,16).transpose(4,0,1,2,5,3).copy();packed.tofile(folder/'weights.bin')
        m=np.zeros((oc,8),'<i4');m[:,:7]=meta;m.tofile(folder/'meta.bin')
        aa=a.astype(np.int32);padded=np.pad(aa,((pad,pad),(pad,pad),(0,0)));acc=np.zeros((oh*ow,oc),np.int32)
        for ky in range(k):
            for kx in range(k):acc+=padded[ky:ky+s*oh:s,kx:kx+s*ow:s].reshape(-1,ic)@w[ky,kx].astype(np.int32)
        if head:
            expected=np.zeros((oh*ow,32),'<i4');expected[:,:oc]=acc
            if oldtrace is not None:
                f=acc.astype(np.float32)*ws[None,:];f=f+bias[None,:];assert f.astype('<f4').tobytes()==oldtrace,'Head independent rawacc/dequant drift'
        else:
            expected=np.zeros((oh*ow,oc),np.int8)
            for c,(split,lb,ln,lo,rb,rn,ro) in enumerate(meta):
                av=acc[:,c];left=lb+np.searchsorted(tab[lo:lo+ln],-av,side='right');right=rb+np.searchsorted(tab[ro:ro+rn],av,side='right');expected[:,c]=np.where(av<=split,left,right)
            if oldtrace is not None:assert expected.tobytes()==oldtrace,'Independent integer output differs from verified C'
        expected.tofile(folder/'expected.bin');counts=[h,ww,ic,oc,k,s,unsigned,int(head),len(tab),len(expected.tobytes())]
        (folder/'shape.txt').write_text(' '.join(map(str,counts))+' '+tablefile+'\n',encoding='ascii')
        rows.append(dict(name=name,shape=counts,table=tablefile,rtl=rtl,independent_reference='NumPy int32 dot bounded below2^31 + sorted threshold upper_count; not HLS implementation',files={p.name:sha(p) for p in folder.iterdir()}))
        print('ROAD_QCONV_FIXTURE',name,flush=True)
    rng=np.random.default_rng(2026102732)
    cases=[('rgb6',(6,8,4,16,6,2,1,False)),('signed_tail3',(5,19,16,32,3,1,0,False)),('ic512_chunk128',(3,5,512,128,1,1,0,False)),('head28_tail',(3,17,16,28,1,1,0,True)),('max_red_chunks',(3,3,128,256,3,2,0,False)),('activation_edges',(1,16,8,16,1,1,0,False))]
    for name,(h,ww,ic,oc,k,s,u,head) in cases:
        a=rng.integers(0,256,(h,ww,ic),dtype=np.uint8) if u else rng.integers(-128,128,(h,ww,ic),dtype=np.int16).astype(np.int8)
        if u:a[:,:,3]=0
        w=rng.integers(-3,4,(k,k,ic,oc),dtype=np.int8)
        if name=='activation_edges':
            a[:]=0;a[0,:,0]=[-128,-101,-100,-21,-20,-13,-12,-11,-1,0,1,19,20,21,99,127];w[:]=0;w[0,0,0,:]=1
        meta=np.tile(np.array([-12,-7,5,0,-2,5,5],np.int32),(oc,1))
        one(name,a,w,k,s,u,head,meta,synth_table,'synth_tables.i32',True)
    photo='02e67bab-27594c1d';traces=globals().get('TRACE_ROOT',OLD/'fast_r1'/photo/'trace')
    for t in g['tensors'][1:]:
        if t['kind']!=1:continue
        p=g['tensors'][t['inputs'][0]];n=q['nodes'][t['id']];ic=p['c4'];oc=t['c4'];k=t['k'];u=p['id']==0
        a=np.fromfile(traces/f'{p["id"]:03d}.f32',np.uint8 if u else np.int8).reshape(p['h'],p['w'],ic)
        cropped=bool(globals().get('CROP_REAL',False))
        if cropped:a=a[:min(p['h'],6 if u else 5),:min(p['w'],8 if u else 19),:].copy()
        w=arrays[f'weight_{t["id"]}'];meta=np.zeros((oc,7),np.int32)
        if not n['head']:
            for c in range(oc):meta[c]=[q['channels'][n['ch_base']+c][key] for key in ['split','lb','ln','lo','rb','rn','ro']]
        one(f'node{t["id"]:02d}',a,w,k,t['s'],int(u),n['head'],meta,table,'model_tables.i32',oldtrace=None if cropped else (traces/f'{t["id"]:03d}.f32').read_bytes(),ws=arrays[f'ws_{t["id"]}'],bias=arrays[f'bias_{t["id"]}'])
    assert len(rows)==66
    (ROOT/'fixtures.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    for mode in ['all','rtl']:(ROOT/f'cases_{mode}.txt').write_text('\n'.join(r['name'] for r in rows if mode=='all' or r['rtl'])+'\n',encoding='ascii')
    setup=f'''set root [file dirname [file normalize [info script]]]
cd $root
open_project qconv_project
set_top road_qconv
add_files road_qconv_hls.cpp -cflags "-std=c++14"
add_files road_qconv_hls.h
add_files -tb tb_road_qconv.cpp -cflags "-std=c++14"
open_solution solution_100mhz -flow_target vivado
set_part {{xc7z020clg400-2}}
create_clock -period 10 -name default
'''
    (ROOT/'csim.tcl').write_text(setup+f'csim_design -O -argv "all {ROOT.as_posix()}"\nputs "ROAD_QCONV_CSIM_COMPLETE"\nexit\n',encoding='ascii')
    (ROOT/'synth.tcl').write_text(setup+'csynth_design\nputs "ROAD_QCONV_SYNTH_COMPLETE"\nexit\n',encoding='ascii')
    (ROOT/'cosim.tcl').write_text('set root [file dirname [file normalize [info script]]]\ncd $root\nopen_project qconv_project\nopen_solution solution_100mhz\n'+f'cosim_design -rtl verilog -tool xsim -trace_level none -argv "rtl {ROOT.as_posix()}"\nputs "ROAD_QCONV_COSIM_COMPLETE"\nexit\n',encoding='ascii')
    protocol=dict(status='EXACT_Q8_HARDWARE_CANDIDATE_NOT_MODEL_PROMOTION',cropped_real_inputs=bool(globals().get('CROP_REAL',False)),part='xc7z020clg400-2',clock_ns=10,pe=16,simd=8,chunk=64,cases=len(rows),real_layers=60,rtl_cases=6,quant_model_sha256=sha(OLD/'qmodel.bin'),source_sha256={n:sha(ROOT/n) for n in ['road_qconv_hls.cpp','road_qconv_hls.h','tb_road_qconv.cpp']},warning='The quant models lost night accuracy; arithmetic reference only. Independent quality gates and routed board timing remain required. 128 parallel MACs is a design target, not achieved FPS.',hardware_access=False,sd_written=False)
    (ROOT/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8');print('ROAD_QCONV_66_FIXTURES_READY',flush=True)
if __name__=='__main__':main()
