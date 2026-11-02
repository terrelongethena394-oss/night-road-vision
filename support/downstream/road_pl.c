/* GPL-3.0. Original FP32 order and packing, no quantization or SD/Flash. */
#include "road_pl.h"
#include "road_pl_layout.h"
#include <math.h>
#include <stddef.h>
#include <string.h>
int road_pack_conv3(const float *,const float *,int,int,int,float *,size_t);
#ifdef ROAD_PL_EMULATE
static float host_packed[ROAD_PL_PACKED_BYTES/4];
static float *const packed=host_packed;
unsigned road_pl_host_calls;
const float *road_pl_host_packed(void){return packed;}
#else
#include "xil_cache.h"
#include "xil_io.h"
#include "xtime_l.h"
#include "sleep.h"
#include "xroad_conv3_fp32_hw.h"
#define CORE 0x43C30000U
static float *const packed=(float *)0x18000000U;
static volatile unsigned *const telemetry=(volatile unsigned *)(0x13800000U+72U*4U);
static XTime now(void){XTime t;XTime_GetTime(&t);return t;}
static void barrier(void){__asm__ volatile("dsb sy" ::: "memory");}
static void wr(unsigned off,unsigned v){Xil_Out32(CORE+off,v);}
static unsigned rd(unsigned off){return Xil_In32(CORE+off);}
static void ptr(unsigned off,const void *p){wr(off,(unsigned)p);wr(off+4,0);}
#endif
static int ready;
int road_pl_prepare(const float *weights){
 unsigned n;memset(packed,0,ROAD_PL_PACKED_BYTES);
 for(n=1;n<ROAD_TENSORS;n++)if(ROAD_PL_LAYOUT[n].bytes){
  const RoadOp *op=ROAD_OPS+n-1;const RoadTensor *in=ROAD_T+op->in[0],*out=ROAD_T+n;
  if(road_pack_conv3(weights+op->wo,weights+op->bo,in->c4,out->c4,8,packed+ROAD_PL_LAYOUT[n].offset/4,ROAD_PL_LAYOUT[n].bytes/4))return 1;
 }
#ifndef ROAD_PL_EMULATE
 Xil_DCacheFlushRange((INTPTR)packed,ROAD_PL_PACKED_BYTES);barrier();telemetry[5]=0x5041434BU;
#endif
 ready=1;return 0;
}
void road_pl_begin(void){
#ifdef ROAD_PL_EMULATE
 road_pl_host_calls=0;
#else
 telemetry[1]=0;telemetry[2]=0;telemetry[3]=0;telemetry[4]=0;
#endif
}
static float silu(float x){if(x>=0.0f)return x*(1.0f/(1.0f+expf(-x)));{float e=expf(x);return x*(e/(1.0f+e));}}
int road_pl_try(int node,const RoadOp *op,const RoadTensor *in,const RoadTensor *out,const float *a,const float *weights,float *b,void (*poll)(void)){
 unsigned y,x,c;const float *w;
 (void)weights;
 if(op->k!=3||!ROAD_PL_LAYOUT[node].bytes)return 0;
#ifndef ROAD_PL_EMULATE
 if(telemetry[0]==0 || (telemetry[0]==1 && !ROAD_PL_LAYOUT[node].selected))return 0;
#endif
 if(!ready)return -1;
 w=packed+ROAD_PL_LAYOUT[node].offset/4;
#ifdef ROAD_PL_EMULATE
 /* Independent scalar reference through the packed layout, for host integration checks. */
 for(y=0;y<(unsigned)out->h;y++)for(x=0;x<(unsigned)out->w;x++)for(c=0;c<(unsigned)out->c4;c++){
  unsigned block=c/8,lane=c%8,base=block*(9U*in->c4+1U)*8U;float sum=w[base+lane];int ky,kx,ic;
  for(ky=0;ky<3;ky++)for(kx=0;kx<3;kx++){
   int iy=(int)y*op->s+ky-1,ix=(int)x*op->s+kx-1;
   if(iy<0||iy>=in->h||ix<0||ix>=in->w)continue;
   for(ic=0;ic<in->c4;ic++){volatile float product=a[(iy*in->w+ix)*in->c4+ic]*w[base+(1U+(ky*3+kx)*in->c4+ic)*8U+lane];sum=sum+product;}
  }
  b[(y*out->w+x)*out->c4+c]=sum;
 }
 road_pl_host_calls++;
#else
 {
  unsigned ni=(unsigned)in->h*in->w*in->c4*4U,no=(unsigned)out->h*out->w*out->c4*4U;
  XTime start=now(),last,t,elapsed;uint64_t total;
  Xil_DCacheFlushRange((INTPTR)a,ni);Xil_DCacheFlushRange((INTPTR)b,no);Xil_DCacheInvalidateRange((INTPTR)b,no);barrier();
  if(!(rd(XROAD_CONV3_FP32_CONTROL_ADDR_AP_CTRL)&4U)){telemetry[2]=11;return -11;}
  ptr(XROAD_CONV3_FP32_CONTROL_ADDR_INPUT_R_DATA,a);ptr(XROAD_CONV3_FP32_CONTROL_ADDR_WEIGHTS_MEM_DATA,w);ptr(XROAD_CONV3_FP32_CONTROL_ADDR_OUTPUT_R_DATA,b);
  wr(XROAD_CONV3_FP32_CONTROL_ADDR_HEIGHT_DATA,(unsigned)in->h);wr(XROAD_CONV3_FP32_CONTROL_ADDR_WIDTH_DATA,(unsigned)in->w);wr(XROAD_CONV3_FP32_CONTROL_ADDR_IC4_DATA,(unsigned)in->c4);wr(XROAD_CONV3_FP32_CONTROL_ADDR_OC4_DATA,(unsigned)out->c4);wr(XROAD_CONV3_FP32_CONTROL_ADDR_STRIDE_DATA,(unsigned)op->s);
  barrier();last=now();wr(XROAD_CONV3_FP32_CONTROL_ADDR_AP_CTRL,1);
  while(!(rd(XROAD_CONV3_FP32_CONTROL_ADDR_AP_CTRL)&2U)){
   t=now();if(t-start>(XTime)COUNTS_PER_SECOND*5U){telemetry[2]=12;return -12;}
   if(t-last>COUNTS_PER_SECOND/1000U){if(poll)poll();last=now();}usleep(10);
  }
  if(rd(XROAD_CONV3_FP32_CONTROL_ADDR_AP_RETURN)){telemetry[2]=13;return -13;}
  Xil_DCacheInvalidateRange((INTPTR)b,no);barrier();elapsed=now()-start;
  total=telemetry[3]|((uint64_t)telemetry[4]<<32);total+=elapsed;telemetry[3]=(unsigned)total;telemetry[4]=(unsigned)(total>>32);telemetry[1]++;
 }
#endif
 if(op->act)for(y=0;y<(unsigned)out->h;y++){
  for(x=0;x<(unsigned)out->w;x++)for(c=0;c<(unsigned)out->c;c++){float *v=b+(y*out->w+x)*out->c4+c;*v=silu(*v);}
  if(poll)poll();
 }
 return 1;
}
