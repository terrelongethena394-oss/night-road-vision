"""Compile ARM app, unchanged PL design and frozen detector, and native reference."""
from pathlib import Path
import json,os,shutil,struct,subprocess
import numpy as np
from road_enhance_common import ROOT,OLD,NN,enhance,sha,write
from road_arm_common import preprocess400
HERE=Path(__file__).resolve().parent
BSP=Path('E:/FPGA_Enhance_Work/multinex_static_20261025/vitis_ws/static_platform/export/static_platform/sw/static_platform/standalone_domain')
TOOLS=Path('E:/Xilinx/Vitis/2020.2/gnu/aarch32/nt/gcc-arm-none-eabi/bin')
def main():
 selected=json.loads((ROOT/'selected.json').read_text());assert selected['validation_gates_passed'];app=ROOT/'firmware';src=app/'source'
 (src/'road_enhance_config.h').write_text('#define ROAD_ENHANCE_DEFAULT_CAP %dU\n'%selected['cap'],encoding='ascii')
 assert sha(src/'road_fp32.c')==sha(OLD/'source/road_fp32.c') and sha(src/'road_pl.c')==sha(OLD/'source/road_pl.c')
 host=ROOT/'host';host.mkdir(exist_ok=False);hs=host/'source';hs.mkdir()
 for n in ['road_fp32.c','road_fp32.h','road_graph.h']:shutil.copy2(NN/'source_r2'/n,hs/n)
 for n in ['road_enhance.c','road_enhance.h','road_enhance_tables.h','road_enhance_config.h']:shutil.copy2(src/n,hs/n)
 harness=(HERE/'road_fp32_host.c').read_text().replace('#include "road_fp32.h"','#include "road_fp32.h"\n#include "road_enhance.h"\n#include "road_enhance_config.h"\n#ifndef ROAD_ENHANCE_MODE\n#define ROAD_ENHANCE_MODE 1\n#endif')
 harness=harness.replace('float *weights,*arena,*decoded;','float *weights,*arena,*decoded;uint32_t *enhanced;RoadEnhanceStats es;')
 harness=harness.replace('road_preprocess400(raw,rgb);','enhanced=malloc(384000U);if(!enhanced)return 30;\n  if(road_enhance(raw,enhanced,96000U,ROAD_ENHANCE_MODE==0?0:1,ROAD_ENHANCE_DEFAULT_CAP,&es,0,0))return 31;\n  snprintf(path,sizeof(path),"%s/enhanced400.u32",argv[3]);if(writefile(path,enhanced,384000U))return 32;\n  snprintf(path,sizeof(path),"%s/enhancement_stats.bin",argv[3]);if(writefile(path,&es,sizeof(es)))return 33;\n  road_preprocess400(ROAD_ENHANCE_MODE==1?enhanced:raw,rgb);')
 harness=harness.replace('free(weights);','free(enhanced);free(weights);');(hs/'host_main.c').write_text(harness,encoding='ascii')
 gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=os.environ.copy();env['PATH']=str(gcc.parent)+';'+env['PATH'];commands=[]
 def run(cmd,label,env=None):
  cmd=list(map(str,cmd));commands.append(cmd);p=subprocess.run(cmd,capture_output=True,text=True,env=env);(app/(label+'.log')).write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr;return p
 flags=['-O3','-std=c99','-msse2','-ffp-contract=off','-fno-fast-math','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-I'+str(hs)]
 for mode,label in [(0,'raw'),(1,'auto'),(2,'view')]:run([gcc,*flags,'-DROAD_ENHANCE_MODE='+str(mode),*[hs/n for n in ['road_fp32.c','road_enhance.c','host_main.c']],'-lm','-o',host/(label+'.exe')],'build_host_'+label,env)
 run([gcc,'-O2','-std=c99','-Wall','-Wextra','-Werror','-I'+str(src),src/'road_camera_draw.c',src/'road_camera_draw_host.c','-lm','-o',host/'render.exe'],'build_render',env)
 fixtures=json.loads((NN/'export_complete.json').read_text())['fixtures'];records=[]
 for f in fixtures:
  name=f['name'];case=host/name;case.mkdir();tr=case/'trace';tr.mkdir()
  p=run([host/'auto.exe',app/'runtime/weights.f32',NN/'cases'/name/'input400.u32',case,tr],'host_'+name,env);assert 'ROAD_FP32_HOST_DONE' in p.stdout
  raw=np.fromfile(NN/'cases'/name/'input400.u32','<u4').reshape(240,400);rgb=np.stack([raw&255,(raw>>8)&255,(raw>>16)&255],2).astype(np.uint8);e,stats=enhance(rgb,1,selected['cap'])
  words=e[:,:,0].astype(np.uint32)|(e[:,:,1].astype(np.uint32)<<8)|(e[:,:,2].astype(np.uint32)<<16)
  assert (case/'enhanced400.u32').read_bytes()==words.tobytes();assert (case/'input320.rgb').read_bytes()==preprocess400(e).tobytes()
  assert struct.unpack('<6I',(case/'enhancement_stats.bin').read_bytes())==tuple(stats.values())
  view=case/'view';view.mkdir();vt=view/'trace';vt.mkdir();run([host/'view.exe',app/'runtime/weights.f32',NN/'cases'/name/'input400.u32',view,vt],'host_view_'+name,env)
  assert (view/'enhanced400.u32').read_bytes()==(case/'enhanced400.u32').read_bytes()
  for p in (NN/'host_r2'/name/'trace').iterdir():assert (vt/p.name).read_bytes()==p.read_bytes(),(name,p.name)
  for n in ['input320.rgb','decoded.f32','boxes400.f32']:assert (view/n).read_bytes()==(NN/'host_r2'/name/n).read_bytes(),(name,n)
  records.append(dict(name=name,enhancement_and_preprocessing_exact=True,default_view_mode_all86_detector_outputs_bytes_unchanged=True,stats=stats));print('ROAD_ENHANCE_HOST_REFERENCE_READY',name,stats,flush=True)
 # Bypass is required to preserve the original same-host detector outputs.
 first=fixtures[0]['name'];rawcase=host/'bypass_control';rawcase.mkdir();run([host/'raw.exe',app/'runtime/weights.f32',NN/'cases'/first/'input400.u32',rawcase],'host_raw_control',env)
 for n in ['input320.rgb','decoded.f32','boxes400.f32']:assert (rawcase/n).read_bytes()==(NN/'host_r2'/first/n).read_bytes(),n
 write(ROOT/'host_complete.json',dict(status='ENHANCED_INPUT_AND_EXACT_PREPROCESS_REFERENCES_READY_RAW_BYPASS_DETECTOR_UNCHANGED',cases=records,selected_sha256=sha(ROOT/'selected.json'),hardware_access=False))
 obj=app/'obj';obj.mkdir();objects=[];logs=[]
 aflags=['-mcpu=cortex-a9','-mfpu=neon-vfpv3','-mfloat-abi=hard','-O3','-std=c99','-ffp-contract=off','-fno-fast-math','-fno-common','-Wall','-g','-fstack-usage','-I'+str(src),'-I'+str(BSP/'bspinclude/include')]
 files=[src/n for n in ['road_fp32.c','road_pl.c','road_conv3_pack.c','road_enhance.c','road_camera_main.c','road_camera_io.c','road_camera_draw.c','road_camera_average.c']]+[p for d in ['display_ctrl','clk_wiz','vdma_api','emio_sccb_cfg','ov5640'] for p in sorted((src/d).glob('*.c'))]
 for p in files:
  target=obj/('_'.join(p.relative_to(src).parts)+'.o');strict=['-Wextra','-Werror','-Wno-misleading-indentation'] if p.parent==src else []
  r=run([TOOLS/'arm-none-eabi-gcc.exe',*aflags,*strict,'-c',p,'-o',target],'compile_'+p.stem);objects.append(target);logs.append(r.stdout+r.stderr)
 elf=app/'road_enhance.elf';run([TOOLS/'arm-none-eabi-gcc.exe',*aflags[:3],'-Wl,-build-id=none','-specs='+str(app/'Xilinx.spec'),'-Wl,-T,'+str(src/'lscript.ld'),'-Wl,-Map,'+str(app/'road_enhance.map'),'-L'+str(BSP/'bsplib/lib'),'-o',elf,*objects,'-Wl,--start-group','-lxil','-lgcc','-lc','-lm','-Wl,--end-group'],'link_arm')
 data=elf.read_bytes();phoff=struct.unpack_from('<I',data,28)[0];ent,n=struct.unpack_from('<HH',data,42);loads=[]
 for i in range(n):
  typ,off,va,pa,fs,mem,fl,al=struct.unpack_from('<8I',data,phoff+i*ent)
  if typ==1 and mem:assert 0x100000<=pa<pa+mem<=0x1000000;loads.append([pa,pa+mem])
 regions=json.loads((OLD/'arm_complete.json').read_text())['regions'];regions=[(name,a,60 if name=='ui' else n) for name,a,n in regions]+[('enhanced_input',0x16600000,384000),('frozen_raw_result',0x16700000,384000)]
 for i,(name,a,n) in enumerate(regions):
  assert a+n<=0x40000000
  for name2,b,m in regions[:i]:assert a+n<=b or b+m<=a,(name,name2)
  for b,e in loads:assert a+n<=b or e<=a
 proof=dict(status='ADAPTIVE_GAMMA_FP32_ARM_FPGA_APP_COMPILED_NOT_BOARD_TESTED',mailbox_version=13,selected_cap=selected['cap'],enhancement_processor='ARM',neural_enhancement=False,detector_weights_unchanged=True,bit_unchanged=True,elf_sha256=sha(elf),bit_sha256=sha(app/'display.bit'),weights_sha256=sha(app/'runtime/weights.f32'),source_sha256={str(p.relative_to(src)):sha(p) for p in src.rglob('*') if p.is_file()},elf_loads=loads,regions=regions,commands=commands,hardware_access=False,sd_written=False)
 write(app/'arm_complete.json',proof);print('ROAD_ENHANCE_ARM_AND_HOST_COMPILED',flush=True)
if __name__=='__main__':main()
