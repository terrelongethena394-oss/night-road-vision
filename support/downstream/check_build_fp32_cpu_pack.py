from pathlib import Path
import os,subprocess,json,hashlib,struct,sys
import numpy as np
from prepare_fp32_cpu_pack import ROOT,CURRENT,BASE,read,write,sha
REF=BASE/'road_roi_spatial_verifier_20261028'
def main():
 src=ROOT/'native_source';gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=os.environ.copy();env['PATH']=str(gcc.parent)+';'+env['PATH'];host=ROOT/'host';host.mkdir()
 cmd=list(map(str,[gcc,'-O3','-std=c99','-msse2','-DROAD_CPU_HOST_PACK=1','-ffp-contract=off','-fno-fast-math','-Wall','-Wextra','-Werror','-I'+str(src),src/'road_fp32.c',src/'road_fp32_host.c','-lm','-o',host/'packed.exe']));p=subprocess.run(cmd,capture_output=True,text=True,env=env);(host/'build.log').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stderr
 records=[]
 for view in ['full','roi']:
  parent=REF/('native_detector_'+view)
  for case in read(parent/'complete.json')['cases']:
   name=case['name'];dest=host/(view+'_'+name);dest.mkdir();trace=dest/'trace';trace.mkdir()
   p=subprocess.run([str(host/'packed.exe'),str(parent/'weights.f32'),str(parent/'cases'/name/'input400.u32'),str(dest),str(trace)],capture_output=True,text=True,env=env);assert p.returncode==0 and 'ROAD_FP32_HOST_DONE' in p.stdout,p.stderr
   for tid in range(86):assert (trace/f'{tid:03d}.f32').read_bytes()==(parent/'cases'/name/'host/trace'/f'{tid:03d}.f32').read_bytes(),(view,name,tid)
   for n in ['decoded.f32','boxes400.f32']:assert (dest/n).read_bytes()==(parent/'cases'/name/'host'/n).read_bytes(),(view,name,n)
   records.append(dict(view=view,name=name,all86_and_outputs_byte_exact=True));print('CPU_PACK_NATIVE_ALL86_EXACT',view,name,flush=True)
 write(ROOT/'native_complete.json',dict(status='CPU_PACK_ALL16_ALL86_OUTPUTS_BYTE_EXACT',cases=records,host_compiler=cmd))
 compile_arm()
def compile_arm():
 app=ROOT/'firmware';(app/'obj').mkdir(exist_ok=True);old=read(CURRENT/'arm_complete.json');logs=[];commands=[]
 source_arg=next(v for cmd in old['commands'] for v in cmd if Path(v).name=='road_fp32.c');origin=Path(source_arg).parent.parent
 assert str(origin).startswith(str(BASE)) and origin!=app
 for command in old['commands']:
  cmd=[v.replace(str(origin),str(app)).replace(origin.as_posix(),app.as_posix()) for v in command]
  assert all(str(origin) not in v and origin.as_posix() not in v for v in cmd)
  assert '-o' in cmd and Path(cmd[cmd.index('-o')+1]).is_relative_to(app)
  for v in cmd:
   if v.endswith('.c'):assert Path(v).is_relative_to(app/'source'),v
  commands.append(cmd);p=subprocess.run(cmd,capture_output=True,text=True);logs.append(p.stdout+p.stderr);(app/'build.log').write_text('\n'.join(logs),encoding='utf-8');assert p.returncode==0,p.stderr
 elf=app/'road_detail.elf';raw=elf.read_bytes();assert b'ROAD_CPU_PACK_READY V16' in raw and sha(elf)!=old['elf_sha256'];phoff=struct.unpack_from('<I',raw,28)[0];ent,n=struct.unpack_from('<HH',raw,42);loads=[]
 for i in range(n):
  typ,off,va,pa,fs,mem,fl,al=struct.unpack_from('<8I',raw,phoff+i*ent)
  if typ==1 and mem:assert 0x100000<=pa<pa+mem<=0x1000000;loads.append([pa,pa+mem])
 regions=old['regions']+[['cpu_packed',0x19000000,read(ROOT/'prepared.json')['packed_bytes']],['layer_profile',0x17400000,696]]
 for i,(name,a,n) in enumerate(regions):
  for n2,b,l in regions[i+1:]:assert a+n<=b or b+l<=a,(name,n2)
  for b,e in loads:assert a+n<=b or e<=a
 common=(app/'camera_common.tcl').read_text(encoding='utf-8').replace('!=15','!=16').replace(old['elf_sha256'],sha(elf));(app/'camera_common.tcl').write_text(common,encoding='ascii')
 startup=(app/'start_default.tcl').read_text(encoding='utf-8').replace('==15','==16').replace('ROAD_DETAIL_EXPERIMENT_LIVE_READY','ROAD_CPU_PACK_LIVE_READY');(app/'start_default.tcl').write_text(startup,encoding='ascii');py=(app/'experiment.py').read_text(encoding='utf-8').replace('ROAD_DETAIL_EXPERIMENT_LIVE_READY','ROAD_CPU_PACK_LIVE_READY');(app/'experiment.py').write_text(py,encoding='ascii')
 proof=dict(old);proof.update(version=16,status='CPU_PACK_ARM_COMPILED_NATIVE_EXACT_NOT_BOARD_TESTED',elf_sha256=sha(elf),regions=regions,elf_loads=loads,commands=commands,cpu_pack_default=1);write(app/'arm_complete.json',proof)
 checks={str(p.relative_to(app)):sha(p) for p in app.rglob('*') if p.is_file() and (p.parent==app and p.suffix in ['.tcl','.py','.elf','.bit','.xsa'] or 'runtime' in p.relative_to(app).parts or 'source' in p.relative_to(app).parts)};checks['arm_complete.json']=sha(app/'arm_complete.json');write(app/'runtime_checksums.json',checks);print('CPU_PACK_NATIVE_AND_ARM_READY',flush=True)
if __name__=='__main__':
 if '--arm-only' in sys.argv:compile_arm()
 else:main()
