"""ABI28 isolated balanced4/7view candidate; unchanged accepted PL bit; no SD."""
from pathlib import Path
import os,re,shutil,struct,subprocess
from study_balanced_car_20261030 import ROOT as STUDY
from car_box_refine_common import BASE,read,write,sha
from camera_snapshot_tools import fnv
ROOT=STUDY/'board_candidate';APP=ROOT/'firmware';OLD=BASE/'road_car_bright_20261030_r1/firmware';HERE=Path(__file__).parent

def main():
 assert read(STUDY/'confirmation/fresh_result.json')['accepted']
 selected=read(STUDY/'selected.json')['chosen'];assert selected['family']=='box_refiner';params=selected['source']
 assert not ROOT.exists();ROOT.mkdir();APP.mkdir();(ROOT/'source').mkdir();shutil.copytree(OLD/'source',APP/'source')
 for n in ['runtime','obj','host']:(APP/n).mkdir()
 src=APP/'source'
 for n in ['display.bit','display.xsa','road_conv.bit','ps7_init.tcl','Xilinx.spec']:shutil.copy2(OLD/n,APP/n)
 shutil.copy2(BASE/'road_viewadapt_20261030_r1/export/weights.f32',APP/'runtime/weights.f32')
 shutil.copy2(STUDY/'export/weights.f32',APP/'runtime/refiner_weights.f32')
 detector_fnv=fnv((APP/'runtime/weights.f32').read_bytes());refiner_fnv=fnv((APP/'runtime/refiner_weights.f32').read_bytes());assert detector_fnv==22819740
 for n in ['road_box_refiner.c','road_box_refiner.h','road_car_refined_zoom.c']:shutil.copy2(STUDY/'c_proof/source'/n,src/n)
 shutil.copy2(BASE/'road_car_zoom_20261030_r1/c_proof/source/road_zoom_pixels.c',src/'road_zoom_pixels.c')
 for n in ['road_balanced_extra.c','road_balanced_extra.h']:shutil.copy2(HERE/n,src/n)
 y=read(BASE/'road_car_zoom_20261030_r1/protocol.json')['geometry']['y']
 (src/'road_balanced_config.h').write_text(f'#define BAL_ZOOM_Y {y}\n#define BAL_STRENGTH {params["strength"]}f\n#define BAL_CAP {params["cap"]}f\n#define BAL_CLASS_GATE {params["class_gate"]}f\n#define BAL_REFINER_FNV {hex(refiner_fnv)}U\n',encoding='ascii')
 p=src/'road_probe_config.h';s=p.read_text();s=re.sub(r'(#define ROAD_EXPECTED_WEIGHT_FNV )0x[0-9a-fA-F]+U',lambda m:m[1]+hex(detector_fnv)+'U',s);p.write_text(s,encoding='ascii')
 p=src/'road_camera_main.c';s=p.read_text();s=s.replace('#include "road_car_pair_model.h"','#include "road_car_pair_model.h"\n#include "road_balanced_extra.h"\n#include "road_balanced_config.h"')
 s=s.replace('m[M_VERSION]=27;','m[M_VERSION]=28;').replace('ROAD_CAR_BRIGHT_READY V27','ROAD_BALANCED_CAR_READY V28')
 s=s.replace(' int injected=kind!=4U;',' int injected=kind!=4U;\n if(kind==2U)fatal(46);')
 a=s.index(' {unsigned calls0=0,calls1=0;');b=s.index(' boxes(RC_BOX400,',a)
 s=s[:a]+''' {unsigned calls0=0,calls1=0,v;uint64_t net0=0,net1=0,total=0;XTime t0,t1,t2;
  XTime_GetTime(&t0);count=road_car_pair_model((const float *)RC_WEIGHT,1,pair_cars,&calls0,&net0);if(count<0||calls0!=204U)fatal(50);
  rvm_baseline_count=(uint32_t)count;boxes(RVM_BASELINE,pair_cars,count);Xil_DCacheFlushRange(RVM_BASELINE,(uint32_t)count*24U);
  for(v=0;v<4;v++){uint32_t source=v?RVM_DECODE(v-1):RC_FULL_DECODE,dest=0x1B800000U+v*0x40000U;memcpy((void *)dest,(const void *)source,ROAD_CANDIDATES*9U*4U);Xil_DCacheFlushRange(dest,ROAD_CANDIDATES*9U*4U);}
  for(v=0;v<96000;v++){uint32_t q=((const uint32_t *)RC_INPUT)[v];total+=54U*(q&255U)+183U*((q>>8)&255U)+19U*((q>>16)&255U);}
  m[189]=total<=48ULL*256ULL*96000ULL?1U:0U;XTime_GetTime(&t1);
  if(m[189]){count=road_balanced_extra((const float *)RC_WEIGHT,(const uint8_t *)RVM_SOURCE800,pair_cars,(int)rvm_baseline_count,(RoadBox *)RC_KEEP,&calls1,&net1);if(count<0||calls1!=153U)fatal(51);}
  else{memcpy((void *)RC_KEEP,pair_cars,rvm_baseline_count*sizeof(RoadBox));m[190]=m[194]=0;memset((void *)BAL_REFINER_PRED,0,900U*5U*4U);Xil_DCacheFlushRange(BAL_REFINER_PRED,900U*5U*4U);for(v=0;v<3;v++){m[180+v]=m[183+v]=0;}}
  XTime_GetTime(&t2);m[104]=calls0+calls1;m[169]=calls0;m[170]=calls1;m[171]=rvm_baseline_count;m[172]=(uint32_t)count;m[163]=1;
  ticks(165,t1-t0);ticks(167,t2-t1);network_ticks=net0+net1;m[M_WEIGHT]=RC_WEIGHT;m[M_WEIGHT_FNV]=m[161];
  m[142]=rvm_baseline_count;m[143]=RVM_BASELINE;m[99]=2;m[102]=(uint32_t)count;result_detail=2;p1=p0;
 }
'''+s[b:]
 old='m[161]=m[M_WEIGHT_FNV];Xil_DCacheInvalidateRange(NEW_WEIGHT,ROAD_WEIGHT_FLOATS*4U);m[162]=hash((const void *)NEW_WEIGHT,ROAD_WEIGHT_FLOATS*4U);\n    if(m[162]!=CAR_PAIR_NEW_FNV){m[M_ERROR]=52;m[M_COMMAND]=0;barrier();continue;}'
 assert s.count(old)==1
 s=s.replace(old,'''m[161]=m[M_WEIGHT_FNV];Xil_DCacheInvalidateRange(BAL_REFINER_WEIGHT,17549U*4U);m[162]=hash((const void *)BAL_REFINER_WEIGHT,17549U*4U);m[193]=m[162];
    if(m[162]!=BAL_REFINER_FNV){m[M_ERROR]=52;m[M_COMMAND]=0;barrier();continue;}''')
 s=s.replace('m[160]=NEW_WEIGHT;m[164]=0x1B800000U;','''m[160]=BAL_REFINER_WEIGHT;m[164]=0x1B800000U;
 m[176]=BAL_ZOOM_INPUT(0);m[177]=BAL_ZOOM_DECODE(0);m[178]=BAL_ZOOM_Y;m[179]=0x3f266666U;
 m[186]=BAL_REFINER_WEIGHT;m[187]=BAL_REFINER_PRED;m[188]=BAL_REFINER_WORK;m[191]=17549;m[192]=BAL_REFINER_FNV;m[195]=5;
 m[196]=0x3f000000U;m[197]=0x3dcccccdU;m[198]=0;m[199]=0x42414c32U;''')
 p.write_text(s,encoding='ascii')
 p=src/'road_camera_draw.c';s=p.read_text();s=s.replace('"STABLE CAR MODEL"','"BASE 4 VIEWS"').replace('"NEW CAR MODEL"','"ADAPTIVE DETAIL"').replace('"STABLE CARS %u"','"BASE CARS %u"').replace('"SAME FRAME  SAME RAW NN INPUT"','"SAME FRAME  RAW DETECTION"').replace('"ENHANCED VIEW BOTH  CAR ONLY"','"BALANCED CAR EXPERIMENT"').replace('"PAIR %u MS CARS %u"','"TEST %u MS CARS %u"');p.write_text(s,encoding='ascii')
 oldproof=read(OLD/'arm_complete.json');commands=[];logs=[]
 def run(cmd):
  commands.append(cmd);p=subprocess.run(cmd,capture_output=True,text=True);logs.append(p.stdout+p.stderr);(APP/'build.log').write_text('\n'.join(logs),encoding='utf-8');assert p.returncode==0,p.stderr
 templates=[[x.replace(str(OLD),str(APP)).replace(OLD.as_posix(),APP.as_posix()) for x in cmd] for cmd in oldproof['commands']]
 template=next(cmd for cmd in templates if any(Path(x).name=='road_vehicle_multiview.c' for x in cmd));added=['road_zoom_pixels','road_box_refiner','road_car_refined_zoom','road_balanced_extra']
 for cmd in templates:
  if '-c' not in cmd:
   for stem in added:run([x.replace('road_vehicle_multiview.c',stem+'.c').replace('road_vehicle_multiview.o',stem+'.o') for x in template])
   cmd=cmd.copy()
   for stem in added:cmd.insert(cmd.index('-Wl,--start-group'),str(APP/'obj'/(stem+'.o')))
  run(cmd)
 elf=APP/'road_detail.elf';raw=elf.read_bytes();assert b'ROAD_BALANCED_CAR_READY V28' in raw
 loads=[];phoff=struct.unpack_from('<I',raw,28)[0];entry,num=struct.unpack_from('<HH',raw,42)
 for i in range(num):
  typ,off,va,pa,fs,mem,fl,al=struct.unpack_from('<8I',raw,phoff+i*entry)
  if typ==1 and mem:assert 0x100000<=pa<pa+mem<=0x1000000;loads.append([pa,pa+mem])
 regions=oldproof['regions']+[['zoom_inputs',0x1C000000,3*0x60000],['zoom_decodes',0x1C120000,3*0x40000],['refiner_weights',0x1C200000,17549*4],['refiner_outputs',0x1C240000,900*5*4],['refiner_work',0x1C250000,6560*4]]
 for i,(n,a,l) in enumerate(regions):
  assert a+l<=0x20000000
  for nn,b,k in regions[:i]:assert a+l<=b or b+k<=a,(n,nn)
  for b,e in loads:assert a+l<=b or e<=a
 unchanged=['road_fp32.c','road_pl.c','road_conv3_pack.c','road_graph.h','road_capture_views.c','road_camera_io.c','road_car_pair_model.c','road_car_pair_post.c','road_retinex_c.c','road_shadowlift.c','road_retinex_shadow.c']
 for n in unchanged:assert sha(src/n)==sha(OLD/'source'/n)
 t=(OLD/'camera_common.tcl').read_text().replace('!=27','!=28');t=re.sub('elf_sha256=[0-9a-f]{64}','elf_sha256='+sha(elf),t);(APP/'camera_common.tcl').write_text(t,encoding='ascii')
 t=(OLD/'start_idle.tcl').read_text().replace('==27','==28').replace('dow -data $root/runtime/new_weights.f32 0x1B000000','dow -data $root/runtime/refiner_weights.f32 0x1C200000');(APP/'start_idle.tcl').write_text(t,encoding='ascii')
 gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH']
 cmd=[str(gcc),'-O2','-std=c99','-Wall','-Wextra','-Werror','-I'+str(src),str(src/'road_camera_draw.c'),str(src/'road_camera_draw_host.c'),'-lm','-o',str(APP/'host/render.exe')];p=subprocess.run(cmd,capture_output=True,text=True,env=env);assert p.returncode==0,p.stderr
 proof=dict(status='ABI28_BALANCED_CAR_COMPILED_REQUIRES_BOARD_VALIDATION',version=28,commands=commands,regions=regions,elf_loads=loads,elf_sha256=sha(elf),bit_sha256=sha(APP/'display.bit'),
  detector_weights_sha256=sha(APP/'runtime/weights.f32'),refiner_weights_sha256=sha(APP/'runtime/refiner_weights.f32'),weight_fnv=dict(detector=detector_fnv,refiner=refiner_fnv),
  mail_words=208,ui_words=17,source_sha256={p.name:sha(p) for p in src.iterdir() if p.is_file()},unchanged_sources=unchanged,
  fresh_result_sha256=sha(STUDY/'confirmation/fresh_result.json'),sd_written=False)
 write(APP/'arm_complete.json',proof);shutil.copy2(__file__,ROOT/'source'/Path(__file__).name)
 print('BALANCED_ABI28_COMPILED',sha(elf),'REFINER_FNV',refiner_fnv,flush=True)

if __name__=='__main__':main()
