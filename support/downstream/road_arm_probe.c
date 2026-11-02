/* Cortex-A9 standalone fixed-image probe, GPL-3.0. No SD/flash writes,
 * camera setup or display integration. DDR inputs supplied by a later JTAG test.
 * Compiled is not board-verified; do not claim timing until readback validation. */
#include "road_fp32.h"
#include "road_probe_config.h"
#include "xil_cache.h"
#include "xil_mmu.h"
#include "xil_printf.h"
#include "xtime_l.h"
#include "sleep.h"
#include <stdint.h>
#include <string.h>
#define INPUT_ADDR 0x10000000U
#define WEIGHT_ADDR 0x11000000U
#define ARENA_ADDR 0x12000000U
#define DECODE_ADDR 0x13000000U
#define PREP_ADDR 0x13200000U
#define CANDIDATE_ADDR 0x13400000U
#define KEEP_ADDR 0x13500000U
#define BOX400_ADDR 0x13600000U
#define BOX320_ADDR 0x13610000U
#define MAIL_ADDR 0x13800000U
#define TRACE_ADDR 0x14000000U
enum{M_MAGIC,M_VERSION,M_STATE,M_COMMAND,M_SEQUENCE,M_HEARTBEAT,M_ERROR,M_INPUT,M_WEIGHT,M_ARENA,M_DECODE,M_BOX400,M_PREP,M_TRACE,M_TRACE_BYTES,M_COUNT,
     M_INPUT_FNV,M_WEIGHT_FNV,M_TIMER_HZ,M_TOTAL_LO,M_TOTAL_HI,M_NETWORK_LO,M_NETWORK_HI,M_PREP_LO,M_PREP_HI,M_POST_LO,M_POST_HI,M_INPUT_EXPECTED_FNV,M_TRACE_ENABLE,M_BOX320};
