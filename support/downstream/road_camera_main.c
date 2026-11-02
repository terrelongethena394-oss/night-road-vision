/* Cooperative raw-camera preview + frozen-frame FP32 road detection.
 * GPL-3.0 for detector-derived portions; vendor notices retained separately.
 * One CPU, no SD/Flash, no PL enhancement request in this application. */
#include "road_fp32.h"
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
 ui.count=result_count;ui.has_result=has_result;ui.is_test=result_test;ui.paused=paused;ui.busy=busy;
 if(road_camera_draw((uint8_t *)(RC_FRAME+selected*RC_FRAME_BYTES),(const uint32_t *)RC_LIVE,(const uint32_t *)RC_RESULT,(const float *)RC_RESULT_BOX,&ui))fatal(210);
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
 m[M_LIVE_FNV]=hash((const void *)RC_LIVE,RC_RAW_BYTES);m[M_RESULT_INPUT_FNV]=has_result?hash((const void *)RC_RESULT,RC_RAW_BYTES):0;
 m[M_FRAME_FNV]=hash((const void *)(RC_FRAME+slot*RC_FRAME_BYTES),RC_FRAME_BYTES);m[M_PAUSE_ACK]=1;m[M_STATE]=3;barrier();
 while(m[M_COMMAND]==1U){m[M_HEART]++;usleep(1000);}
 paused_ticks+=now()-start;m[M_PAUSE_ACK]=0;m[M_STATE]=busy?2:1;last_view=0;barrier();
}
static void service(void *opaque){
 (void)opaque;m[M_SERVICE_CALLS]++;m[M_HEART]++;
 if(m[M_COMMAND]==1U)pause_service();
 if(!last_view||now()-last_view>=(uint64_t)COUNTS_PER_SECOND*m[M_VIEW_MS]/1000U)preview();
}
static void trace(int id,const float *data,uint32_t n,void *p){(void)id;(void)p;memcpy((void *)(RC_TRACE+trace_cursor),data,n*4U);trace_cursor+=n*4U;}
static void boxes(uint32_t address,const RoadBox *b,int count){float *p=(float *)address;int i;for(i=0;i<count;i++){p[i*6]=b[i].x1;p[i*6+1]=b[i].y1;p[i*6+2]=b[i].x2;p[i*6+3]=b[i].y2;p[i*6+4]=b[i].score;p[i*6+5]=(float)b[i].cls;}}
static void infer(int injected){
 XTime start,p0,p1,n0,n1,end,pause0,input_ticks;uint32_t offset=0,j,source_id;int count;
 if(injected){Xil_DCacheInvalidateRange(RC_INPUT,RC_RAW_BYTES);source_id=m[M_INPUT_ID];input_ticks=now();}
 else {service(0);memcpy((void *)RC_INPUT,(const void *)RC_LIVE,RC_RAW_BYTES);source_id=live_id;input_ticks=live_ticks;}
 m[M_INPUT_FNV]=hash((const void *)RC_INPUT,RC_RAW_BYTES);
 if(injected&&m[M_INPUT_EXPECT]&&m[M_INPUT_EXPECT]!=m[M_INPUT_FNV])fatal(11);
 /* Ignore any idle-preview pause before start; subtract only pauses inside this cycle. */
 pause0=paused_ticks;start=now();busy=1;active_id=source_id;m[M_ACTIVE_ID]=active_id;m[M_INPUT_ID]=source_id;m[M_STATE]=2;m[M_UPDATES_IN_NN]=0;paused_flag=0;trace_cursor=0;
 p0=now();road_preprocess400((const uint32_t *)RC_INPUT,(uint8_t *)RC_PREP);road_input320((const uint8_t *)RC_PREP,(float *)RC_ARENA);p1=now();
 n0=now();if(road_forward((const float *)RC_WEIGHT,(float *)RC_ARENA,m[M_TRACE_ENABLE]?trace:0,0))fatal(20);n1=now();
 road_decode((const float *)RC_ARENA,(float *)RC_DECODE);count=road_nms((const float *)RC_DECODE,(RoadBox *)RC_CANDIDATES,(RoadBox *)RC_KEEP,300,.25f,.6f);if(count<0)fatal(21);
 boxes(RC_BOX320,(const RoadBox *)RC_KEEP,count);road_boxes_to400((RoadBox *)RC_KEEP,count);boxes(RC_BOX400,(const RoadBox *)RC_KEEP,count);end=now();
 if(hash((const void *)RC_INPUT,RC_RAW_BYTES)!=m[M_INPUT_FNV])fatal(12);
 memcpy((void *)RC_RESULT,(const void *)RC_INPUT,RC_RAW_BYTES);memcpy((void *)RC_RESULT_BOX,(const void *)RC_BOX400,(uint32_t)count*24U);
 memcpy((void *)RC_RESULT_DECODE,(const void *)RC_DECODE,ROAD_CANDIDATES*9U*4U);
 for(j=0;j<3;j++){const RoadTensor *t=ROAD_T+ROAD_HEADS[j];uint32_t size=(uint32_t)t->h*t->w*t->c4*4U;memcpy((void *)(RC_RESULT_HEAD+offset),(const float *)RC_ARENA+t->off,size);offset+=size;}
 has_result=1;result_id=source_id;result_ticks=input_ticks;result_test=(uint32_t)injected;result_count=(uint32_t)count;detect_ms=ms(end-start-(paused_ticks-pause0));busy=0;
 m[M_SEQUENCE]++;m[M_DONE]++;m[M_COUNT]=(uint32_t)count;m[M_RESULT_COUNT]=result_count;m[M_RESULT_ID]=result_id;m[M_IS_TEST]=result_test;m[M_CYCLE_PAUSED]=paused_flag;
 ticks(M_TOTAL_LO,end-start-(paused_ticks-pause0));ticks(M_NET_LO,n1-n0-(paused_ticks-pause0));ticks(M_PREP_LO,p1-p0);ticks(M_POST_LO,end-n1);ticks(M_RESULT_TLO,result_ticks);
 m[M_TRACE_BYTES]=trace_cursor;
 if(injected){
  Xil_DCacheFlushRange(RC_INPUT,RC_RAW_BYTES);Xil_DCacheFlushRange(RC_PREP,320U*320U*3U);Xil_DCacheFlushRange(RC_BOX320,300U*24U);Xil_DCacheFlushRange(RC_BOX400,300U*24U);
  if(trace_cursor)Xil_DCacheFlushRange(RC_TRACE,trace_cursor);
 }
 present(0);m[M_STATE]=injected?5:1;barrier();
}
int main(void){
 uint32_t lcd=0,camera=0;int status;
 Xil_DCacheDisable();Xil_SetTlbAttributes(RC_MAIL,NORM_NONCACHE);Xil_DCacheEnable();Xil_ICacheEnable();memset((void *)RC_MAIL,0,4096);
 m[M_MAGIC]=0x524F4144U;m[M_VERSION]=10;m[M_HZ]=COUNTS_PER_SECOND;m[M_VIEW_MS]=150;m[M_INPUT]=RC_INPUT;m[M_WEIGHT]=RC_WEIGHT;m[M_ARENA]=RC_ARENA;m[M_DECODE]=RC_DECODE;m[M_BOX400]=RC_BOX400;m[M_PREP]=RC_PREP;m[M_BOX320]=RC_BOX320;m[M_TRACE]=RC_TRACE;
 m[M_LIVE_ADDR]=RC_LIVE;m[M_RESULT_ADDR]=RC_RESULT;m[M_RESULT_BOX]=RC_RESULT_BOX;m[M_UI_ADDR]=RC_UI;m[M_SAVED_DECODE]=RC_RESULT_DECODE;m[M_SAVED_HEAD]=RC_RESULT_HEAD;
 status=rc_io_init(&lcd,&camera);m[M_LCD]=lcd;m[M_CAMERA]=camera;if(status)fatal((uint32_t)(100+status));
 road_set_service(service,0);preview();m[M_STATE]=1;barrier();xil_printf("ROAD_CAMERA_READY V10 raw_preview_frozen_result no_sd\r\n");
 for(;;){
  service(0);
  if(m[M_COMMAND]==2U||m[M_COMMAND]==3U){
   int injected=m[M_COMMAND]==2U;
   if(!m[M_WEIGHT_READY]){
    Xil_DCacheInvalidateRange(RC_WEIGHT,ROAD_WEIGHT_FLOATS*4U);m[M_WEIGHT_FNV]=hash((const void *)RC_WEIGHT,ROAD_WEIGHT_FLOATS*4U);
    if(m[M_WEIGHT_FNV]!=ROAD_EXPECTED_WEIGHT_FNV){m[M_ERROR]=10;m[M_COMMAND]=0;barrier();continue;}
    m[M_WEIGHT_READY]=0x57475453U;m[M_ERROR]=0;
   }
   if(injected)m[M_COMMAND]=0;
   infer(injected);
  }else usleep(1000);
 }
}
