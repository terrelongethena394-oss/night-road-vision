"""Whole-network integration against independent unchanged86-tensor references."""
from pathlib import Path
import shutil,subprocess,os,re
import numpy as np
from prepare_fp32_cpu_pack import BASE,NN,CURRENT,HERE,read,write,sha
from prepare_road_conv13 import ROOT as HLS,GCC
ROOT=BASE/'road_conv13_runtime_20261028_r1'
REF=BASE/'road_roi_spatial_verifier_20261028'
PE=8
VERSION=17

def main():
    ROOT.mkdir(exist_ok=False)
    app=ROOT/'firmware';shutil.copytree(CURRENT,app,ignore=shutil.ignore_patterns('physical_r1','static_readback','obj','*.log'))
    src=app/'source';g=read(NN/'graph.json');ts=g['tensors'];policy=read(HLS/'protocol.json')
    old=set(policy['existing_selected_3x3_nodes']);new=set(policy['pointwise_nodes']);eligible=old|new
    rows=[];packed=bytearray();weights=np.fromfile(CURRENT/'runtime/weights.f32','<f4')
    for t in ts:
        n=t['id']
        if n not in eligible:rows.append((0,0,0));continue
        i=ts[t['inputs'][0]];red=t['k']*t['k']*i['c4'];oc=t['c4'];offset=(len(packed)+63)//64*64;packed.extend(bytes(offset-len(packed)))
        assert oc%PE==0 and (i['offset']*4)%64==(t['offset']*4)%64==0
        w=weights[t['woff']:t['woff']+red*oc].reshape(red,oc);bias=weights[t['boff']:t['boff']+oc];p=np.empty((oc//PE,red+1,PE),'<f4')
        for b in range(oc//PE):p[b,0]=bias[b*PE:b*PE+PE];p[b,1:]=w[:,b*PE:b*PE+PE]
        raw=p.tobytes();packed.extend(raw);rows.append((offset,len(raw),int(n in old)))
        assert i['offset']+i['elements']<=t['offset'] or t['offset']+t['elements']<=i['offset']
    assert 0x18000000+len(packed)<0x19000000
    (ROOT/'independent_packed.bin').write_bytes(packed)
    h='#ifndef ROAD_PL_LAYOUT_H\n#define ROAD_PL_LAYOUT_H\n#define ROAD_PL_PACKED_BYTES %dU\ntypedef struct {unsigned offset,bytes,selected;} RoadPLLayout;\nstatic const RoadPLLayout ROAD_PL_LAYOUT[ROAD_TENSORS]={\n'%len(packed)
    h+='\n'.join('{%dU,%dU,%dU},'%r for r in rows)+'\n};\n#endif\n';(src/'road_pl_layout.h').write_text(h,encoding='ascii')
    c=(src/'road_conv3_pack.c').read_text().replace('int road_pack_conv3(','int road_pack_conv13(').replace('int pe,float *dst','int pe,int kernel,float *dst').replace('ic4>128','ic4>(kernel==1?512:128)').replace('if(!weights','if((kernel!=1&&kernel!=3)||!weights').replace('9*ic4','kernel*kernel*ic4');(src/'road_conv3_pack.c').write_text(c,encoding='ascii')
    c=(src/'road_pl.c').read_text().replace('int road_pack_conv3(const float *,const float *,int,int,int,float *,size_t);','int road_pack_conv13(const float *,const float *,int,int,int,int,float *,size_t);')
    c=c.replace('road_pack_conv3(weights+op->wo,weights+op->bo,in->c4,out->c4,8,','road_pack_conv13(weights+op->wo,weights+op->bo,in->c4,out->c4,8,op->k,')
    c=c.replace('unsigned road_pl_host_calls;','unsigned road_pl_host_calls;\nstatic int host_mode=2;\nvoid road_pl_host_set_mode(int mode){host_mode=mode;}')
    c=c.replace('if(op->k!=3||!ROAD_PL_LAYOUT[node].bytes)return 0;','if((op->k!=1&&op->k!=3)||!ROAD_PL_LAYOUT[node].bytes)return 0;\n#ifdef ROAD_PL_EMULATE\n if(host_mode==0 || (host_mode==1 && !ROAD_PL_LAYOUT[node].selected))return 0;\n#endif')
    c=c.replace('9U*in->c4+1U','(unsigned)(op->k*op->k)*in->c4+1U').replace('ky<3','ky<op->k').replace('kx<3','kx<op->k').replace('y*op->s+ky-1','y*op->s+ky-op->p').replace('x*op->s+kx-1','x*op->s+kx-op->p').replace('(ky*3+kx)','(ky*op->k+kx)')
    needle='wr(XROAD_CONV3_FP32_CONTROL_ADDR_STRIDE_DATA,(unsigned)op->s);';assert needle in c
    c=c.replace(needle,needle+'wr(XROAD_CONV3_FP32_CONTROL_ADDR_KERNEL_DATA,(unsigned)op->k);')
    if PE==16:
        c=c.replace('out->c4,8,op->k','out->c4,16,op->k').replace('block=c/8,lane=c%8','block=c/16,lane=c%16').replace('8U','16U')
        pack=(src/'road_conv3_pack.c').read_text().replace('(pe!=4&&pe!=8)','(pe!=4&&pe!=8&&pe!=16)');(src/'road_conv3_pack.c').write_text(pack,encoding='ascii')
    (src/'road_pl.c').write_text(c,encoding='ascii')
    c=(src/'road_camera_main.c').read_text().replace('m[M_VERSION]=15;','m[M_VERSION]=17;').replace('[72]=1U;','[72]=2U;').replace('ROAD_ROI_EXPERIMENT_READY V15','ROAD_CONV13_READY V17')
    c=c.replace(' RoadEnhanceStats es;',' m[132]=m[72];\n RoadEnhanceStats es;',1)
    oldtrace='static void trace(int id,const float *data,uint32_t n,void *p){(void)id;(void)p;memcpy((void *)(RC_TRACE+trace_cursor),data,n*4U);trace_cursor+=n*4U;}'
    trace='static XTime profile_previous;\nstatic void trace(int id,const float *data,uint32_t n,void *p){XTime t=now();(void)p;if(m[M_TRACE_ENABLE]==2U){if(id)((volatile uint64_t *)0x17400000U)[id]=t-profile_previous;profile_previous=t;return;}memcpy((void *)(RC_TRACE+trace_cursor),data,n*4U);trace_cursor+=n*4U;}'
    assert oldtrace in c;c=c.replace(oldtrace,trace).replace(' Xil_DCacheFlushRange(RC_ROI_INPUT',' Xil_DCacheFlushRange(0x17400000U,696U);\n Xil_DCacheFlushRange(RC_ROI_INPUT',1);(src/'road_camera_main.c').write_text(c,encoding='ascii')
    if VERSION!=17:
        c=c.replace('m[M_VERSION]=17;',f'm[M_VERSION]={VERSION};').replace('ROAD_CONV13_READY V17',f'ROAD_CONV13_READY V{VERSION}');(src/'road_camera_main.c').write_text(c,encoding='ascii')
    c=(HERE/'road_fp32_host.c').read_text().replace('#include "road_fp32.h"','#include "road_fp32.h"\n#include "road_pl.h"\nextern unsigned road_pl_host_calls;\nvoid road_pl_host_set_mode(int);\nconst float *road_pl_host_packed(void);')
    c=c.replace('road_preprocess400(raw,rgb);','road_pl_host_set_mode(atoi(getenv("ROAD_PL_HOST_MODE")));if(road_pl_prepare(weights))return 20;road_pl_begin();\n  road_preprocess400(raw,rgb);')
    c=c.replace('free(weights);free(arena);','printf("CONV13_HOST_CALLS=%u\\n",road_pl_host_calls);\n  snprintf(path,sizeof(path),"%s/packed.bin",argv[3]);if(writefile(path,road_pl_host_packed(),ROAD_PL_PACKED_BYTES))return 22;\n  free(weights);free(arena);')
    c=c.replace('#include "road_pl.h"','#include "road_pl.h"\n#include "road_pl_layout.h"',1)
    (src/'conv13_host.c').write_text(c,encoding='ascii')
    host=ROOT/'host';host.mkdir();env=os.environ.copy();env['PATH']=str(GCC.parent)+';'+env['PATH']
    cmd=list(map(str,[GCC,'-O3','-std=c99','-msse2','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror','-DROAD_PL_EMULATE','-I'+str(src),*[src/n for n in ['road_fp32.c','road_pl.c','road_conv3_pack.c','conv13_host.c']],'-lm','-o',host/'conv13_host.exe']))
    p=subprocess.run(cmd,capture_output=True,text=True,env=env);(host/'build.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
    records=[]
    for mode in [1,2]:
        env['ROAD_PL_HOST_MODE']=str(mode)
        for view in ['full','roi']:
            parent=REF/('native_detector_'+view)
            for case in read(parent/'complete.json')['cases']:
                name=case['name'];dest=host/f'{mode}_{view}_{name}';dest.mkdir();trace=dest/'trace';trace.mkdir()
                p=subprocess.run([str(host/'conv13_host.exe'),str(app/'runtime/weights.f32'),str(parent/'cases'/name/'input400.u32'),str(dest),str(trace)],capture_output=True,text=True,env=env)
                assert p.returncode==0 and f'CONV13_HOST_CALLS={12 if mode==1 else 51}' in p.stdout,(name,p.stdout,p.stderr)
                assert (dest/'packed.bin').read_bytes()==packed
                for tid in range(86):assert (trace/f'{tid:03d}.f32').read_bytes()==(parent/'cases'/name/'host/trace'/f'{tid:03d}.f32').read_bytes(),(mode,view,name,tid)
                for n in ['decoded.f32','boxes400.f32']:assert (dest/n).read_bytes()==(parent/'cases'/name/'host'/n).read_bytes(),(mode,view,name,n)
                records.append(dict(mode=mode,view=view,name=name,all86_and_outputs_byte_exact=True))
                print('CONV13_WHOLE86_EXACT',mode,view,name,flush=True)
    write(ROOT/'host_complete.json',dict(status='BOTH_MODES_ALL16_ALL86_AND_PACKING_BYTE_EXACT',cases=records,packed_bytes=len(packed),packed_sha256=sha(ROOT/'independent_packed.bin'),command=cmd,sd_written=False))
    write(ROOT/'protocol.json',dict(status='NATIVE_COMPLETE_WAIT_HLS_ROUTED_BIT',version=VERSION,pe=PE,mode1='Original12 selected3x3 on shared newcore',mode2='Original12 selected3x3 plus39pointwise onshared core',default=2,selected_3x3=sorted(old),pointwise=sorted(new),packed_addr=0x18000000,packed_bytes=len(packed),profile_addr=0x17400000,sd_written=False))

if __name__=='__main__':main()
