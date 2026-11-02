"""User-chosen car-only A/B scope; preserve prior four-class failures unchanged."""
import os,re,shutil,struct,subprocess,sys
from car_pair_common import *
from camera_snapshot_tools import fnv
HERE=Path(__file__).resolve().parent

def main_source(s):
 s=s.replace('#include "road_vehicle_multiview.h"','#include "road_vehicle_multiview.h"\n#include "road_car_pair_model.h"\n#define NEW_WEIGHT 0x1B000000U\nstatic RoadBox pair_cars[300];')
 s=s.replace('m[M_VERSION]=24;','m[M_VERSION]=26;').replace('ROAD_CAMERA_SNAPSHOT_READY V24','ROAD_CAR_PAIR_READY V26')
 begin=s.index(' road_preprocess400((const uint32_t *)(pipe==1U?');end=s.index(' boxes(RC_BOX400,',begin)
 s=s[:begin]+''' {unsigned calls0=0,calls1=0;uint64_t net0=0,net1=0;XTime t0,t1,t2;
  XTime_GetTime(&t0);count=road_car_pair_model((const float *)RC_WEIGHT,0,pair_cars,&calls0,&net0);if(count<0||calls0!=204U)fatal(50);
  rvm_baseline_count=(uint32_t)count;boxes(RVM_BASELINE,pair_cars,count);Xil_DCacheFlushRange(RVM_BASELINE,(uint32_t)count*24U);
  XTime_GetTime(&t1);count=road_car_pair_model((const float *)NEW_WEIGHT,1,(RoadBox *)RC_KEEP,&calls1,&net1);if(count<0||calls1!=204U)fatal(51);XTime_GetTime(&t2);
  m[104]=calls0+calls1;m[169]=calls0;m[170]=calls1;m[171]=rvm_baseline_count;m[172]=(uint32_t)count;m[163]=2;
  ticks(165,t1-t0);ticks(167,t2-t1);network_ticks=net0+net1;m[M_WEIGHT]=NEW_WEIGHT;m[M_WEIGHT_FNV]=m[162];
  m[142]=rvm_baseline_count;m[143]=RVM_BASELINE;m[99]=2;m[102]=(uint32_t)count;result_detail=2;p1=p0;
 }
''' +s[end:]
 # Input protection, enhancement and final rendering stay in the accepted path.
 marker='if(road_pl_prepare((const float *)RC_WEIGHT))fatal(30);'
 assert s.count(marker)==1
 s=s.replace(marker,'''m[161]=m[M_WEIGHT_FNV];Xil_DCacheInvalidateRange(NEW_WEIGHT,ROAD_WEIGHT_FLOATS*4U);m[162]=hash((const void *)NEW_WEIGHT,ROAD_WEIGHT_FLOATS*4U);
    if(m[162]!=CAR_PAIR_NEW_FNV){m[M_ERROR]=52;m[M_COMMAND]=0;barrier();continue;}''')
 s=s.replace('m[144]=RVM_SOURCE800;', 'm[160]=NEW_WEIGHT;m[164]=0x1B800000U;\n m[144]=RVM_SOURCE800;')
 s=s.replace('if((detail!=0U&&detail!=2U)||(detail&&pipe==1U))fatal(34);if(kind!=2U&&detail!=2U)fatal(42);','if(detail!=2U||pipe!=2U)fatal(34);')
 # Declarations belonging to the removed one-model branch are no longer needed.
 s=s.replace('start,p0,p1,n0,n1,end,pause0,input_ticks','start,p0,p1,end,pause0,input_ticks')
 s=s.replace('static RoadBox rvm_tiles[900];\nstatic int rvm_counts[3];\n','')
 a=s.index('static XTime profile_previous;');b=s.index('static void boxes(',a);s=s[:a]+s[b:]
 return s

