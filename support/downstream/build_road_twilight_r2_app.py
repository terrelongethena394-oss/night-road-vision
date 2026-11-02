"""Build a new ABI14 app only for a statistically accepted, C-proven checkpoint."""
from pathlib import Path
import re,shutil,struct,subprocess
from road_twilight_r2_common import ROOT,read,write,sha
CURRENT=Path('E:/FPGA_Enhance_Work/road_enhance_20261027/firmware')
ORIGINAL=Path('E:/FPGA_Enhance_Work/road_hybrid_20261027_r1')
BSP=Path('E:/FPGA_Enhance_Work/multinex_static_20261025/vitis_ws/static_platform/export/static_platform/sw/static_platform/standalone_domain')
TOOLS=Path('E:/Xilinx/Vitis/2020.2/gnu/aarch32/nt/gcc-arm-none-eabi/bin')
HERE=Path(__file__).resolve().parent
def fnv(b):
 h=2166136261
 for v in b:h=((h^v)*16777619)&0xffffffff
 return h
def main():
 accepted=read(ROOT/'fresh_complete.json');assert accepted['deployment_decision']!='retain_current';native=read(ROOT/'native_complete.json');pipe=native['pipe_mode']
 assert pipe in [1,2] and sha(ROOT/'native_raw/weights.f32')==native['weights_sha256']
 for n,h in read(CURRENT/'runtime_checksums.json').items():assert sha(CURRENT/n)==h,n
 app=ROOT/'firmware';app.mkdir(exist_ok=False);src=app/'source';shutil.copytree(CURRENT/'source',src)
 mainc=(src/'road_camera_main.c').read_text(encoding='utf-8');assert mainc.count('m[M_VERSION]=13;')==1 and mainc.count('m[80]=2U;')==1
 mainc=mainc.replace('m[M_VERSION]=13;','m[M_VERSION]=14;').replace('m[80]=2U;',f'm[80]={pipe}U;').replace('ROAD_ENHANCE_CAMERA_READY V13','ROAD_TWILIGHT_CAMERA_READY V14')
 (src/'road_camera_main.c').write_text(mainc,encoding='ascii');digest=fnv((ROOT/'native_raw/weights.f32').read_bytes());(src/'road_probe_config.h').write_text('#define ROAD_EXPECTED_WEIGHT_FNV 0x%08xU\n'%digest,encoding='ascii')
 for n in ['display.bit','display.xsa','ps7_init.tcl','Xilinx.spec']:shutil.copy2(CURRENT/n,app/n)
 runtime=app/'runtime';runtime.mkdir();shutil.copy2(ROOT/'native_raw/weights.f32',runtime/'weights.f32');cases=read(ROOT/'native_raw/complete.json')['cases'];entries=[]
 for photo,r in enumerate(cases,1):
  name=r['name'];assert re.fullmatch('[A-Za-z0-9_-]+',name);p=runtime/'cases'/name;p.mkdir(parents=True);shutil.copy2(ROOT/'native_raw/cases'/name/'input400.u32',p/'input400.u32');entries.append('{%s} {%d %d}'%(name,photo,fnv((p/'input400.u32').read_bytes())))
 common=(CURRENT/'camera_common.tcl').read_text(encoding='utf-8').replace('!=13','!=14');old=read(CURRENT/'arm_complete.json');common=common.replace(old['weights_sha256'],native['weights_sha256'])
 (app/'camera_common.tcl').write_text(common,encoding='ascii')
 startup=(CURRENT/'start_auto_live.tcl').read_text(encoding='utf-8').replace('==13','==14').replace('ROAD_ENHANCE_CAMERA_LIVE_READY','ROAD_TWILIGHT_CAMERA_LIVE_READY');(app/'start_live.tcl').write_text(startup,encoding='ascii')
 test=(ORIGINAL/'test_full_ram.tcl').read_text(encoding='utf-8');test=test.replace('physical_full_r1','board_fixed_r1').replace('road_hybrid.elf','road_enhance.elf').replace('==11','==14').replace('ROAD_HYBRID','ROAD_TWILIGHT')
 test=re.sub(r'^set cases .*$',lambda m:'set cases [dict create '+' '.join(entries)+']',test,flags=re.M);test=re.sub(r'^set first .*$',lambda m:'set first {'+cases[0]['name']+'}',test,flags=re.M)
 test=test.replace('foreach {mode label} {0 cpu 1 hybrid}','foreach {mode label} {0 cpu 1 fpga}')
 test=test.replace('if {$mode==0} {compact $out/cpu_first} else {compact $out/$first}','if {$mode==0} {compact $out/cpu_first} else {compact $out/$first}')
 test=test.replace('$folder/mailbox80.bin 0x13800000 80','$folder/mailbox96.bin 0x13800000 96').replace('$out/${label}_timing$j.bin 0x13800000 80','$out/${label}_timing$j.bin 0x13800000 96')
 needle=' mrd -bin -file $folder/head0.f32';i=test.index(needle);test=test[:i]+' mrd -bin -file $folder/raw_result400.u32 0x16700000 96000\n mrd -bin -file $folder/enhanced400.u32 0x16100000 96000\n mrd -bin -file $folder/preprocessed.rgb 0x13200000 76800\n'+test[i:]
 test=test.replace('first_hybrid_full','first_default_full').replace('$out/first_default_full/mailbox80.bin 0x13800000 80','$out/first_default_full/mailbox96.bin 0x13800000 96')
 insert=''' mwr 0x1380000c 0
 after 300
 mwr 0x1380000c 3
 after 15000
 rc_pause
 rc_packet $out/live_default live camera 0
'''
 needle=' set f [open $out/COMPLETE.txt w]';assert test.count(needle)==1;test=test.replace(needle,insert+needle);(app/'test_ram.tcl').write_text(test,encoding='ascii')
 scan=(CURRENT/'scan_only.tcl').read_text(encoding='utf-8').replace('ROAD_ENHANCE_SCAN_READY','ROAD_TWILIGHT_SCAN_READY');(app/'scan_only.tcl').write_text(scan,encoding='ascii')
 obj=app/'obj';obj.mkdir();commands=[];objects=[];logs=[]
 flags=['-mcpu=cortex-a9','-mfpu=neon-vfpv3','-mfloat-abi=hard','-O3','-std=c99','-ffp-contract=off','-fno-fast-math','-fno-common','-Wall','-g','-fstack-usage','-I'+str(src),'-I'+str(BSP/'bspinclude/include')]
 files=[src/n for n in ['road_fp32.c','road_pl.c','road_conv3_pack.c','road_enhance.c','road_camera_main.c','road_camera_io.c','road_camera_draw.c','road_camera_average.c']]+[p for d in ['display_ctrl','clk_wiz','vdma_api','emio_sccb_cfg','ov5640'] for p in sorted((src/d).glob('*.c'))]
 def run(cmd):
  cmd=list(map(str,cmd));commands.append(cmd);p=subprocess.run(cmd,capture_output=True,text=True);logs.append(p.stdout+p.stderr);(app/'build.log').write_text('\n'.join(logs),encoding='utf-8');assert p.returncode==0,p.stderr
 for p in files:
  o=obj/('_'.join(p.relative_to(src).parts)+'.o');strict=['-Wextra','-Werror','-Wno-misleading-indentation'] if p.parent==src else [];run([TOOLS/'arm-none-eabi-gcc.exe',*flags,*strict,'-c',p,'-o',o]);objects.append(o)
 elf=app/'road_enhance.elf';run([TOOLS/'arm-none-eabi-gcc.exe',*flags[:3],'-Wl,-build-id=none','-specs='+str(app/'Xilinx.spec'),'-Wl,-T,'+str(src/'lscript.ld'),'-Wl,-Map,'+str(app/'road_twilight.map'),'-L'+str(BSP/'bsplib/lib'),'-o',elf,*objects,'-Wl,--start-group','-lxil','-lgcc','-lc','-lm','-Wl,--end-group'])
 host=ROOT/'host';host.mkdir();run(['E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe','-O2','-std=c99','-Wall','-Wextra','-Werror','-I'+str(src),src/'road_camera_draw.c',src/'road_camera_draw_host.c','-lm','-o',host/'render.exe'])
 raw=elf.read_bytes();phoff=struct.unpack_from('<I',raw,28)[0];ent,n=struct.unpack_from('<HH',raw,42);loads=[]
 for i in range(n):
  typ,off,va,pa,fs,mem,fl,al=struct.unpack_from('<8I',raw,phoff+i*ent)
  if typ==1 and mem:assert 0x100000<=pa<pa+mem<=0x1000000;loads.append([pa,pa+mem])
 for name,a,n in old['regions']:
  for b,e in loads:assert a+n<=b or e<=a
 common=(app/'camera_common.tcl').read_text(encoding='utf-8').replace(old['elf_sha256'],sha(elf));(app/'camera_common.tcl').write_text(common,encoding='ascii')
 start='''from pathlib import Path
import json,hashlib,subprocess
root=Path(__file__).resolve().parent
for n,h in json.loads((root/'runtime_checksums.json').read_text(encoding='utf-8')).items():assert hashlib.sha256((root/n).read_bytes()).hexdigest()==h,n
print('ROAD_TWILIGHT_RUNTIME_HASHES_PASS',flush=True)
for attempt in range(2):
 p=subprocess.run(['E:/Xilinx/Vitis/2020.2/bin/xsct.bat',str(root/'start_live.tcl')],capture_output=True,text=True)
 text=p.stdout+p.stderr;(root/f'last_start_attempt{attempt}.log').write_text(text,encoding='utf-8');print(text)
 if p.returncode==0 and 'ROAD_TWILIGHT_CAMERA_LIVE_READY' in p.stdout:break
 if attempt==0 and 'Camera app error 220' in text:continue
 raise RuntimeError('Twilight camera startup failed')
else:raise RuntimeError('Twilight startup failed twice')
'''
 (app/'start_live.py').write_text(start,encoding='ascii');(app/'00_start_twilight_detection.cmd').write_text('@echo off\r\n"E:\\FPGA_Enhance_Work\\nn_env312\\Scripts\\python.exe" "%~dp0start_live.py"\r\npause\r\n',encoding='ascii')
 checks={str(p.relative_to(app)):sha(p) for p in app.rglob('*') if p.is_file() and (p.parent==app and p.suffix in ['.tcl','.py','.elf','.bit','.xsa'] or 'runtime' in p.relative_to(app).parts or 'source' in p.relative_to(app).parts)};write(app/'runtime_checksums.json',checks)
 write(app/'arm_complete.json',dict(status='ACCEPTED_TWILIGHT_CHECKPOINT_ARM_APP_COMPILED_NOT_BOARD_TESTED',version=14,default_pipe=pipe,weights_sha256=native['weights_sha256'],weight_fnv32=digest,elf_sha256=sha(elf),bit_sha256=sha(app/'display.bit'),bit_unchanged=True,model_architecture_unchanged=True,cases=cases,commands=commands,regions=old['regions'],elf_loads=loads,source_sha256={str(p.relative_to(src)):sha(p) for p in src.rglob('*') if p.is_file()},hardware_access=False,sd_written=False));print('TWILIGHT_NEW_ARM_APP_READY',pipe,flush=True)
if __name__=='__main__':main()