static volatile uint32_t *const mail=(volatile uint32_t *)MAIL_ADDR;
static uint32_t trace_cursor;
static void barrier(void){__asm__ volatile("dsb sy" ::: "memory");}
static uint32_t fnv(const void *data,uint32_t size){const uint8_t *p=(const uint8_t *)data;uint32_t h=2166136261U,i;for(i=0;i<size;i++)h=(h^p[i])*16777619U;return h;}
static void trace(int id,const float *data,uint32_t elements,void *unused){
  (void)id;(void)unused;memcpy((void *)(TRACE_ADDR+trace_cursor),data,elements*4U);trace_cursor+=elements*4U;
}
static void pack_boxes(uint32_t address,const RoadBox *boxes,int count){
  float *p=(float *)address;int i;for(i=0;i<count;i++){
    p[6*i]=boxes[i].x1;p[6*i+1]=boxes[i].y1;p[6*i+2]=boxes[i].x2;p[6*i+3]=boxes[i].y2;p[6*i+4]=boxes[i].score;p[6*i+5]=(float)boxes[i].cls;
  }
}
static void ticks(int lo,int hi,XTime elapsed){mail[lo]=(uint32_t)elapsed;mail[hi]=(uint32_t)(elapsed>>32);}
int main(void){
  XTime begin,p0,p1,n0,n1,end,finished;int n,error;
  Xil_DCacheDisable();Xil_SetTlbAttributes(MAIL_ADDR,NORM_NONCACHE);Xil_DCacheEnable();Xil_ICacheEnable();
  memset((void *)MAIL_ADDR,0,4096);mail[M_MAGIC]=0x524F4144U;mail[M_VERSION]=1;mail[M_STATE]=1;mail[M_TIMER_HZ]=COUNTS_PER_SECOND;
  mail[M_INPUT]=INPUT_ADDR;mail[M_WEIGHT]=WEIGHT_ADDR;mail[M_ARENA]=ARENA_ADDR;mail[M_DECODE]=DECODE_ADDR;
  mail[M_BOX400]=BOX400_ADDR;mail[M_BOX320]=BOX320_ADDR;mail[M_PREP]=PREP_ADDR;mail[M_TRACE]=TRACE_ADDR;barrier();
  xil_printf("ROAD_ARM_PROBE_READY V1\r\n");
  for(;;){
    mail[M_HEARTBEAT]++;
    if(mail[M_COMMAND]!=1U){usleep(1000);continue;}
    mail[M_COMMAND]=0;mail[M_STATE]=2;mail[M_ERROR]=0;mail[M_COUNT]=0;trace_cursor=0;barrier();XTime_GetTime(&begin);
    Xil_DCacheInvalidateRange(INPUT_ADDR,400U*240U*4U);Xil_DCacheInvalidateRange(WEIGHT_ADDR,ROAD_WEIGHT_FLOATS*4U);
    mail[M_INPUT_FNV]=fnv((const void *)INPUT_ADDR,400U*240U*4U);mail[M_WEIGHT_FNV]=fnv((const void *)WEIGHT_ADDR,ROAD_WEIGHT_FLOATS*4U);
    if(mail[M_WEIGHT_FNV]!=ROAD_EXPECTED_WEIGHT_FNV){mail[M_ERROR]=10;mail[M_STATE]=4;barrier();continue;}
    if(mail[M_INPUT_EXPECTED_FNV]&&mail[M_INPUT_EXPECTED_FNV]!=mail[M_INPUT_FNV]){mail[M_ERROR]=11;mail[M_STATE]=4;barrier();continue;}
    XTime_GetTime(&p0);road_preprocess400((const uint32_t *)INPUT_ADDR,(uint8_t *)PREP_ADDR);road_input320((const uint8_t *)PREP_ADDR,(float *)ARENA_ADDR);XTime_GetTime(&p1);
    XTime_GetTime(&n0);error=road_forward((const float *)WEIGHT_ADDR,(float *)ARENA_ADDR,mail[M_TRACE_ENABLE]?trace:0,0);XTime_GetTime(&n1);
    if(error){mail[M_ERROR]=20;mail[M_STATE]=4;barrier();continue;}
    road_decode((const float *)ARENA_ADDR,(float *)DECODE_ADDR);
    n=road_nms((const float *)DECODE_ADDR,(RoadBox *)CANDIDATE_ADDR,(RoadBox *)KEEP_ADDR,300,.25f,.6f);
    if(n<0){mail[M_ERROR]=21;mail[M_STATE]=4;barrier();continue;}
    pack_boxes(BOX320_ADDR,(const RoadBox *)KEEP_ADDR,n);road_boxes_to400((RoadBox *)KEEP_ADDR,n);pack_boxes(BOX400_ADDR,(const RoadBox *)KEEP_ADDR,n);XTime_GetTime(&end);
    Xil_DCacheFlushRange(DECODE_ADDR,ROAD_CANDIDATES*9U*4U);Xil_DCacheFlushRange(PREP_ADDR,320U*320U*3U);
    Xil_DCacheFlushRange(BOX320_ADDR,(uint32_t)n*6U*4U);Xil_DCacheFlushRange(BOX400_ADDR,(uint32_t)n*6U*4U);
    if(trace_cursor)Xil_DCacheFlushRange(TRACE_ADDR,trace_cursor);
    XTime_GetTime(&finished);
    mail[M_TRACE_BYTES]=trace_cursor;mail[M_COUNT]=(uint32_t)n;ticks(M_PREP_LO,M_PREP_HI,p1-p0);ticks(M_NETWORK_LO,M_NETWORK_HI,n1-n0);
    ticks(M_POST_LO,M_POST_HI,end-n1);ticks(M_TOTAL_LO,M_TOTAL_HI,finished-begin);mail[M_SEQUENCE]++;barrier();mail[M_STATE]=3;barrier();
    xil_printf("ROAD_ARM_PROBE_DONE boxes=%d\r\n",n);
  }
}
