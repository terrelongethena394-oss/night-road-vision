"""Integer display guard on unchanged ABI31 neural/PL pipeline, RAM candidate."""
from pathlib import Path
import ctypes as ct,os,shutil,struct,subprocess
import numpy as np
from car_roi_delivery_common import BASE,read,write,sha
from camera_snapshot_tools import fnv,words,rgb
from natural_guard_lab import ROOT,CASES,PROFILES,table,apply

OLD=BASE/'camera_station_abi31_20261031'

def main():
    assert not (ROOT/'build_verified.json').exists()
    profile=PROFILES['natural55'];lut=table(profile);fingerprint=fnv(lut.tobytes())
    write(ROOT/'selection.json',dict(status='NATURAL55_FROZEN_BEFORE_ARM_TESTS',profile=profile,lut_fnv=fingerprint,
        reason='Manual inspection of two computer prototypes on four exposed diagnostic cases; retain visibility with less extreme shadow amplification.',
        quality_scope='Exposed-case visual engineering selection, not independent PSNR/SSIM or detection accuracy evidence.',model_changed=False,detector_changed=False,sd_written=False))
    app=ROOT/'firmware';shutil.copytree(OLD/'firmware',app);src=app/'source';headers=',\n '.join(','.join(str(int(v)) for v in lut[i:i+16]) for i in range(0,256,16))
    header=f'''#ifndef ROAD_NATURAL_GUARD_H
#define ROAD_NATURAL_GUARD_H
#include <stdint.h>
#define NATURAL_GUARD_MAGIC 0x4E475231U
#define NATURAL_GUARD_LUT_FNV {fingerprint}U
#ifdef ROAD_NATURAL_IMPLEMENTATION
static const uint16_t natural_target_q8[256]={{
 {headers}
}};
static int natural_apply(const uint32_t *raw,uint32_t *enh,unsigned n,void (*poll)(void *),void *opaque){{
 unsigned i,c;
 if(!raw||!enh||raw==enh||n!=96000U)return 1;
 for(i=0;i<n;i++){{
  uint32_t a=raw[i],b=enh[i],yr=54U*(a&255U)+183U*((a>>8)&255U)+19U*((a>>16)&255U);
  uint32_t ye=54U*(b&255U)+183U*((b>>8)&255U)+19U*((b>>16)&255U),target=natural_target_q8[(yr+128U)>>8];
  if(target<yr)target=yr;
  if(ye>target){{
   uint32_t den=ye-yr,w0=ye-target,w1=target-yr,out=0;
   for(c=0;c<3;c++){{uint32_t v=(((a>>(8*c))&255U)*w0+((b>>(8*c))&255U)*w1+den/2U)/den;out|=v<<(8*c);}}
   enh[i]=out;
  }}
  if(poll&&(i&4095U)==0)poll(opaque);
 }}
 return 0;
}}
#endif
#endif
'''
    (src/'road_natural_guard.h').write_text(header,encoding='ascii')
    path=src/'road_retinex_shadow.c';text=path.read_text(encoding='ascii');assert text.count('int road_retinex_c(')==1
    text='#define ROAD_NATURAL_IMPLEMENTATION\n#include "road_natural_guard.h"\n'+text.replace('int road_retinex_c(','static int road_retinex_unbounded(')
    text+='''
/* Display-only constraint; same raw detector input and original NN weights. */
int road_retinex_c(const uint32_t *raw,uint32_t *dst,unsigned n,float *work,RoadRetinexStats *s,void (*poll)(void *),void *opaque){
 unsigned i;uint64_t total=0;float maximum=1.f;int e=road_retinex_unbounded(raw,dst,n,work,s,poll,opaque);if(e)return e;
 e=natural_apply(raw,dst,n,poll,opaque);if(e)return e;
 for(i=0;i<n;i++){
  uint32_t a=raw[i],b=dst[i],ra=a&255U,ga=(a>>8)&255U,ba=(a>>16)&255U,rb=b&255U,gb=(b>>8)&255U,bb=(b>>16)&255U;
  uint32_t vi=ra>ga?(ra>ba?ra:ba):(ga>ba?ga:ba),vo=rb>gb?(rb>bb?rb:bb):(gb>bb?gb:bb);
  total+=54U*rb+183U*gb+19U*bb;
  if(vi){float gain=(float)vo/(float)vi;if(gain>maximum)maximum=gain;}
 }
 s->mean_out=(float)((double)total/(256.0*n));s->max_gain=maximum;return 0;
}
''';path.write_text(text,encoding='ascii')
    path=src/'road_camera_main.c';text=path.read_text(encoding='ascii');assert text.count('m[M_VERSION]=31;')==1
    text='#include "road_natural_guard.h"\n'+text.replace('m[M_VERSION]=31;','m[M_VERSION]=32;').replace('m[266]=0x53443331U;','m[266]=0x53443332U;')
    text=text.replace('m[268]=0x43414D31U;','m[280]=NATURAL_GUARD_MAGIC;m[281]=NATURAL_GUARD_LUT_FNV;m[282]=1;m[283]=55;m[284]=550;m[285]=12;m[286]=130;m[287]=245;m[268]=0x43414D31U;')
    text=text.replace('READY V31','READY V32');path.write_text(text,encoding='ascii')
    # Verify portable integer implementation, including canaries and source immutability.
    host=ROOT/'host';host.mkdir();bridge=host/'guard.c';bridge.write_text('#define ROAD_NATURAL_IMPLEMENTATION\n#include "road_natural_guard.h"\nint guard(const uint32_t *a,uint32_t *b,unsigned n){return natural_apply(a,b,n,0,0);}\n',encoding='ascii')
    gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH'];logs=[];commands=[]
    def run(cmd):
        p=subprocess.run(cmd,capture_output=True,text=True,env=env);commands.append(cmd);logs.append(p.stdout+p.stderr);(ROOT/'build.log').write_text('\n'.join(logs),encoding='utf-8');assert p.returncode==0,p.stderr
    run([str(gcc),'-shared','-O2','-std=c99','-Wall','-Wextra','-Werror','-I'+str(src),str(bridge),'-o',str(host/'guard.dll')])
    directory=os.add_dll_directory(str(gcc.parent));lib=ct.CDLL(str(host/'guard.dll'));up=ct.POINTER(ct.c_uint32);lib.guard.argtypes=[up,up,ct.c_uint]
    def check(a,b):
        aw=words(a).reshape(-1).copy();before=aw.copy();bw=np.full(96004,0xdeadbeef,np.uint32);bw[:96000]=words(b).reshape(-1)
        assert lib.guard(aw.ctypes.data_as(up),bw.ctypes.data_as(up),96000)==0
        assert np.array_equal(aw,before) and np.all(bw[-4:]==0xdeadbeef)
        expected=words(apply(a,b,lut)).reshape(-1);assert np.array_equal(bw[:96000],expected)
        return bw[:96000].copy()
    tests=[]
    for row in read(CASES/'complete.json')['cases']:
        packet=Path(row['source_result']['packet_evidence']);a=rgb(packet/'raw.u32');b=rgb(packet/'enhanced.u32');out=check(a,b)
        out.tofile(host/f'case{row["case"]:02d}_expected.u32');tests.append(dict(case=row['case'],byte_exact=True,baseline_packet=str(packet)))
    rng=np.random.default_rng(2026110102)
    for _ in range(4):check(rng.integers(0,256,(240,400,3),dtype=np.uint8),rng.integers(0,256,(240,400,3),dtype=np.uint8))
    for level in [0,49,128,255]:
        a=np.full((240,400,3),level,np.uint8);assert np.array_equal(check(a,a),words(a).reshape(-1))
    old=read(OLD/'build_verified.json');relocate=lambda cmd:[s.replace(str(OLD),str(ROOT)).replace(OLD.as_posix(),ROOT.as_posix()) for s in cmd]
    compile_main=relocate(old['commands'][0]);run(compile_main)
    compile_enh=compile_main.copy();compile_enh[compile_enh.index('-c')+1]=str(src/'road_retinex_shadow.c');compile_enh[compile_enh.index('-o')+1]=str(app/'obj/road_retinex_shadow.o');run(compile_enh)
    run(relocate(old['commands'][1]))
    for p in (OLD/'firmware/source').iterdir():
        if p.is_file() and p.name not in ['road_retinex_shadow.c','road_camera_main.c']:assert sha(p)==sha(src/p.name)
    assert sha(app/'display.bit')==old['bit_sha256']
    data=(app/'road_detail.elf').read_bytes();ph=struct.unpack_from('<I',data,28)[0];ent,n=struct.unpack_from('<HH',data,42);regions=[]
    for i in range(n):
        typ,off,va,pa,fs,mem,flags,align=struct.unpack_from('<8I',data,ph+i*ent)
        if typ==1 and mem:assert 0x100000<=pa<pa+mem<=0x02000000;regions.append([pa,pa+mem])
    loader=(OLD/'start_camera.tcl').read_text(encoding='ascii').replace((OLD/'firmware').as_posix(),app.as_posix()).replace('==31','==32').replace('ABI31','ABI32')
    (ROOT/'start_camera.tcl').write_text(loader,encoding='ascii')
    record=dict(status='ABI32_NATURAL_GUARD_BUILT_NOT_BOARD_TESTED',version=32,elf_sha256=sha(app/'road_detail.elf'),bit_sha256=sha(app/'display.bit'),
        models_unchanged=True,detector_unchanged=True,enhancement_changed=True,integer_reference_byte_exact=True,tests=tests,
        lut_fnv=fingerprint,profile=profile,commands=commands,elf_regions=regions,sd_written=False)
    write(ROOT/'build_verified.json',record);print('ABI32_NATURAL_GUARD_BUILD_PASS',fingerprint,sha(app/'road_detail.elf'),flush=True)

if __name__=='__main__':main()
