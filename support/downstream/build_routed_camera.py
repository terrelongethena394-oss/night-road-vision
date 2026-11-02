"""ABI25 candidate: scene-selected weights, same protected frame and4 PL passes."""
import re,shutil,struct,subprocess,os
from road_brightness_route_common import *
from camera_snapshot_tools import fnv
HERE=Path(__file__).resolve().parent
DEST=BASE/'road_routed_camera_20261030_r1'
OLD=BASE/'road_camera_snapshot_20261030_r1/firmware'
APP=DEST/'firmware'

def main_source(s,newfnv):
 s=s.replace('#include "road_vehicle_multiview.h"','#include "road_vehicle_multiview.h"\n#include "road_score_calibration.h"\nint road_brightness_route(const uint32_t *,unsigned);\n#define ROUTE_DARK_WEIGHTS 0x1B000000U\n#define ROUTE_DARK_FNV '+hex(newfnv)+'U')
 s=s.replace('#include <string.h>','#include <string.h>\nstatic uint32_t active_weight,route_mode;')
 marker=' p0=now();enh_start=now();'
 assert s.count(marker)==1
 s=s.replace(marker,''' /* Select once from the protected unenhanced global frame. All four views
  * and both software/PL operators use exactly this same weight bank. */
 {int r=road_brightness_route((const uint32_t *)RC_INPUT,96000U);uint32_t wanted,expected;
  if(r<0)fatal(46);route_mode=(uint32_t)r;wanted=route_mode?ROUTE_DARK_WEIGHTS:RC_WEIGHT;expected=route_mode?ROUTE_DARK_FNV:ROAD_EXPECTED_WEIGHT_FNV;
  if(wanted!=active_weight){Xil_DCacheInvalidateRange(wanted,ROAD_WEIGHT_FLOATS*4U);m[M_WEIGHT_FNV]=hash((const void *)wanted,ROAD_WEIGHT_FLOATS*4U);if(m[M_WEIGHT_FNV]!=expected)fatal(47);if(road_pl_prepare((const float *)wanted))fatal(30);active_weight=wanted;m[163]++;}
  m[160]=route_mode;m[M_WEIGHT]=active_weight;if(route_mode)m[162]=m[M_WEIGHT_FNV];else m[161]=m[M_WEIGHT_FNV];
 }
 p0=now();enh_start=now();''')
 assert s.count('road_forward((const float *)RC_WEIGHT,')==2
 s=s.replace('road_forward((const float *)RC_WEIGHT,','road_forward((const float *)active_weight,')
 marker='count=road_vehicle_multiview((const RoadBox *)RC_FULL_BOX,nf,rvm_tiles,rvm_counts,.75f,(RoadBox *)RC_FUSED_BOX,300);if(count<0)fatal(40);'
 assert s.count(marker)==1
 s=s.replace(marker,marker+'\n  if(route_mode&&road_score_calibrate_classwise((RoadBox *)RC_FUSED_BOX,count,1.75f,1.1f)<0)fatal(48);')
 old='''  rvm_baseline_count=0;
  for(k=0;k<nf;k++)if(((const RoadBox *)RC_FULL_BOX)[k].score>=.25f){
   const RoadBox *v=(const RoadBox *)RC_FULL_BOX+k;'''
 new='''  rvm_baseline_count=0;
  memcpy((void *)RC_CANDIDATES,(const void *)RC_FULL_BOX,(uint32_t)nf*sizeof(RoadBox));
  if(route_mode&&road_score_calibrate_classwise((RoadBox *)RC_CANDIDATES,nf,1.75f,1.1f)<0)fatal(49);
  for(k=0;k<nf;k++)if(((const RoadBox *)RC_CANDIDATES)[k].score>=.25f){
   const RoadBox *v=(const RoadBox *)RC_CANDIDATES+k;'''
 assert old in s;s=s.replace(old,new)
 marker='if(road_pl_prepare((const float *)RC_WEIGHT))fatal(30);'
 assert s.count(marker)==1;s=s.replace(marker,marker+'\n    active_weight=RC_WEIGHT;m[161]=m[M_WEIGHT_FNV];m[163]=1;')
 s=s.replace('m[M_VERSION]=24;','m[M_VERSION]=25;').replace('ROAD_CAMERA_SNAPSHOT_READY V24','ROAD_CAMERA_ROUTE_READY V25')
 return s

