"""ABI24: one-shot protected camera frame -> ARM views -> unchanged4 forwards."""
from pathlib import Path
import hashlib,json,os,re,shutil,struct,subprocess,sys
HERE=Path(__file__).resolve().parent
ROOT=Path('E:/FPGA_Enhance_Work/road_camera_snapshot_20261030_r1')
OLD=Path('E:/FPGA_Enhance_Work/road_accuracy_20261030_r1/firmware')
APP=ROOT/'firmware'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,x):p.write_text(json.dumps(x,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def io_source(s):
 s=s.replace('#include "road_roi_guard.h"','#include "road_capture_views.h"')
 start=s.index('int rc_snapshot(');end=s.index('int rc_io_init(',start)
 s=s[:start]+'''/* Only this thread changes VDMA parking. After switching to next, old is
 * immutable until another snapshot call. No callback is made during copying. */
static int parked_source(const uint8_t **source,uint32_t *slot){
 uint32_t old=XAxiVdma_CurrFrameStore(&vdma,XAXIVDMA_WRITE),next,i;
 if(old>1)return 1;
 next=1U-old;
 if(XAxiVdma_StartParking(&vdma,(int)next,XAXIVDMA_WRITE)!=XST_SUCCESS)return 2;
 for(i=0;i<2000;i++){if(XAxiVdma_CurrFrameStore(&vdma,XAXIVDMA_WRITE)==next)break;usleep(1000);}
 if(i==2000)return 3;
 usleep(1000);__asm__ volatile("dsb sy" ::: "memory");
 *source=(const uint8_t *)(RC_CAPTURE+old*RC_FRAME_BYTES);Xil_DCacheInvalidateRange((INTPTR)*source,RC_FRAME_BYTES);
 *slot=old;return rc_dma_error(1)?4:0;
}
int rc_snapshot(uint32_t *dest,uint32_t *slot){
 const uint8_t *src;int e=parked_source(&src,slot);if(e)return e;
 road_camera_average(src,dest);__asm__ volatile("dsb sy" ::: "memory");return rc_dma_error(1)?4:0;
}
int rc_capture_frozen(uint8_t *saved,uint32_t *full,uint32_t *a,uint32_t *b,uint32_t *c,uint32_t *slot){
 const uint8_t *src;int e=parked_source(&src,slot);if(e)return e;
 memcpy(saved,src,RC_FRAME_BYTES);
 if(road_capture_views(saved,full,a,b,c))return 5;
 __asm__ volatile("dsb sy" ::: "memory");return rc_dma_error(1)?4:0;
}
''' +s[end:]
 return s

def main_source(s):
 s=s.replace('enhancement is ARM integer LUT','enhancement is ARM Retinex/patch filtering')
 s=s.replace('#include "road_vehicle_multiview.h"','#include "road_vehicle_multiview.h"\n#include "road_capture_views.h"\n#define RVM_SOURCE800 0x1A300000U')
 s=s.replace('(result_test&&has_result)?RC_RAW_RESULT:RC_LIVE','has_result?RC_RAW_RESULT:RC_LIVE')
 s=s.replace('static void infer(int injected){','static void infer(unsigned kind){\n int injected=kind!=4U;')
 s=s.replace('if(detail&&!injected)fatal(42);','if(kind!=2U&&detail!=2U)fatal(42);')
 start=s.index(' if(injected){Xil_DCacheInvalidateRange(RC_INPUT,RC_RAW_BYTES);')
 end=s.index(' m[M_INPUT_FNV]=hash(',start)
 s=s[:start]+''' m[156]=0;m[155]=kind;m[158]=0;
 if(kind==2U){
  Xil_DCacheInvalidateRange(RC_INPUT,RC_RAW_BYTES);if(detail){unsigned q;for(q=0;q<3;q++)Xil_DCacheInvalidateRange(RVM_TILE(q),RC_RAW_BYTES);}source_id=m[M_INPUT_ID];input_ticks=now();m[145]=m[148]=0;m[146]=0xffffffffU;
 }else{
  XTime cap0=now();uint32_t capture_slot=0xffffffffU;
  if(kind==5U){
   Xil_DCacheInvalidateRange(RVM_SOURCE800,RC_FRAME_BYTES);m[145]=hash((const void *)RVM_SOURCE800,RC_FRAME_BYTES);
   if(m[157]&&m[157]!=m[145])fatal(44);
   if(road_capture_views((const uint8_t *)RVM_SOURCE800,(uint32_t *)RC_INPUT,(uint32_t *)RVM_TILE(0),(uint32_t *)RVM_TILE(1),(uint32_t *)RVM_TILE(2)))fatal(43);
   source_id=m[M_INPUT_ID];
  }else{
   m[M_INPUT_EXPECT]=0;m[136]=m[137]=m[138]=m[157]=0;
   if(rc_capture_frozen((uint8_t *)RVM_SOURCE800,(uint32_t *)RC_INPUT,(uint32_t *)RVM_TILE(0),(uint32_t *)RVM_TILE(1),(uint32_t *)RVM_TILE(2),&capture_slot))fatal(221);
   m[145]=hash((const void *)RVM_SOURCE800,RC_FRAME_BYTES);source_id=++m[147];m[M_CAPTURE_SLOT]=capture_slot;
  }
  input_ticks=now();m[146]=capture_slot;ticks(153,input_ticks-cap0);memcpy((void *)RC_LIVE,(const void *)RC_INPUT,RC_RAW_BYTES);
 }
''' +s[end:]
 s=s.replace('trace_cursor=0;\n p0=now();','trace_cursor=0;present(0);\n p0=now();')
 # No write-parking switch after capture: all four views and inactive DMA bank
 # remain fixed until the next explicit request, even through preview callbacks.
 old='if(!last_view||now()-last_view>=(uint64_t)COUNTS_PER_SECOND*m[M_VIEW_MS]/1000U)preview();'
 assert old in s;s=s.replace(old,'if(!busy&&!has_result&&(!last_view||now()-last_view>=(uint64_t)COUNTS_PER_SECOND*m[M_VIEW_MS]/1000U))preview();')
 marker=' if(hash((const void *)RC_INPUT,RC_RAW_BYTES)!=m[M_INPUT_FNV])fatal(12);'
 assert marker in s;s=s.replace(marker,marker+'\n if(kind!=2U){m[148]=hash((const void *)RVM_SOURCE800,RC_FRAME_BYTES);if(m[145]!=m[148])fatal(45);m[158]=1;Xil_DCacheFlushRange(RVM_SOURCE800,RC_FRAME_BYTES);}')
 s=s.replace('present(0);m[M_STATE]=injected?5:1;barrier();','{unsigned q;Xil_DCacheFlushRange(RC_INPUT,RC_RAW_BYTES);for(q=0;q<3;q++)Xil_DCacheFlushRange(RVM_TILE(q),RC_RAW_BYTES);}\n present(0);m[156]=1;m[M_STATE]=5;barrier();')
 s=s.replace('m[M_VERSION]=23;','m[M_VERSION]=24;').replace('ROAD_ACCURACY_READY V23','ROAD_CAMERA_SNAPSHOT_READY V24')
 s=s.replace('status=rc_io_init(&lcd,&camera);','m[144]=RVM_SOURCE800;m[149]=RC_FRAME_BYTES;m[150]=800;m[151]=480;m[159]=0x46524f5aU;\n status=rc_io_init(&lcd,&camera);')
 s=s.replace('if(m[M_COMMAND]==2U||m[M_COMMAND]==3U){\n   int injected=m[M_COMMAND]==2U;','if(m[M_COMMAND]==2U||m[M_COMMAND]==4U||m[M_COMMAND]==5U){\n   unsigned kind=m[M_COMMAND];')
 s=s.replace('if(injected)m[M_COMMAND]=0;\n   infer(injected);','m[M_COMMAND]=0;\n   infer(kind);')
 assert 'infer(injected)' not in s and 'if(detail&&!injected)' not in s
 return s

def draw_source(s):
 s=s.replace('u->is_test?"RAW SINGLE DET":"LIVE RAW"','u->is_test?"PHOTO RAW DET":"CAMERA RAW DET"')
 old='snprintf(s,sizeof(s),"SNAP %u  VIEW %u.%u HZ",(unsigned)u->live_id,(unsigned)(u->view_hz10/10),(unsigned)(u->view_hz10%10));'
 assert old in s;s=s.replace(old,'if(u->busy)snprintf(s,sizeof(s),"SHOT %u PROCESSING",(unsigned)u->active_id);else if(u->has_result)snprintf(s,sizeof(s),"SHOT %u FROZEN",(unsigned)u->result_id);else strcpy(s,"LIVE PREVIEW READY");')
 s=s.replace('u->is_test?"TEST":"SNAP"','u->is_test?"PHOTO":"SHOT"')
 s=s.replace('DISPLAY ENHANCED  DETECTOR INPUT RAW','FROZEN FRAME  DETECTOR INPUT RAW')
 return s

def main():
 assert read(ROOT/'pixel_complete.json')['source_sha256']==sha(HERE/'road_capture_views.c')
 rebuild='--rebuild' in sys.argv
 if APP.exists():
  assert rebuild and (APP/'arm_complete.json').exists()
  shutil.copy2(APP/'arm_complete.json',ROOT/'build_before_input_flush_review.json')
 APP.mkdir(exist_ok=rebuild);shutil.copytree(OLD/'source',APP/'source',dirs_exist_ok=rebuild);(APP/'runtime').mkdir(exist_ok=rebuild);shutil.copy2(OLD/'runtime/weights.f32',APP/'runtime/weights.f32')
 for n in ['display.bit','display.xsa','road_conv.bit','ps7_init.tcl','Xilinx.spec']:shutil.copy2(OLD/n,APP/n)
 src=APP/'source'
 for n in ['road_capture_views.c','road_capture_views.h']:shutil.copy2(HERE/n,src/n)
 for n,func in [('road_camera_main.c',main_source),('road_camera_io.c',io_source),('road_camera_draw.c',draw_source)]:
  p=src/n;p.write_text(func(p.read_text()),encoding='ascii')
 p=src/'road_camera_io.h';s=p.read_text().replace('#endif','int rc_capture_frozen(uint8_t *,uint32_t *,uint32_t *,uint32_t *,uint32_t *,uint32_t *);\n#endif');p.write_text(s,encoding='ascii')
 for n in ['road_fp32.c','road_pl.c','road_conv3_pack.c','road_graph.h','road_enhance.c','road_retinex_c.c','road_vehicle_multiview.c']:
  assert sha(src/n)==sha(OLD/'source'/n),n
 old=read(OLD/'arm_complete.json');(APP/'obj').mkdir(exist_ok=rebuild);commands=[];logs=[]
 def run(cmd):
  commands.append(cmd);p=subprocess.run(cmd,capture_output=True,text=True);logs.append(p.stdout+p.stderr);(APP/'build.log').write_text('\n'.join(logs),encoding='utf-8');assert p.returncode==0,p.stderr
 templates=[[v.replace(str(OLD),str(APP)).replace(OLD.as_posix(),APP.as_posix()) for v in cmd] for cmd in old['commands']]
 ex=next(cmd for cmd in templates if any(Path(v).name=='road_vehicle_multiview.c' for v in cmd));extra=[v.replace('road_vehicle_multiview.c','road_capture_views.c').replace('road_vehicle_multiview.o','road_capture_views.o') for v in ex]
 for cmd in templates:
  if '-c' not in cmd:run(extra);cmd=cmd.copy();cmd.insert(cmd.index('-Wl,--start-group'),str(APP/'obj/road_capture_views.o'))
  run(cmd)
 elf=APP/'road_detail.elf';raw=elf.read_bytes();assert b'ROAD_CAMERA_SNAPSHOT_READY V24' in raw
 phoff=struct.unpack_from('<I',raw,28)[0];ent,num=struct.unpack_from('<HH',raw,42);loads=[]
 for i in range(num):
  typ,off,va,pa,fs,mem,fl,al=struct.unpack_from('<8I',raw,phoff+i*ent)
  if typ==1 and mem:assert 0x100000<=pa<pa+mem<=0x1000000;loads.append([pa,pa+mem])
 regions=list(old['regions'])+[['frozen_bgr800',0x1A300000,1152000]]
 for i,(n,a,l) in enumerate(regions):
  assert a+l<=0x20000000
  for n2,b,k in regions[:i]:assert a+l<=b or b+k<=a,(n,n2)
  for b,e in loads:assert a+l<=b or e<=a
 common=(OLD/'camera_common.tcl').read_text().replace('!=23','!=24');common=re.sub('elf_sha256=[0-9a-f]{64}','elf_sha256='+sha(elf),common);(APP/'camera_common.tcl').write_text(common,encoding='ascii')
 start=(OLD/'start_idle.tcl').read_text().replace('==23','==24');(APP/'start_idle.tcl').write_text(start,encoding='ascii')
 host=APP/'host';host.mkdir(exist_ok=rebuild);gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH']
 cmd=[str(gcc),'-O2','-std=c99','-Wall','-Wextra','-Werror','-I'+str(src),str(src/'road_camera_draw.c'),str(src/'road_camera_draw_host.c'),'-lm','-o',str(host/'render.exe')];p=subprocess.run(cmd,capture_output=True,text=True,env=env);assert p.returncode==0,p.stderr
 proof=dict(status='ABI24_CAMERA_ONESHOT_COMPILED_NOT_BOARD_TESTED',version=24,commands=commands,regions=regions,elf_loads=loads,elf_sha256=sha(elf),bit_sha256=sha(APP/'display.bit'),weights_sha256=sha(APP/'runtime/weights.f32'),source_sha256={p.name:sha(p) for p in src.iterdir() if p.is_file()},mail_words=160,ui_words=17,source_kind_commands=dict(precut=2,camera=4,bgr800_injection=5),frozen_source=0x1A300000,detector_and_enhancer_unchanged=True,sd_written=False)
 write(APP/'arm_complete.json',proof);write(APP/'runtime_checksums.json',{str(p.relative_to(APP)):sha(p) for p in APP.rglob('*') if p.is_file() and p.name!='runtime_checksums.json' and 'obj' not in p.relative_to(APP).parts and p.suffix not in ['.log','.map','.su']})
 print('CAMERA_SNAPSHOT_ABI24_COMPILED',sha(elf),flush=True)
if __name__=='__main__':main()
