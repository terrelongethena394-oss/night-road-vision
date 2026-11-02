"""Build a reversible two-pass experiment. ROI is OFF by default; never writes SD."""
from pathlib import Path
import re,shutil,struct,subprocess,os
import cv2,numpy as np
from road_roi_spatial_common import ROOT,BASE,GUARD,read,write,sha
CURRENT=BASE.parent/'road_enhance_20261027/firmware'
HERE=Path(__file__).resolve().parent
BSP=BASE.parent/'multinex_static_20261025/vitis_ws/static_platform/export/static_platform/sw/static_platform/standalone_domain'
TOOLS=Path('E:/Xilinx/Vitis/2020.2/gnu/aarch32/nt/gcc-arm-none-eabi/bin')

def fnv(b):
 h=2166136261
 for v in b:h=((h^v)*16777619)&0xffffffff
 return h

def main():
 assert (ROOT/'native_detector_complete.json').exists() and (ROOT/'native_pipeline/complete.json').exists()
 # This build intentionally excludes the verifier: same-cohort ablation found no benefit.
 assert (ROOT/'fresh_ablation/complete.json').exists();old=read(CURRENT/'arm_complete.json')
 for n,h in read(CURRENT/'runtime_checksums.json').items():assert sha(CURRENT/n)==h,n
 app=ROOT/'firmware_experiment';app.mkdir(exist_ok=False);src=app/'source';shutil.copytree(CURRENT/'source',src)
 for n in ['road_roi_guard.c','road_roi_guard.h']:shutil.copy2(HERE/n,src/n)
 header=(src/'road_camera.h').read_text(encoding='utf-8').replace('uint32_t mean_luma,enh_alpha,enh_cap,pipe_mode;','uint32_t mean_luma,enh_alpha,enh_cap,pipe_mode,detail_mode;')
 header=header.replace('#define RC_RAW_BYTES', '#define RC_ROI_LIVE 0x16800000U\n#define RC_ROI_INPUT 0x16900000U\n#define RC_ROI_RESULT 0x16A00000U\n#define RC_FULL_BOX 0x17000000U\n#define RC_ROI_BOX 0x17010000U\n#define RC_FUSED_BOX 0x17020000U\n#define RC_FULL_DECODE 0x17100000U\n#define RC_FULL_HEAD 0x17200000U\n#define RC_FULL_PREP 0x17300000U\n#define RC_RAW_BYTES')
 (src/'road_camera.h').write_text(header,encoding='ascii')
 policy=read(GUARD/'selected.json')['chosen']['policy'];values=[policy['border'],*policy['person_aspect'],*policy['weights'],policy['dedup_iou'],policy['dedup_containment']]
 (src/'road_detail_config.h').write_text('static const RoadRoiPolicy ROAD_DETAIL_POLICY={%sf,%sf,%sf,{%s},%sf,%sf};\n'%tuple([str(v) for v in values[:3]]+[','.join(str(v)+'f' for v in values[3:7])]+[str(v) for v in values[7:]]),encoding='ascii')
 c=(src/'road_camera_main.c').read_text(encoding='utf-8')
 def replace(a,b):
  nonlocal c
  assert c.count(a)==1,(a,c.count(a));c=c.replace(a,b)
 replace('#include "road_enhance.h"','#include "road_enhance.h"\n#include "road_roi_guard.h"\n#include "road_detail_config.h"')
 replace('static uint32_t result_mean,result_alpha,result_cap,result_pipe;','static uint32_t result_mean,result_alpha,result_cap,result_pipe,result_detail;')
 replace('ui.pipe_mode=result_pipe;','ui.pipe_mode=result_pipe;ui.detail_mode=result_detail;m[127]=(result_test&&has_result)?RC_RAW_RESULT:RC_LIVE;')
 replace('(const uint32_t *)RC_LIVE,(const uint32_t *)RC_RESULT,','(const uint32_t *)m[127],(const uint32_t *)RC_RESULT,')
 replace(' RoadEnhanceStats es;XTime enh_start,enh_elapsed;unsigned pipe=m[80];',' RoadEnhanceStats es;XTime enh_start,enh_elapsed;unsigned pipe=m[80],detail=m[94];\n if(detail>1U||(detail&&pipe==1U))fatal(34);')
 replace('XTime enh_start,enh_elapsed;','XTime enh_start,enh_elapsed,network_ticks;')
 replace('fatal(20);n1=now();','fatal(20);n1=now();network_ticks=n1-n0;')
 replace('ticks(M_NET_LO,n1-n0-(paused_ticks-pause0));','ticks(M_NET_LO,network_ticks-(paused_ticks-pause0));')
 replace('ticks(M_POST_LO,end-n1);','ticks(M_POST_LO,end-start-network_ticks-(p1-p0));')
 replace('if(injected){Xil_DCacheInvalidateRange(RC_INPUT,RC_RAW_BYTES);source_id=', 'if(injected){Xil_DCacheInvalidateRange(RC_INPUT,RC_RAW_BYTES);if(detail)Xil_DCacheInvalidateRange(RC_ROI_INPUT,RC_RAW_BYTES);source_id=')
 replace('else {service(0);memcpy((void *)RC_INPUT,','else {if(detail){preview();memcpy((void *)RC_ROI_INPUT,(const void *)RC_ROI_LIVE,RC_RAW_BYTES);}else service(0);memcpy((void *)RC_INPUT,')
 replace('m[M_INPUT_FNV]=hash((const void *)RC_INPUT,RC_RAW_BYTES);','m[M_INPUT_FNV]=hash((const void *)RC_INPUT,RC_RAW_BYTES);m[97]=detail?hash((const void *)RC_ROI_INPUT,RC_RAW_BYTES):0;if(injected&&detail&&m[98]&&m[98]!=m[97])fatal(36);')
 needle='boxes(RC_BOX320,(const RoadBox *)RC_KEEP,count);road_boxes_to400((RoadBox *)RC_KEEP,count);boxes(RC_BOX400,(const RoadBox *)RC_KEEP,count);end=now();'
 stage='''boxes(RC_BOX320,(const RoadBox *)RC_KEEP,count);road_boxes_to400((RoadBox *)RC_KEEP,count);
 m[100]=(uint32_t)count;m[101]=0;m[103]=m[73];m[104]=m[73];ticks(110,n1-n0);ticks(112,0);ticks(114,0);ticks(116,0);
 if(detail){
  XTime a,b;int nr,nf=count,k,kept=0;uint32_t o=0;
  memcpy((void *)RC_FULL_BOX,(const void *)RC_KEEP,(uint32_t)nf*sizeof(RoadBox));
  memcpy((void *)RC_FULL_DECODE,(const void *)RC_DECODE,ROAD_CANDIDATES*9U*4U);memcpy((void *)RC_FULL_PREP,(const void *)RC_PREP,320U*320U*3U);
  for(k=0;k<3;k++){const RoadTensor *t=ROAD_T+ROAD_HEADS[k];uint32_t size=(uint32_t)t->h*t->w*t->c4*4U;memcpy((void *)(RC_FULL_HEAD+o),(const float *)RC_ARENA+t->off,size);o+=size;}
  a=now();road_preprocess400((const uint32_t *)RC_ROI_INPUT,(uint8_t *)RC_PREP);road_input320((const uint8_t *)RC_PREP,(float *)RC_ARENA);ticks(114,now()-a);
  road_pl_begin();a=now();if(road_forward((const float *)RC_WEIGHT,(float *)RC_ARENA,0,0))fatal(37);b=now();network_ticks+=b-a;ticks(112,b-a);m[104]+=m[73];
  road_decode((const float *)RC_ARENA,(float *)RC_DECODE);nr=road_nms((const float *)RC_DECODE,(RoadBox *)RC_CANDIDATES,(RoadBox *)RC_KEEP,300,.25f,.6f);if(nr<0)fatal(38);
  road_boxes_to400((RoadBox *)RC_KEEP,nr);nr=road_roi_map400((RoadBox *)RC_KEEP,nr);if(nr<0)fatal(39);m[101]=(uint32_t)nr;memcpy((void *)RC_ROI_BOX,(const void *)RC_KEEP,(uint32_t)nr*sizeof(RoadBox));
  a=now();count=road_roi_fuse((const RoadBox *)RC_FULL_BOX,nf,(const RoadBox *)RC_ROI_BOX,nr,&ROAD_DETAIL_POLICY,(RoadBox *)RC_FUSED_BOX,300);if(count<0)fatal(40);
  for(k=0;k<count;k++)if(((RoadBox *)RC_FUSED_BOX)[k].score>=.25f)((RoadBox *)RC_KEEP)[kept++]=((RoadBox *)RC_FUSED_BOX)[k];count=kept;ticks(116,now()-a);
  if(hash((const void *)RC_ROI_INPUT,RC_RAW_BYTES)!=m[97])fatal(41);memcpy((void *)RC_ROI_RESULT,(const void *)RC_ROI_INPUT,RC_RAW_BYTES);m[119]=hash((const void *)RC_ROI_RESULT,RC_RAW_BYTES);
 }
 m[99]=detail;m[102]=(uint32_t)count;result_detail=detail;
 boxes(RC_BOX400,(const RoadBox *)RC_KEEP,count);end=now();'''
 replace(needle,stage)
 replace('m[M_VERSION]=13;','m[M_VERSION]=15;')
 replace('m[80]=2U;','m[80]=2U;m[94]=0U;m[95]=RC_ROI_INPUT;m[96]=RC_ROI_LIVE;m[105]=RC_FULL_DECODE;m[106]=RC_FULL_HEAD;m[107]=RC_FULL_BOX;m[108]=RC_ROI_BOX;m[120]=RC_ROI_RESULT;')
 replace('ROAD_ENHANCE_CAMERA_READY V13','ROAD_ROI_EXPERIMENT_READY V15')
 replace(' Xil_DCacheFlushRange(RC_ENH_INPUT,RC_RAW_BYTES);',' Xil_DCacheFlushRange(RC_ROI_INPUT,RC_RAW_BYTES);Xil_DCacheFlushRange(RC_ROI_RESULT,RC_RAW_BYTES);Xil_DCacheFlushRange(RC_FULL_BOX,300U*sizeof(RoadBox));Xil_DCacheFlushRange(RC_ROI_BOX,300U*sizeof(RoadBox));Xil_DCacheFlushRange(RC_FULL_DECODE,ROAD_CANDIDATES*9U*4U);Xil_DCacheFlushRange(RC_FULL_HEAD,58800U*4U);Xil_DCacheFlushRange(RC_FULL_PREP,320U*320U*3U);\n Xil_DCacheFlushRange(RC_ENH_INPUT,RC_RAW_BYTES);')
 (src/'road_camera_main.c').write_text(c,encoding='ascii')
 io=(src/'road_camera_io.c').read_text(encoding='utf-8').replace('#include "road_camera.h"','#include "road_camera.h"\n#include "road_roi_guard.h"').replace(' road_camera_average(src,dest);',' road_camera_average(src,dest);if(((volatile uint32_t *)RC_MAIL)[94])road_roi_from_bgr800(src,(uint32_t *)RC_ROI_LIVE);');(src/'road_camera_io.c').write_text(io,encoding='ascii')
 draw=(src/'road_camera_draw.c').read_text(encoding='utf-8').replace('u->pipe_mode==1U?"ENH INPUT + DET"','u->detail_mode?"DETAIL X2 / EXPERIMENT":u->pipe_mode==1U?"ENH INPUT + DET"').replace('text(f,10,14,"LIVE RAW",','text(f,10,14,u->is_test?"STATIC RAW":"LIVE RAW",');(src/'road_camera_draw.c').write_text(draw,encoding='ascii')
 for n in ['display.bit','display.xsa','ps7_init.tcl','Xilinx.spec']:shutil.copy2(CURRENT/n,app/n)
 runtime=app/'runtime';runtime.mkdir();shutil.copy2(CURRENT/'runtime/weights.f32',runtime/'weights.f32')
 records=[];cases=read(ROOT/'native_detector_full/complete.json')['cases']
 for r in cases:
  if r['name']=='control_random':continue
  p=runtime/'cases'/r['name'];p.mkdir(parents=True)
  for kind,outname in [('native_detector_full','input400.u32'),('native_detector_roi','roi400.u32')]:shutil.copy2(ROOT/kind/'cases'/r['name']/'input400.u32',p/outname)
  if r['kind']=='real':
   image=cv2.imread(str(ROOT/'fresh/images'/r['source']))[:,:,::-1].copy();a=cv2.resize(image,(800,480),interpolation=cv2.INTER_LINEAR);a[:,:,0]&=248;a[:,:,1]&=252;a[:,:,2]&=248
  else:a=np.zeros((480,800,3),np.uint8)
  b=a.astype(np.uint16);full=((b[0::2,0::2]+b[0::2,1::2]+b[1::2,0::2]+b[1::2,1::2]+2)//4).astype(np.uint32);roi=a[120:360,200:600].astype(np.uint32)
  assert (full[:,:,0]|(full[:,:,1]<<8)|(full[:,:,2]<<16)).astype('<u4').tobytes()==(p/'input400.u32').read_bytes();assert (roi[:,:,0]|(roi[:,:,1]<<8)|(roi[:,:,2]<<16)).astype('<u4').tobytes()==(p/'roi400.u32').read_bytes();records.append(dict(name=r['name'],input_fnv=fnv((p/'input400.u32').read_bytes()),roi_fnv=fnv((p/'roi400.u32').read_bytes())))
 obj=app/'obj';obj.mkdir();commands=[];logs=[]
 def run(cmd):
  cmd=list(map(str,cmd));commands.append(cmd);p=subprocess.run(cmd,capture_output=True,text=True);logs.append(p.stdout+p.stderr);(app/'build.log').write_text('\n'.join(logs),encoding='utf-8');assert p.returncode==0,p.stderr
 flags=['-mcpu=cortex-a9','-mfpu=neon-vfpv3','-mfloat-abi=hard','-O3','-std=c99','-ffp-contract=off','-fno-fast-math','-fno-common','-Wall','-g','-fstack-usage','-I'+str(src),'-I'+str(BSP/'bspinclude/include')]
 files=[src/n for n in ['road_fp32.c','road_pl.c','road_conv3_pack.c','road_enhance.c','road_roi_guard.c','road_camera_main.c','road_camera_io.c','road_camera_draw.c','road_camera_average.c']]+[p for d in ['display_ctrl','clk_wiz','vdma_api','emio_sccb_cfg','ov5640'] for p in sorted((src/d).glob('*.c'))];objects=[]
 for p in files:
  o=obj/('_'.join(p.relative_to(src).parts)+'.o');strict=['-Wextra','-Werror','-Wno-misleading-indentation'] if p.parent==src else [];run([TOOLS/'arm-none-eabi-gcc.exe',*flags,*strict,'-c',p,'-o',o]);objects.append(o)
 elf=app/'road_detail.elf';run([TOOLS/'arm-none-eabi-gcc.exe',*flags[:3],'-Wl,-build-id=none','-specs='+str(app/'Xilinx.spec'),'-Wl,-T,'+str(src/'lscript.ld'),'-Wl,-Map,'+str(app/'road_detail.map'),'-L'+str(BSP/'bsplib/lib'),'-o',elf,*objects,'-Wl,--start-group','-lxil','-lgcc','-lc','-lm','-Wl,--end-group'])
 host=app/'host';host.mkdir();run(['E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe','-O2','-std=c99','-Wall','-Wextra','-Werror','-I'+str(src),src/'road_camera_draw.c',src/'road_camera_draw_host.c','-lm','-o',host/'render.exe'])
 raw=elf.read_bytes();phoff=struct.unpack_from('<I',raw,28)[0];ent,n=struct.unpack_from('<HH',raw,42);loads=[]
 for i in range(n):
  typ,off,va,pa,fs,mem,fl,al=struct.unpack_from('<8I',raw,phoff+i*ent)
  if typ==1 and mem:assert 0x100000<=pa<pa+mem<=0x1000000;loads.append([pa,pa+mem])
 regions=old['regions']+[['roi_live',0x16800000,384000],['roi_input',0x16900000,384000],['roi_result',0x16a00000,384000],['full_boxes',0x17000000,8400],['roi_boxes',0x17010000,8400],['fused_boxes',0x17020000,8400],['full_decode',0x17100000,226800],['full_head',0x17200000,235200],['full_preprocess',0x17300000,307200]]
 for i,(name,a,n) in enumerate(regions):
  for n2,b,l in regions[i+1:]:assert a+n<=b or b+l<=a,(name,n2)
  for b,e in loads:assert a+n<=b or e<=a
 common=(CURRENT/'camera_common.tcl').read_text(encoding='utf-8').replace('!=13','!=15').replace(old['elf_sha256'],sha(elf));(app/'camera_common.tcl').write_text(common,encoding='ascii')
 scan=(CURRENT/'scan_only.tcl').read_text(encoding='utf-8').replace('ROAD_ENHANCE_SCAN_READY','ROAD_DETAIL_SCAN_READY');(app/'scan_only.tcl').write_text(scan,encoding='ascii')
 write(app/'arm_complete.json',dict(status='EXPERIMENTAL_DETAIL_ARM_COMPILED_NOT_BOARD_TESTED',version=15,default_roi_mode=0,default_pipe=2,verifier_included=False,reason_verifier_excluded='Same-cohort ablation did not improve precision/recall.',geometry_not_qualified_as_default='First heldout personFP exceeded frozen default-upgrade limit; candidate is a reversible diagnostic mode.',bit_unchanged=True,weights_unchanged=True,elf_sha256=sha(elf),bit_sha256=sha(app/'display.bit'),weights_sha256=sha(runtime/'weights.f32'),cases=records,regions=regions,elf_loads=loads,commands=commands,hardware_access=False,sd_written=False));print('EXPERIMENTAL_ROI_ARM_COMPILED_DEFAULT_OFF',flush=True)
if __name__=='__main__':main()
