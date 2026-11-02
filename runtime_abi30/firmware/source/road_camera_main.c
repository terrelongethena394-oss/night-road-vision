/* Raw-camera preview + ARM custom Retinex + FP32 ARM/FPGA detection.
 * GPL-3.0 for detector-derived portions; vendor notices retained separately.
 * One CPU, no SD/Flash, enhancement is display-only ARM fusion; RAW native ROI verification uses shared PL convolutions. */
#include "road_fp32.h"
#include "road_enhance.h"
#include "road_roi_guard.h"
#include "road_detail_config.h"
#include "road_vehicle_multiview.h"
#include "road_car_pair_model.h"
#include "road_balanced_extra.h"
#include "road_balanced_config.h"
#include "road_roi_verify_hw.h"
#include "roi_model_config.h"
#define NEW_WEIGHT 0x1B000000U
static RoadBox pair_cars[300];
#include "road_capture_views.h"
#define RVM_SOURCE800 0x1A300000U
#define RVM_TILE(i) (0x1A000000U+(i)*0x60000U)
#define RVM_DECODE(i) (0x1A120000U+(i)*0x40000U)
#define RVM_BASELINE 0x1A200000U
static uint32_t rvm_baseline_count;
#include "road_enhance_config.h"
#include "road_pl.h"
#include "road_camera.h"
#include "road_camera_io.h"
#include "road_probe_config.h"
#include "xil_cache.h"
#include "xil_mmu.h"
#include "xil_printf.h"
#include "xtime_l.h"
#include "sleep.h"
#include <string.h>
enum {M_MAGIC,M_VERSION,M_STATE,M_COMMAND,M_SEQUENCE,M_HEART,M_ERROR,M_INPUT,M_WEIGHT,M_ARENA,M_DECODE,M_BOX400,M_PREP,M_TRACE,M_TRACE_BYTES,M_COUNT,
 M_INPUT_FNV,M_WEIGHT_FNV,M_HZ,M_TOTAL_LO,M_TOTAL_HI,M_NET_LO,M_NET_HI,M_PREP_LO,M_PREP_HI,M_POST_LO,M_POST_HI,M_INPUT_EXPECT,M_TRACE_ENABLE,M_BOX320,
 M_LCD,M_SLOT,M_FRAME,M_RENDER_LO,M_RENDER_HI,M_DMA_R,M_ACTIVE_ID,M_FRAME_FNV,M_LCD_STATE,M_LIVE_ID,M_CAMERA,M_DMA_W,M_LIVE_ADDR,M_RESULT_ADDR,M_RESULT_BOX,
 M_RESULT_ID,M_INPUT_ID,M_LIVE_TLO,M_LIVE_THI,M_RESULT_TLO,M_RESULT_THI,M_DONE,M_RESULT_COUNT,M_UI_ADDR,M_SERVICE_CALLS,M_VIEW_MS,M_IS_TEST,M_PAUSE_ACK,
 M_SAVED_DECODE,M_SAVED_HEAD,M_PAUSES,M_CAPTURE_SLOT,M_CYCLE_PAUSED,M_RESULT_FRAME_FNV,M_RESULT_INPUT_FNV,M_LIVE_FNV,M_RESERVED,M_SNAP_LO,M_SNAP_HI,
 M_WEIGHT_READY,M_UPDATES_IN_NN};