def main():
 proof=read(ROOT/'fresh_result.json');assert proof['accepted'] and not DEST.exists();DEST.mkdir();APP.mkdir();shutil.copytree(OLD/'source',APP/'source');(APP/'runtime').mkdir();(APP/'obj').mkdir();(APP/'host').mkdir()
 for name in ['display.bit','display.xsa','road_conv.bit','ps7_init.tcl','Xilinx.spec']:shutil.copy2(OLD/name,APP/name)
 shutil.copy2(OLD/'runtime/weights.f32',APP/'runtime/weights.f32');shutil.copy2(ADAPT/'export/weights.f32',APP/'runtime/dark_weights.f32')
 newfnv=fnv((APP/'runtime/dark_weights.f32').read_bytes());src=APP/'source'
 for name in ['road_score_calibration.c','road_score_calibration.h','road_brightness_route.c']:shutil.copy2(HERE/name,src/name)
 p=src/'road_camera_main.c';p.write_text(main_source(p.read_text(),newfnv),encoding='ascii')
 old=read(OLD/'arm_complete.json');commands=[];logs=[]
 def run(cmd):
  commands.append(cmd);p=subprocess.run(cmd,capture_output=True,text=True);logs.append(p.stdout+p.stderr);(APP/'build.log').write_text('\n'.join(logs),encoding='utf-8');assert p.returncode==0,p.stderr
 templates=[[x.replace(str(OLD),str(APP)).replace(OLD.as_posix(),APP.as_posix()) for x in cmd] for cmd in old['commands']]
 template=next(cmd for cmd in templates if any(Path(x).name=='road_vehicle_multiview.c' for x in cmd));extras=[]
 for stem in ['road_score_calibration','road_brightness_route']:extras.append([x.replace('road_vehicle_multiview.c',stem+'.c').replace('road_vehicle_multiview.o',stem+'.o') for x in template])
 for cmd in templates:
  if '-c' not in cmd:
   for extra in extras:run(extra)
   cmd=cmd.copy()
   for stem in ['road_score_calibration','road_brightness_route']:cmd.insert(cmd.index('-Wl,--start-group'),str(APP/'obj'/(stem+'.o')))
  run(cmd)
 elf=APP/'road_detail.elf';raw=elf.read_bytes();assert b'ROAD_CAMERA_ROUTE_READY V25' in raw
 phoff=struct.unpack_from('<I',raw,28)[0];ent,num=struct.unpack_from('<HH',raw,42);loads=[]
 for i in range(num):
  typ,off,va,pa,fs,mem,fl,al=struct.unpack_from('<8I',raw,phoff+i*ent)
  if typ==1 and mem:assert 0x100000<=pa<pa+mem<=0x1000000;loads.append([pa,pa+mem])
 regions=old['regions']+[['dark_weight_bank',0x1B000000,(APP/'runtime/dark_weights.f32').stat().st_size]]
 for i,(name,a,l) in enumerate(regions):
  assert a+l<=0x20000000
  for n,b,k in regions[:i]:assert a+l<=b or b+k<=a,(name,n)
  for b,e in loads:assert a+l<=b or e<=a
 for name in ['road_fp32.c','road_pl.c','road_conv3_pack.c','road_graph.h','road_capture_views.c','road_camera_io.c','road_camera_draw.c','road_retinex_c.c','road_vehicle_multiview.c']:assert sha(src/name)==sha(OLD/'source'/name)
 t=(OLD/'camera_common.tcl').read_text().replace('!=24','!=25');t=re.sub('elf_sha256=[0-9a-f]{64}','elf_sha256='+sha(elf),t);(APP/'camera_common.tcl').write_text(t,encoding='ascii')
 t=(OLD/'start_idle.tcl').read_text().replace('==24','==25');marker='dow -data $root/runtime/weights.f32 0x11000000';assert marker in t;t=t.replace(marker,marker+'\n dow -data $root/runtime/dark_weights.f32 0x1B000000');(APP/'start_idle.tcl').write_text(t,encoding='ascii')
 gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH']
 for name in ['render.exe']:
  cmd=[str(gcc),'-O2','-std=c99','-Wall','-Wextra','-Werror','-I'+str(src),str(src/'road_camera_draw.c'),str(src/'road_camera_draw_host.c'),'-lm','-o',str(APP/'host'/name)];p=subprocess.run(cmd,capture_output=True,text=True,env=env);assert p.returncode==0,p.stderr
 shutil.copy2(BASE/'road_accuracy_20261030_r1/firmware/host/post.dll',APP/'host/post.dll');shutil.copy2(BASE/'road_accuracy_20261030_r1/native/fusion.dll',APP/'host/fusion.dll');shutil.copy2(BASE/'road_local_enhance_20261029_r2/host/road_ap.exe',APP/'host/road_ap.exe');shutil.copy2(ROOT/'calibration_c/calibration.dll',APP/'host/calibration.dll')
 write(APP/'arm_complete.json',dict(status='ABI25_ROUTED_CAMERA_COMPILED_NOT_BOARD_TESTED',version=25,commands=commands,regions=regions,elf_loads=loads,elf_sha256=sha(elf),bit_sha256=sha(APP/'display.bit'),weights_sha256=dict(bright=sha(APP/'runtime/weights.f32'),dark=sha(APP/'runtime/dark_weights.f32')),weight_fnv=dict(bright=1483844061,dark=newfnv),source_sha256={p.name:sha(p) for p in src.iterdir() if p.is_file()},mail_words=164,ui_words=17,offline_result_sha256=sha(ROOT/'fresh_result.json'),dark_weight_address=0x1B000000,model_switch_rebuilds_PL_packed_bank=True,sd_written=False))
 write(APP/'runtime_checksums.json',{str(p.relative_to(APP)):sha(p) for p in APP.rglob('*') if p.is_file() and p.name!='runtime_checksums.json' and 'obj' not in p.relative_to(APP).parts and p.suffix not in ['.log','.map','.su']})
 print('ROUTED_CAMERA_ABI25_COMPILED',sha(elf),newfnv,flush=True)

if __name__=='__main__':main()
