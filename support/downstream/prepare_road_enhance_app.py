"""Clone verified FP32 hybrid and add an ARM tone-curve input stage; no board calls."""
from pathlib import Path
import json,shutil
from road_enhance_common import ROOT,OLD,sha,write
HERE=Path(__file__).resolve().parent
def replace(s,a,b):assert s.count(a)==1,a;return s.replace(a,b)
def main():
 app=ROOT/'firmware';app.mkdir(exist_ok=False);src=app/'source';shutil.copytree(OLD/'source',src)
 for n in ['road_enhance.c','road_enhance.h','road_enhance_tables.h']:shutil.copy2(ROOT/'source'/n,src/n)
 for n in ['display.bit','display.xsa','ps7_init.tcl','Xilinx.spec','YOLOv5_LICENSE']:
  if (OLD/n).exists():shutil.copy2(OLD/n,app/n)
 h=(src/'road_camera.h').read_text();h=replace(h,'#define RC_UI 0x16500000U','#define RC_UI 0x16500000U\n#define RC_ENH_INPUT 0x16600000U\n#define RC_RAW_RESULT 0x16700000U')
 h=replace(h,'uint32_t count,has_result,is_test,paused,busy;','uint32_t count,has_result,is_test,paused,busy;\n uint32_t mean_luma,enh_alpha,enh_cap,pipe_mode;');(src/'road_camera.h').write_text(h,encoding='ascii')
 s=(src/'road_camera_main.c').read_text();s=replace(s,'#include "road_fp32.h"','#include "road_fp32.h"\n#include "road_enhance.h"\n#include "road_enhance_config.h"')
 s=replace(s,'static XTime last_view','static uint32_t result_mean,result_alpha,result_cap,result_pipe;\nstatic XTime last_view')
 s=replace(s,'ui.busy=busy;','ui.busy=busy;ui.mean_luma=result_mean;ui.enh_alpha=result_alpha;ui.enh_cap=result_cap;ui.pipe_mode=result_pipe;')
 s=replace(s,'Xil_DCacheFlushRange(RC_UI,sizeof(RoadCameraUI));','Xil_DCacheFlushRange(RC_UI,sizeof(RoadCameraUI));\n Xil_DCacheFlushRange(RC_ENH_INPUT,RC_RAW_BYTES);Xil_DCacheFlushRange(RC_RAW_RESULT,RC_RAW_BYTES);\n m[91]=has_result?hash((const void *)RC_RAW_RESULT,RC_RAW_BYTES):0;m[92]=has_result?hash((const void *)RC_RESULT,RC_RAW_BYTES):0;')
 s=replace(s,'static void infer(int injected){','static void infer(int injected){\n RoadEnhanceStats es;XTime enh_start,enh_elapsed;unsigned pipe=m[80];')
 s=replace(s,'p0=now();road_preprocess400((const uint32_t *)RC_INPUT,(uint8_t *)RC_PREP);',
 '''p0=now();enh_start=now();
 if(pipe>2U)fatal(32);
 if(road_enhance((const uint32_t *)RC_INPUT,(uint32_t *)RC_ENH_INPUT,96000U,pipe==0U?0U:1U,m[81],&es,service,0))fatal(31);
 enh_elapsed=now()-enh_start;m[82]=es.mean_in;m[83]=es.mean_out;m[84]=es.alpha;m[85]=es.changed;m[86]=es.max_delta;m[87]=(uint32_t)enh_elapsed;m[88]=(uint32_t)(enh_elapsed>>32);
 road_preprocess400((const uint32_t *)(pipe==1U?RC_ENH_INPUT:RC_INPUT),(uint8_t *)RC_PREP);''')
 s=replace(s,'memcpy((void *)RC_RESULT,(const void *)RC_INPUT,RC_RAW_BYTES);',
 'memcpy((void *)RC_RESULT,(const void *)RC_ENH_INPUT,RC_RAW_BYTES);memcpy((void *)RC_RAW_RESULT,(const void *)RC_INPUT,RC_RAW_BYTES);result_mean=es.mean_in;result_alpha=es.alpha;result_cap=es.cap;result_pipe=pipe;m[93]=pipe;')
 s=replace(s,'m[M_VERSION]=11;','m[M_VERSION]=13;m[80]=2U;m[81]=ROAD_ENHANCE_DEFAULT_CAP;m[89]=RC_ENH_INPUT;m[90]=RC_RAW_RESULT;')
 s=replace(s,'ROAD_HYBRID_CAMERA_READY V11 raw_preview_frozen_result no_sd','ROAD_ENHANCE_CAMERA_READY V13 raw_preview_enhanced_detection no_sd')
 s=s.replace('Cooperative raw-camera preview + frozen-frame FP32 road detection.','Raw-camera preview + ARM adaptive gamma + FP32 ARM/FPGA detection.')
 s=s.replace('no PL enhancement request in this application.','enhancement is ARM integer LUT; convolution acceleration remains in PL.')
 (src/'road_camera_main.c').write_text(s,encoding='ascii')
 d=(src/'road_camera_draw.c').read_text();d=replace(d,'"LIVE CAMERA"','"LIVE RAW"');d=replace(d,'"LAST DETECTION"','u->pipe_mode==1U?"ENH INPUT + DET":(u->pipe_mode==2U?"ENH VIEW / RAW DET":"RAW + DETECTION")')
 d=replace(d,'text(f,10,440,"BOXES APPLY TO RIGHT IMAGE ONLY",2,0xFFFFFF);',
 '''if(u->has_result){
  if(!u->enh_alpha)snprintf(s,sizeof(s),"BYPASS / MEAN %u / BOXES ON RIGHT",(unsigned)u->mean_luma);
  else snprintf(s,sizeof(s),"ENH %u%% / MEAN %u / BOXES ON RIGHT",(unsigned)((u->enh_alpha*100U+128U)/256U),(unsigned)u->mean_luma);
  text(f,10,440,s,2,0xFFFFFF);
 }else text(f,10,440,"AUTO GAMMA / BRIGHT AREAS PROTECTED",2,0xFFFFFF);''')
 (src/'road_camera_draw.c').write_text(d,encoding='ascii')
 (app/'runtime').mkdir();shutil.copy2(OLD/'runtime/weights.f32',app/'runtime/weights.f32')
 assert sha(app/'display.bit')==sha(OLD/'display.bit');assert sha(app/'runtime/weights.f32')==sha(OLD/'runtime/weights.f32')
 write(app/'source_prepared.json',dict(status='ARM_ENHANCEMENT_PLUS_EXISTING_FP32_HYBRID_SOURCE_PREPARED',mailbox_version=13,default_mode=2,mode2='Enhanced display, raw detector input',mode1='Experimental enhanced detector input',mode0='Raw detector and display',display_bit_unchanged=True,detector_weights_unchanged=True,enhancement_processor='ARM',neural_enhancer=False,enhanced_input_address=0x16600000,raw_frozen_result_address=0x16700000,hardware_access=False,sd_written=False));print('ROAD_ENHANCE_APP_SOURCE_READY',flush=True)
if __name__=='__main__':main()