def draw_source(s):
 # Equal enhanced backgrounds: detection comparison does not mix input appearances.
 s=s.replace('uint32_t v=live[y*400+x];','uint32_t v=(u->has_result?result:live)[y*400+x];')
 old='text(f,10,14,u->is_test?"PHOTO RAW DET":"CAMERA RAW DET",2,0xFFFFFF);text(f,410,14,u->detail_mode?"ENH VIEW 4 PASS DET":u->pipe_mode==1U?"RETI INPUT + DET":(u->pipe_mode==2U?"GUARD / RAW DET":"RAW + DETECTION"),2,0xFFFFFF);'
 assert old in s;s=s.replace(old,'text(f,10,14,"STABLE CAR MODEL",2,0xFFFFFF);text(f,410,14,"NEW CAR MODEL",2,0xFFFFFF);')
 s=s.replace('"4PASS %u MS BOXES %u"','"PAIR %u MS CARS %u"').replace('"RAW BOXES %u"','"STABLE CARS %u"')
 s=s.replace('for(i=0;i<4;i++)text(f,10+200*i,400,names[i],2,colors[i]);','text(f,10,400,"SAME FRAME  SAME RAW NN INPUT",2,0xFFFFFF);')
 s=s.replace('"FROZEN FRAME  DETECTOR INPUT RAW"','"ENHANCED VIEW BOTH  CAR ONLY"')
 return s

