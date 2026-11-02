"""ABI27: brighter display; unchanged dual-car neural pipeline and weights."""
import re,shutil,struct,subprocess,os,sys
from pathlib import Path
from shadowlift_lab import BASE,ROOT as LAB,read,write,sha
from camera_snapshot_tools import fnv
HERE=Path(__file__).resolve().parent;OLDROOT=BASE/'road_car_pair_20261030_r1';OLD=OLDROOT/'firmware';ROOT=BASE/'road_car_bright_20261030_r1';APP=ROOT/'firmware'

def draw(s):
 s=s.replace('int x,y,i,k;char s[64];','int x,y,i,k;unsigned view=0;char s[64];')
 marker=' if(u->has_result)for(i=0;i<(int)u->count;i++){';assert s.count(marker)==1;s=s.replace(marker,' view=(u->pipe_mode>>8)&1U;\n'+marker)
 s=s.replace('uint32_t v=(u->has_result?result:live)[y*400+x];','uint32_t v=(u->has_result&&view?result:live)[y*400+x];')
 s=s.replace('unsigned count=side?u->count:u->baseline_count;const float *source=side?boxes:baseline;','unsigned count=side||!view?u->count:u->baseline_count;const float *source=side||!view?boxes:baseline;')
 s=s.replace('text(f,10,14,"STABLE CAR MODEL",2,0xFFFFFF);text(f,410,14,"NEW CAR MODEL",2,0xFFFFFF);','text(f,10,14,view?"STABLE CAR MODEL":"RAW IMAGE",2,0xFFFFFF);text(f,410,14,view?"NEW CAR MODEL":"ENHANCED IMAGE",2,0xFFFFFF);')
 s=s.replace('if(u->paused)snprintf(s,sizeof(s),"STABLE CARS %u",(unsigned)u->baseline_count);','if(u->paused)snprintf(s,sizeof(s),view?"STABLE CARS %u":"CARS FROM RAW %u",(unsigned)(view?u->baseline_count:u->count));')
 s=s.replace('"SAME FRAME  SAME RAW NN INPUT"','view?"SAME FRAME  SAME RAW NN INPUT":"SAME CAR BOXES FROM RAW INPUT"')
 s=s.replace('strcpy(s,"ENHANCED VIEW BOTH  CAR ONLY");','strcpy(s,view?"ENHANCED VIEW BOTH  CAR ONLY":"RAW VS ENHANCED  CAR ONLY");')
 return s