static volatile uint32_t *const m=(volatile uint32_t *)RC_MAIL;
static uint32_t slot,live_id,result_id,active_id,result_count,detect_ms,result_test,has_result,busy,trace_cursor,view_hz10;
static uint32_t result_mean,result_alpha,result_cap,result_pipe,result_detail;
static XTime last_view,live_ticks,result_ticks,paused_ticks;static uint32_t paused_flag;
static void barrier(void){__asm__ volatile("dsb sy" ::: "memory");}
static XTime now(void){XTime v;XTime_GetTime(&v);return v;}
static uint32_t ms(XTime t){return (uint32_t)((t*1000U+COUNTS_PER_SECOND/2U)/COUNTS_PER_SECOND);}
static void ticks(unsigned lo,XTime t){m[lo]=(uint32_t)t;m[lo+1]=(uint32_t)(t>>32);}
static uint32_t hash(const void *a,uint32_t n){const uint8_t *p=a;uint32_t v=2166136261U,i;for(i=0;i<n;i++)v=(v^p[i])*16777619U;return v;}
static void fatal(uint32_t e){m[M_ERROR]=e;m[M_STATE]=4;barrier();xil_printf("ROAD_CAMERA_FAILED %lu\r\n",(unsigned long)e);for(;;){m[M_HEART]++;usleep(1000);}}
static void present(int paused){
 RoadCameraUI ui;XTime start=now();uint32_t selected=1U-slot;
 ui.live_id=live_id;ui.result_id=result_id;ui.active_id=active_id;ui.detect_ms=detect_ms;ui.age_ms=has_result?ms(start-result_ticks):0;ui.view_hz10=view_hz10;
 ui.count=result_count;ui.has_result=has_result;ui.is_test=result_test;ui.paused=paused;ui.busy=busy;ui.mean_luma=result_mean;ui.enh_alpha=result_alpha;ui.enh_cap=result_cap;ui.pipe_mode=result_pipe|((m[175]&1U)<<8);ui.detail_mode=result_detail;ui.baseline_count=rvm_baseline_count;m[127]=has_result?RC_RAW_RESULT:RC_LIVE;
 if(road_camera_draw((uint8_t *)(RC_FRAME+selected*RC_FRAME_BYTES),(const uint32_t *)m[127],(const uint32_t *)RC_RESULT,(const float *)RC_RESULT_BOX,(const float *)RVM_BASELINE,&ui))fatal(210);
 if(rc_present(selected))fatal(211);
 slot=selected;*(RoadCameraUI *)RC_UI=ui;
 m[M_SLOT]=slot;m[M_FRAME]=RC_FRAME+slot*RC_FRAME_BYTES;m[M_LCD_STATE]=2;m[M_DMA_R]=rc_dma_error(0);m[M_DMA_W]=rc_dma_error(1);ticks(M_RENDER_LO,now()-start);barrier();
}
static void preview(void){
 uint32_t capture_slot=0;XTime a=now(),previous=last_view;
 if(rc_snapshot((uint32_t *)RC_LIVE,&capture_slot))fatal(220);
 live_ticks=now();live_id++;m[M_LIVE_ID]=live_id;m[M_CAPTURE_SLOT]=capture_slot;ticks(M_LIVE_TLO,live_ticks);ticks(M_SNAP_LO,live_ticks-a);
 if(previous){XTime dt=a-previous;if(dt)view_hz10=(uint32_t)(((uint64_t)COUNTS_PER_SECOND*10U+dt/2)/dt);}
 last_view=a;present(0);if(busy)m[M_UPDATES_IN_NN]++;
}
static void pause_service(void){
 XTime start=now();m[M_PAUSES]++;paused_flag=1;
 present(1);
 Xil_DCacheFlushRange(RC_LIVE,RC_RAW_BYTES);Xil_DCacheFlushRange(RC_RESULT,RC_RAW_BYTES);Xil_DCacheFlushRange(RC_RESULT_BOX,300U*24U);
 Xil_DCacheFlushRange(RC_RESULT_DECODE,ROAD_CANDIDATES*9U*4U);Xil_DCacheFlushRange(RC_RESULT_HEAD,58800U*4U);Xil_DCacheFlushRange(RC_UI,sizeof(RoadCameraUI));
 Xil_DCacheFlushRange(0x17400000U,696U);
 Xil_DCacheFlushRange(RC_ROI_INPUT,RC_RAW_BYTES);Xil_DCacheFlushRange(RC_ROI_RESULT,RC_RAW_BYTES);Xil_DCacheFlushRange(RC_FULL_BOX,300U*sizeof(RoadBox));Xil_DCacheFlushRange(RC_ROI_BOX,300U*sizeof(RoadBox));Xil_DCacheFlushRange(RC_FULL_DECODE,ROAD_CANDIDATES*9U*4U);Xil_DCacheFlushRange(RC_FULL_HEAD,58800U*4U);Xil_DCacheFlushRange(RC_FULL_PREP,320U*320U*3U);
 Xil_DCacheFlushRange(RC_ENH_INPUT,RC_RAW_BYTES);Xil_DCacheFlushRange(RC_RAW_RESULT,RC_RAW_BYTES);
 m[91]=has_result?hash((const void *)RC_RAW_RESULT,RC_RAW_BYTES):0;m[92]=has_result?hash((const void *)RC_RESULT,RC_RAW_BYTES):0;
 m[M_LIVE_FNV]=hash((const void *)RC_LIVE,RC_RAW_BYTES);m[M_RESULT_INPUT_FNV]=has_result?hash((const void *)RC_RESULT,RC_RAW_BYTES):0;
 m[M_FRAME_FNV]=hash((const void *)(RC_FRAME+slot*RC_FRAME_BYTES),RC_FRAME_BYTES);m[M_PAUSE_ACK]=1;m[M_STATE]=3;barrier();
 while(m[M_COMMAND]==1U){m[M_HEART]++;usleep(1000);}
 paused_ticks+=now()-start;m[M_PAUSE_ACK]=0;m[M_STATE]=busy?2:1;last_view=0;barrier();
}
static void service(void *opaque){
 (void)opaque;m[M_SERVICE_CALLS]++;m[M_HEART]++;
 if(m[M_COMMAND]==1U)pause_service();
 if(!busy&&!has_result&&(!last_view||now()-last_view>=(uint64_t)COUNTS_PER_SECOND*m[M_VIEW_MS]/1000U))preview();
}
static void boxes(uint32_t address,const RoadBox *b,int count){float *p=(float *)address;int i;for(i=0;i<count;i++){p[i*6]=b[i].x1;p[i*6+1]=b[i].y1;p[i*6+2]=b[i].x2;p[i*6+3]=b[i].y2;p[i*6+4]=b[i].score;p[i*6+5]=(float)b[i].cls;}}
static void infer(unsigned kind){
 int injected=kind!=4U;
 if(kind==2U)fatal(46);
 m[132]=m[72];
 RoadEnhanceStats es;XTime enh_start,enh_elapsed,network_ticks;unsigned pipe=m[80],detail=m[94];
 if(detail!=2U||pipe!=2U)fatal(34);
 XTime start,p0,p1,end,pause0,input_ticks;uint32_t offset=0,j,source_id;int count;
 m[156]=0;m[155]=kind;m[158]=0;
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
 m[M_INPUT_FNV]=hash((const void *)RC_INPUT,RC_RAW_BYTES);m[97]=0;if(detail){unsigned q;for(q=0;q<3;q++){m[133+q]=hash((const void *)RVM_TILE(q),RC_RAW_BYTES);if(m[136+q]&&m[133+q]!=m[136+q])fatal(36);}}
 if(injected&&m[M_INPUT_EXPECT]&&m[M_INPUT_EXPECT]!=m[M_INPUT_FNV])fatal(11);
 /* Ignore any idle-preview pause before start; subtract only pauses inside this cycle. */
 pause0=paused_ticks;start=now();busy=1;active_id=source_id;m[M_ACTIVE_ID]=active_id;m[M_INPUT_ID]=source_id;m[M_STATE]=2;m[M_UPDATES_IN_NN]=0;paused_flag=0;trace_cursor=0;present(0);
 p0=now();enh_start=now();
 if(pipe>2U)fatal(32);
 if(road_enhance((const uint32_t *)RC_INPUT,(uint32_t *)RC_ENH_INPUT,96000U,pipe==0U?0U:1U,m[81],&es,service,0))fatal(31);
 enh_elapsed=now()-enh_start;m[82]=es.mean_in;m[83]=es.mean_out;m[84]=es.alpha;m[85]=es.changed;m[86]=es.max_delta;m[87]=(uint32_t)enh_elapsed;m[88]=(uint32_t)(enh_elapsed>>32);
 {unsigned calls0=0,calls1=0,calls_roi=0,v,visible=0;uint64_t net0=0,net1=0,net_roi=0,total=0;XTime t0,t1,t2,t3;int base_count,full_count;
  XTime_GetTime(&t0);count=road_car_pair_model((const float *)RC_WEIGHT,1,pair_cars,&calls0,&net0);if(count<0||calls0!=204U)fatal(50);
  for(v=0;v<4;v++){uint32_t source=v?RVM_DECODE(v-1):RC_FULL_DECODE,dest=0x1B800000U+v*0x40000U;memcpy((void *)dest,(const void *)source,ROAD_CANDIDATES*9U*4U);Xil_DCacheFlushRange(dest,ROAD_CANDIDATES*9U*4U);}
  for(v=0;v<96000;v++){uint32_t q=((const uint32_t *)RC_INPUT)[v];total+=54U*(q&255U)+183U*((q>>8)&255U)+19U*((q>>16)&255U);}
  m[189]=total<=48ULL*256ULL*96000ULL?1U:0U;XTime_GetTime(&t1);
  if(m[189]){count=road_balanced_extra((const float *)RC_WEIGHT,(const uint8_t *)RVM_SOURCE800,pair_cars,count,(RoadBox *)RC_KEEP,&calls1,&net1);if(count<0||calls1!=153U)fatal(51);}
  else{memcpy((void *)RC_KEEP,pair_cars,(unsigned)count*sizeof(RoadBox));m[190]=m[194]=0;memset((void *)BAL_REFINER_PRED,0,900U*5U*4U);Xil_DCacheFlushRange(BAL_REFINER_PRED,900U*5U*4U);for(v=0;v<3;v++)m[180+v]=m[183+v]=0;}
  XTime_GetTime(&t2);base_count=count;memcpy((void *)ROI_BASE_STRUCT,(const void *)RC_KEEP,(unsigned)count*sizeof(RoadBox));boxes(ROI_BASE_FLOAT,(const RoadBox *)ROI_BASE_STRUCT,count);m[212]=(unsigned)count;
  for(v=0;v<(unsigned)count;v++)if(((RoadBox *)ROI_BASE_STRUCT)[v].score>=.25f){boxes(RVM_BASELINE+visible*24U,(const RoadBox *)ROI_BASE_STRUCT+v,1);visible++;}
  rvm_baseline_count=visible;m[213]=visible;Xil_DCacheFlushRange(RVM_BASELINE,visible*24U);
  if(m[189]){count=road_roi_verify_live((const float *)ROI_VERIFY_WEIGHT,(const uint8_t *)RVM_SOURCE800,(const RoadBox *)ROI_BASE_STRUCT,base_count,(RoadBox *)RC_KEEP,&calls_roi,&net_roi);if(count<0||calls_roi!=51U*m[209])fatal(60);}
  else{m[209]=0;for(v=0;v<8;v++)m[220+v]=m[228+v]=m[236+v]=m[244+v]=m[252+v]=0;boxes(ROI_FINAL_FLOAT,(const RoadBox *)RC_KEEP,count);memset((void *)ROI_PLAN_DATA,0,128U);memset((void *)ROI_LOCAL_BOXES,0,8U*300U*6U*4U);}
  full_count=count;m[214]=(unsigned)count;visible=0;for(v=0;v<(unsigned)count;v++)if(((RoadBox *)RC_KEEP)[v].score>=.25f)((RoadBox *)RC_KEEP)[visible++]=((RoadBox *)RC_KEEP)[v];count=(int)visible;
  (void)full_count;XTime_GetTime(&t3);m[104]=calls0+calls1+calls_roi;m[169]=calls0;m[170]=calls1;m[171]=rvm_baseline_count;m[172]=(unsigned)count;m[163]=1;m[215]=calls_roi;
  ticks(165,t1-t0);ticks(167,t2-t1);ticks(216,t3-t2);network_ticks=net0+net1+net_roi;m[M_WEIGHT]=RC_WEIGHT;m[M_WEIGHT_FNV]=m[161];
  m[142]=rvm_baseline_count;m[143]=RVM_BASELINE;m[99]=2;m[102]=(unsigned)count;result_detail=2;p1=p0;
  Xil_DCacheFlushRange(ROI_BASE_STRUCT,300U*sizeof(RoadBox));Xil_DCacheFlushRange(ROI_BASE_FLOAT,300U*6U*4U);Xil_DCacheFlushRange(ROI_FINAL_FLOAT,300U*6U*4U);Xil_DCacheFlushRange(ROI_LOCAL_BOXES,8U*300U*6U*4U);Xil_DCacheFlushRange(ROI_PLAN_DATA,128U);
 }
 boxes(RC_BOX400,(const RoadBox *)RC_KEEP,count);end=now();
 if(hash((const void *)RC_INPUT,RC_RAW_BYTES)!=m[M_INPUT_FNV])fatal(12);
 if(kind!=2U){m[148]=hash((const void *)RVM_SOURCE800,RC_FRAME_BYTES);if(m[145]!=m[148])fatal(45);m[158]=1;Xil_DCacheFlushRange(RVM_SOURCE800,RC_FRAME_BYTES);}
 memcpy((void *)RC_RESULT,(const void *)RC_ENH_INPUT,RC_RAW_BYTES);memcpy((void *)RC_RAW_RESULT,(const void *)RC_INPUT,RC_RAW_BYTES);result_mean=es.mean_in;result_alpha=es.alpha;result_cap=es.cap;result_pipe=pipe;m[93]=pipe;memcpy((void *)RC_RESULT_BOX,(const void *)RC_BOX400,(uint32_t)count*24U);
 memcpy((void *)RC_RESULT_DECODE,(const void *)RC_DECODE,ROAD_CANDIDATES*9U*4U);
 for(j=0;j<3;j++){const RoadTensor *t=ROAD_T+ROAD_HEADS[j];uint32_t size=(uint32_t)t->h*t->w*t->c4*4U;memcpy((void *)(RC_RESULT_HEAD+offset),(const float *)RC_ARENA+t->off,size);offset+=size;}
 has_result=1;result_id=source_id;result_ticks=input_ticks;result_test=(uint32_t)injected;result_count=(uint32_t)count;detect_ms=ms(end-start-(paused_ticks-pause0));busy=0;
 m[M_SEQUENCE]++;m[M_DONE]++;m[M_COUNT]=(uint32_t)count;m[M_RESULT_COUNT]=result_count;m[M_RESULT_ID]=result_id;m[M_IS_TEST]=result_test;m[M_CYCLE_PAUSED]=paused_flag;
 ticks(M_TOTAL_LO,end-start-(paused_ticks-pause0));ticks(M_NET_LO,network_ticks-(paused_ticks-pause0));ticks(M_PREP_LO,p1-p0);ticks(M_POST_LO,end-start-network_ticks-(p1-p0));ticks(M_RESULT_TLO,result_ticks);
 m[M_TRACE_BYTES]=trace_cursor;
 if(injected){
  Xil_DCacheFlushRange(RC_INPUT,RC_RAW_BYTES);Xil_DCacheFlushRange(RC_PREP,320U*320U*3U);Xil_DCacheFlushRange(RC_BOX320,300U*24U);Xil_DCacheFlushRange(RC_BOX400,300U*24U);
  if(trace_cursor)Xil_DCacheFlushRange(RC_TRACE,trace_cursor);
 }
 {unsigned q;Xil_DCacheFlushRange(RC_INPUT,RC_RAW_BYTES);for(q=0;q<3;q++)Xil_DCacheFlushRange(RVM_TILE(q),RC_RAW_BYTES);}
 present(0);m[156]=1;m[M_STATE]=5;barrier();
}
int main(void){
 uint32_t lcd=0,camera=0;int status;
 Xil_DCacheDisable();Xil_SetTlbAttributes(RC_MAIL,NORM_NONCACHE);Xil_DCacheEnable();Xil_ICacheEnable();memset((void *)RC_MAIL,0,4096);
 m[M_MAGIC]=0x524F4144U;m[M_VERSION]=30;m[80]=2U;m[94]=2U;m[95]=RC_ROI_INPUT;m[96]=RC_ROI_LIVE;m[105]=RC_FULL_DECODE;m[106]=RC_FULL_HEAD;m[107]=RC_FULL_BOX;m[108]=RC_ROI_BOX;m[120]=RC_ROI_RESULT;m[81]=ROAD_ENHANCE_DEFAULT_CAP;m[89]=RC_ENH_INPUT;m[90]=RC_RAW_RESULT;((volatile uint32_t *)RC_MAIL)[72]=2U;m[M_HZ]=COUNTS_PER_SECOND;m[M_VIEW_MS]=150;m[M_INPUT]=RC_INPUT;m[M_WEIGHT]=RC_WEIGHT;m[M_ARENA]=RC_ARENA;m[M_DECODE]=RC_DECODE;m[M_BOX400]=RC_BOX400;m[M_PREP]=RC_PREP;m[M_BOX320]=RC_BOX320;m[M_TRACE]=RC_TRACE;
 m[M_LIVE_ADDR]=RC_LIVE;m[M_RESULT_ADDR]=RC_RESULT;m[M_RESULT_BOX]=RC_RESULT_BOX;m[M_UI_ADDR]=RC_UI;m[M_SAVED_DECODE]=RC_RESULT_DECODE;m[M_SAVED_HEAD]=RC_RESULT_HEAD;
 m[160]=BAL_REFINER_WEIGHT;m[164]=0x1B800000U;
 m[176]=BAL_ZOOM_INPUT(0);m[177]=BAL_ZOOM_DECODE(0);m[178]=BAL_ZOOM_Y;m[179]=0x3f266666U;
 m[186]=BAL_REFINER_WEIGHT;m[187]=BAL_REFINER_PRED;m[188]=BAL_REFINER_WORK;m[191]=17549;m[192]=BAL_REFINER_FNV;m[195]=5;
 m[196]=0x3f000000U;m[197]=0x3dcccccdU;m[198]=0;m[199]=0x42414c32U;
 m[200]=0x53544631U;m[201]=411;m[202]=1005712079U;m[203]=3137536U;m[204]=0x19000000U;m[205]=0x3f000000U;m[206]=9;m[207]=1;
 m[208]=0x524f4931U;m[211]=ROI_VERIFY_WEIGHT;m[260]=ROI_BASE_FLOAT;m[261]=ROI_FINAL_FLOAT;m[262]=ROI_LOCAL_BOXES;m[263]=ROI_PLAN_DATA;m[264]=ROI_BASE_STRUCT;
 m[144]=RVM_SOURCE800;m[149]=RC_FRAME_BYTES;m[150]=800;m[151]=480;m[159]=0x46524f5aU;
 status=rc_io_init(&lcd,&camera);m[M_LCD]=lcd;m[M_CAMERA]=camera;if(status)fatal((uint32_t)(100+status));
 road_set_service(service,0);preview();m[M_STATE]=1;barrier();xil_printf("ROAD_NATIVE_ROI_READY V30 raw_preview_enhanced_detection no_sd\r\n");
 for(;;){
  service(0);
  if(m[M_COMMAND]==2U||m[M_COMMAND]==4U||m[M_COMMAND]==5U){
   unsigned kind=m[M_COMMAND];
   if(!m[M_WEIGHT_READY]){
    Xil_DCacheInvalidateRange(RC_WEIGHT,ROAD_WEIGHT_FLOATS*4U);m[M_WEIGHT_FNV]=hash((const void *)RC_WEIGHT,ROAD_WEIGHT_FLOATS*4U);
    if(m[M_WEIGHT_FNV]!=ROAD_EXPECTED_WEIGHT_FNV){m[M_ERROR]=10;m[M_COMMAND]=0;barrier();continue;}
    m[161]=m[M_WEIGHT_FNV];Xil_DCacheInvalidateRange(BAL_REFINER_WEIGHT,17549U*4U);m[162]=hash((const void *)BAL_REFINER_WEIGHT,17549U*4U);m[193]=m[162];
    if(m[162]!=BAL_REFINER_FNV){m[M_ERROR]=52;m[M_COMMAND]=0;barrier();continue;}
    Xil_DCacheInvalidateRange(ROI_VERIFY_WEIGHT,ROAD_WEIGHT_FLOATS*4U);m[210]=hash((const void *)ROI_VERIFY_WEIGHT,ROAD_WEIGHT_FLOATS*4U);if(m[210]!=ROI_MODEL_FNV){m[M_ERROR]=61;m[M_COMMAND]=0;barrier();continue;}
    m[M_WEIGHT_READY]=0x57475453U;m[M_ERROR]=0;
   }
   m[M_COMMAND]=0;
   infer(kind);
  }else if(m[M_COMMAND]==6U){m[M_COMMAND]=0;present(0);m[M_STATE]=5;barrier();}else usleep(1000);
 }
}