def main():
 resume='--resume-failed-build' in sys.argv
 assert not ROOT.exists() or (resume and (ROOT/'scope.json').exists() and not (APP/'arm_complete.json').exists())
 ROOT.mkdir(exist_ok=resume);APP.mkdir(exist_ok=resume);(ROOT/'source').mkdir(exist_ok=resume)
 result=read(ROUTE/'fresh_result.json');before=result['low_baseline']['all']['classes']['car'];after=result['low_candidate']['all']['classes']['car']
 assert after['ap50']>before['ap50'] and after['precision']>before['precision'] and after['recall']>before['recall'] and result['uncertainty']['car_ap50_difference_interval995_descriptive'][0]>0
 write(ROOT/'scope.json',dict(status='USER_CHOSE_CAR_ONLY_AB_COMPARISON',request='优先汽车，准备专项对照版上板验证',prior_four_class_acceptance=False,prior_test_sha256=sha(ROUTE/'fresh_result.json'),purpose='Two actual neural models on one frozen800 frame, each the same4 raw views; only car output. Both LCD backgrounds use the same enhanced image. Eight forwards,408PL calls, no real-time claim. Functional board verification still pending.',car_metrics=dict(stable=before,candidate=after),car_ci995_descriptive=result['uncertainty']['car_ap50_difference_interval995_descriptive'],hardware_access=False,sd_written=False))
 shutil.copytree(OLD/'source',APP/'source',dirs_exist_ok=resume);(APP/'runtime').mkdir(exist_ok=resume);(APP/'obj').mkdir(exist_ok=resume);(APP/'host').mkdir(exist_ok=resume)
 for n in ['display.bit','display.xsa','road_conv.bit','ps7_init.tcl','Xilinx.spec']:shutil.copy2(OLD/n,APP/n)
 shutil.copy2(OLD/'runtime/weights.f32',APP/'runtime/weights.f32');shutil.copy2(ADAPT/'export/weights.f32',APP/'runtime/new_weights.f32');newfnv=fnv((APP/'runtime/new_weights.f32').read_bytes());src=APP/'source'
 for n in ['road_car_pair_post.c','road_car_pair_post.h','road_car_pair_model.c','road_car_pair_model.h']:shutil.copy2(HERE/n,src/n);shutil.copy2(HERE/n,ROOT/'source'/n)
 p=src/'road_probe_config.h';p.write_text(p.read_text()+'\n#define CAR_PAIR_NEW_FNV '+hex(newfnv)+'U\n',encoding='ascii')
 for name,func in [('road_camera_main.c',main_source),('road_camera_draw.c',draw_source)]:
  p=src/name;p.write_text(func(p.read_text()),encoding='ascii')
 old=read(OLD/'arm_complete.json');commands=[];logs=[]
 def run(cmd):
  commands.append(cmd);p=subprocess.run(cmd,capture_output=True,text=True);logs.append(p.stdout+p.stderr);(APP/'build.log').write_text('\n'.join(logs),encoding='utf-8');assert p.returncode==0,p.stderr
 templates=[[x.replace(str(OLD),str(APP)).replace(OLD.as_posix(),APP.as_posix()) for x in cmd] for cmd in old['commands']];tpl=next(cmd for cmd in templates if any(Path(x).name=='road_vehicle_multiview.c' for x in cmd))
 for cmd in templates:
  if '-c' not in cmd:
   for stem in ['road_car_pair_post','road_car_pair_model']:run([x.replace('road_vehicle_multiview.c',stem+'.c').replace('road_vehicle_multiview.o',stem+'.o') for x in tpl])
   cmd=cmd.copy()
   for stem in ['road_car_pair_post','road_car_pair_model']:cmd.insert(cmd.index('-Wl,--start-group'),str(APP/'obj'/(stem+'.o')))
  run(cmd)
 elf=APP/'road_detail.elf';raw=elf.read_bytes();assert b'ROAD_CAR_PAIR_READY V26' in raw;loads=[];phoff=struct.unpack_from('<I',raw,28)[0];ent,num=struct.unpack_from('<HH',raw,42)
 for i in range(num):
  typ,off,va,pa,fs,mem,fl,al=struct.unpack_from('<8I',raw,phoff+i*ent)
  if typ==1 and mem:assert 0x100000<=pa<pa+mem<=0x1000000;loads.append([pa,pa+mem])
 regions=old['regions']+[['new_weights',0x1B000000,7062464],['stable_four_decodes',0x1B800000,4*0x40000]]
 for i,(n,a,l) in enumerate(regions):
  assert a+l<=0x20000000
  for nn,b,k in regions[:i]:assert a+l<=b or b+k<=a,(n,nn)
  for b,e in loads:assert a+l<=b or e<=a
 for n in ['road_fp32.c','road_pl.c','road_conv3_pack.c','road_graph.h','road_capture_views.c','road_camera_io.c','road_retinex_c.c','road_vehicle_multiview.c']:assert sha(src/n)==sha(OLD/'source'/n)
 t=(OLD/'camera_common.tcl').read_text().replace('!=24','!=26');t=re.sub('elf_sha256=[0-9a-f]{64}','elf_sha256='+sha(elf),t);(APP/'camera_common.tcl').write_text(t,encoding='ascii')
 t=(OLD/'start_idle.tcl').read_text().replace('==24','==26');m='dow -data $root/runtime/weights.f32 0x11000000';assert m in t;t=t.replace(m,m+'\n dow -data $root/runtime/new_weights.f32 0x1B000000');(APP/'start_idle.tcl').write_text(t,encoding='ascii')
 gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH']
 cmd=[str(gcc),'-O2','-std=c99','-Wall','-Wextra','-Werror','-I'+str(src),str(src/'road_camera_draw.c'),str(src/'road_camera_draw_host.c'),'-lm','-o',str(APP/'host/render.exe')];p=subprocess.run(cmd,capture_output=True,text=True,env=env);assert p.returncode==0,p.stderr
 shutil.copy2(BASE/'road_accuracy_20261030_r1/firmware/host/post.dll',APP/'host/post.dll');shutil.copy2(BASE/'road_local_enhance_20261029_r2/host/road_ap.exe',APP/'host/road_ap.exe')
 write(APP/'arm_complete.json',dict(status='ABI26_CAR_PAIR_COMPILED_NOT_BOARD_TESTED',version=26,commands=commands,regions=regions,elf_loads=loads,elf_sha256=sha(elf),bit_sha256=sha(APP/'display.bit'),weights_sha256=dict(stable=sha(APP/'runtime/weights.f32'),candidate=sha(APP/'runtime/new_weights.f32')),weight_fnv=dict(stable=1483844061,candidate=newfnv),mail_words=176,ui_words=17,source_sha256={p.name:sha(p) for p in src.iterdir() if p.is_file()},sd_written=False))
 shutil.copy2(HERE/'build_car_pair.py',ROOT/'source/build_car_pair.py');print('CAR_PAIR_ABI26_COMPILED',sha(elf),newfnv,flush=True)

if __name__=='__main__':main()