def main():
 rebuild='--rebuild-offline' in sys.argv
 assert (not ROOT.exists() or (rebuild and (APP/'arm_complete.json').exists() and not (ROOT/'board_verified.json').exists())) and read(LAB/'c_complete.json')['cases']==37 and read(OLDROOT/'board_verified.json')['status']=='ABI26_CAR_PAIR_ALL_INPUTS_AND_OUTPUTS_BOARD_VERIFIED';ROOT.mkdir(exist_ok=rebuild);APP.mkdir(exist_ok=rebuild);(ROOT/'source').mkdir(exist_ok=rebuild)
 if rebuild:shutil.copy2(APP/'arm_complete.json',ROOT/'build_before_null_guard_fix.json')
 shutil.copytree(OLD/'source',APP/'source',dirs_exist_ok=rebuild);(APP/'runtime').mkdir(exist_ok=rebuild);(APP/'obj').mkdir(exist_ok=rebuild);(APP/'host').mkdir(exist_ok=rebuild);src=APP/'source'
 for n in ['display.bit','display.xsa','road_conv.bit','ps7_init.tcl','Xilinx.spec']:shutil.copy2(OLD/n,APP/n)
 for n in ['weights.f32','new_weights.f32']:shutil.copy2(OLD/'runtime'/n,APP/'runtime'/n)
 for name in ['road_shadowlift.c','road_shadowlift.h','road_retinex_shadow.c']:shutil.copy2(LAB/'c_proof/source'/name,src/name)
 shutil.copy2(LAB/'c_proof/source/road_retinex_base.c',src/'road_retinex_c.c')
 p=src/'road_camera_main.c';s=p.read_text();s=s.replace('m[M_VERSION]=26;','m[M_VERSION]=27;').replace('ROAD_CAR_PAIR_READY V26','ROAD_CAR_BRIGHT_READY V27');s=s.replace('ui.pipe_mode=result_pipe;','ui.pipe_mode=result_pipe|((m[175]&1U)<<8);')
 marker='  }else usleep(1000);';assert s.count(marker)==1;s=s.replace(marker,'  }else if(m[M_COMMAND]==6U){m[M_COMMAND]=0;present(0);m[M_STATE]=5;barrier();}else usleep(1000);');p.write_text(s,encoding='ascii')
 p=src/'road_camera_draw.c';p.write_text(draw(p.read_text()),encoding='ascii')
 old=read(OLD/'arm_complete.json');commands=[];logs=[]
 def run(cmd):
  commands.append(cmd);p=subprocess.run(cmd,capture_output=True,text=True);logs.append(p.stdout+p.stderr);(APP/'build.log').write_text('\n'.join(logs),encoding='utf-8');assert p.returncode==0,p.stderr
 templates=[[x.replace(str(OLD),str(APP)).replace(OLD.as_posix(),APP.as_posix()) for x in cmd] for cmd in old['commands']];tpl=next(cmd for cmd in templates if any(Path(x).name=='road_vehicle_multiview.c' for x in cmd))
 for cmd in templates:
  if '-c' not in cmd:
   for stem in ['road_shadowlift','road_retinex_shadow']:run([x.replace('road_vehicle_multiview.c',stem+'.c').replace('road_vehicle_multiview.o',stem+'.o') for x in tpl])
   cmd=cmd.copy()
   for stem in ['road_shadowlift','road_retinex_shadow']:cmd.insert(cmd.index('-Wl,--start-group'),str(APP/'obj'/(stem+'.o')))
  run(cmd)
 elf=APP/'road_detail.elf';raw=elf.read_bytes();assert b'ROAD_CAR_BRIGHT_READY V27' in raw;loads=[];phoff=struct.unpack_from('<I',raw,28)[0];ent,num=struct.unpack_from('<HH',raw,42)
 for i in range(num):
  typ,off,va,pa,fs,mem,fl,al=struct.unpack_from('<8I',raw,phoff+i*ent)
  if typ==1 and mem:assert 0x100000<=pa<pa+mem<=0x1000000;loads.append([pa,pa+mem])
 for n,a,l in old['regions']:
  for b,e in loads:assert a+l<=b or e<=a
 unchanged=['road_fp32.c','road_pl.c','road_conv3_pack.c','road_graph.h','road_car_pair_model.c','road_car_pair_post.c','road_vehicle_multiview.c','road_capture_views.c','road_camera_io.c','road_enhance.c']
 for n in unchanged:assert sha(src/n)==sha(OLD/'source'/n)
 for n in ['weights.f32','new_weights.f32']:assert sha(APP/'runtime'/n)==sha(OLD/'runtime'/n)
 t=(OLD/'camera_common.tcl').read_text().replace('!=26','!=27');t=re.sub('elf_sha256=[0-9a-f]{64}','elf_sha256='+sha(elf),t);(APP/'camera_common.tcl').write_text(t,encoding='ascii');(APP/'start_idle.tcl').write_text((OLD/'start_idle.tcl').read_text().replace('==26','==27'),encoding='ascii')
 gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH'];cmd=[str(gcc),'-O2','-std=c99','-Wall','-Wextra','-Werror','-I'+str(src),str(src/'road_camera_draw.c'),str(src/'road_camera_draw_host.c'),'-lm','-o',str(APP/'host/render.exe')];p=subprocess.run(cmd,capture_output=True,text=True,env=env);assert p.returncode==0,p.stderr
 for n in ['post.dll','car_post.dll','road_ap.exe']:shutil.copy2(OLD/'host'/n,APP/'host'/n)
 shutil.copy2(LAB/'c_proof/shadow.dll',APP/'host/shadow.dll')
 proof=dict(old);proof.update(status='ABI27_BRIGHTER_DISPLAY_COMPILED_NOT_BOARD_TESTED',version=27,commands=commands,elf_loads=loads,elf_sha256=sha(elf),source_sha256={p.name:sha(p) for p in src.iterdir() if p.is_file()},neural_source_files_unchanged=unchanged,enhancement_c_proof_sha256=sha(LAB/'c_complete.json'),UI_modes=dict(raw_vs_enhanced=0,model_comparison=1),mode_mail_index=175,display_command=6,sd_written=False);write(APP/'arm_complete.json',proof)
 shutil.copytree(OLDROOT/'fixtures',ROOT/'fixtures',dirs_exist_ok=rebuild);fixture=ROOT/'fixtures/road';shutil.copy2(LAB/'current_road/final.u32',fixture/'enhanced.u32');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH'];cmd=[str(APP/'host/render.exe'),str(fixture/'raw.u32'),str(fixture/'enhanced.u32'),str(fixture/'candidate.f32'),str(fixture/'stable.f32'),str(fixture/'ui.u32'),str(fixture/'frame.bgr')];p=subprocess.run(cmd,capture_output=True,text=True,env=env);assert p.returncode==0 and 'GUARDS_PASS' in p.stdout
 from PIL import Image
 import numpy as np
 Image.fromarray(np.fromfile(fixture/'frame.bgr',np.uint8).reshape(480,800,3)[:,:,::-1]).save(fixture/'preview.png')
 for name in ['build_car_bright.py','shadowlift_lab.py','shadowlift_refine.py','prove_shadowlift.py']:shutil.copy2(HERE/name,ROOT/'source'/name)
 write(ROOT/'scope.json',dict(status='DISPLAY_ONLY_BRIGHTNESS_IMPROVEMENT',feedback='Still too dark',physical_previous_panel='User confirmed ABI26 images/text/boxes normal',enhancement_target=62,display_enhancement_only=True,detector_input_raw=True,weights_unchanged=True,old_ABI26_preserved=True,sd_written=False));print('CAR_BRIGHT_ABI27_COMPILED',sha(elf),flush=True)

if __name__=='__main__':main()
