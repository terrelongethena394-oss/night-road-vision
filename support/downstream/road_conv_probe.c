/* Standalone single-layer CPU/PL A/B probe for the NEW convolution-test bit.
 * Offline candidate only. Not a camera app; no SD orFlash writes. GPL-3.0. */
#include <stdint.h>
#include <string.h>
#include <math.h>
#include "xil_io.h"
#include "xil_cache.h"
#include "xil_mmu.h"
#include "xtime_l.h"
#include "sleep.h"
#include "xroad_conv3_fp32_hw.h"
#define INPUT 0x10000000U
#define PACKED 0x18000000U
#define PL_OUT 0x19000000U
#define CPU_OUT 0x1A000000U
#define RAW_WEIGHT 0x1B000000U
#define MAIL 0x1F000000U
#define CORE 0x43C30000U
void road_layer_cpu(const float *,const float *,float *,int,int,int,int,int);
enum {MAGIC,VERSION,STATE,COMMAND,SEQ,ERROR_CODE,HEART,H,W,IC,OC,STRIDE,EXPECT_INPUT,EXPECT_PACKED,ACTUAL_INPUT,ACTUAL_PACKED,HZ,OUTPUT_FLOATS,MAX_ERROR_BITS,BAD_OUTPUTS,CPU_FNV,PL_FNV,LAYOUT_PE,GUARD_OK,RETURN_CODE};
static volatile uint32_t *const m=(volatile uint32_t *)MAIL;
static XTime now(void){XTime t;XTime_GetTime(&t);return t;}
static void barrier(void){__asm__ volatile("dsb sy" ::: "memory");}
static uint32_t hash(const void *d,uint32_t n){const uint8_t *p=d;uint32_t a=2166136261U,i;for(i=0;i<n;i++)a=(a^p[i])*16777619U;return a;}
static void ticks(unsigned i,XTime t){m[i]=(uint32_t)t;m[i+1]=(uint32_t)(t>>32);}
static void wr(unsigned off,uint32_t x){Xil_Out32(CORE+off,x);}
static uint32_t rd(unsigned off){return Xil_In32(CORE+off);}
static void ptr(unsigned off,uint32_t address){wr(off,address);wr(off+4,0);}
static int pl_run(unsigned input_bytes,unsigned packed_bytes,unsigned output_bytes,XTime *whole,XTime *wait){
 XTime start=now(),a,b;uint8_t *guard=(uint8_t *)(PL_OUT+output_bytes);unsigned i;
 memset(guard,0xA5,64);Xil_DCacheFlushRange(INPUT,input_bytes);Xil_DCacheFlushRange(PACKED,packed_bytes);
 Xil_DCacheFlushRange(PL_OUT,output_bytes+64U);Xil_DCacheInvalidateRange(PL_OUT,output_bytes+64U);barrier();
 if(!(rd(XROAD_CONV3_FP32_CONTROL_ADDR_AP_CTRL)&4U))return 11;
 ptr(XROAD_CONV3_FP32_CONTROL_ADDR_INPUT_R_DATA,INPUT);ptr(XROAD_CONV3_FP32_CONTROL_ADDR_WEIGHTS_MEM_DATA,PACKED);ptr(XROAD_CONV3_FP32_CONTROL_ADDR_OUTPUT_R_DATA,PL_OUT);
 wr(XROAD_CONV3_FP32_CONTROL_ADDR_HEIGHT_DATA,m[H]);wr(XROAD_CONV3_FP32_CONTROL_ADDR_WIDTH_DATA,m[W]);wr(XROAD_CONV3_FP32_CONTROL_ADDR_IC4_DATA,m[IC]);wr(XROAD_CONV3_FP32_CONTROL_ADDR_OC4_DATA,m[OC]);wr(XROAD_CONV3_FP32_CONTROL_ADDR_STRIDE_DATA,m[STRIDE]);
 barrier();a=now();wr(XROAD_CONV3_FP32_CONTROL_ADDR_AP_CTRL,1);
 while(!(rd(XROAD_CONV3_FP32_CONTROL_ADDR_AP_CTRL)&2U)){m[HEART]++;if(now()-a>(XTime)COUNTS_PER_SECOND*5U)return 12;usleep(10);}
 b=now();m[RETURN_CODE]=rd(XROAD_CONV3_FP32_CONTROL_ADDR_AP_RETURN);if(m[RETURN_CODE])return 13;
 Xil_DCacheInvalidateRange(PL_OUT,output_bytes+64U);barrier();*whole=now()-start;*wait=b-a;
 for(i=0;i<64;i++)if(guard[i]!=0xA5)return 14;
 return 0;
}
int main(void){
 Xil_DCacheDisable();Xil_SetTlbAttributes(MAIL,NORM_NONCACHE);Xil_DCacheEnable();Xil_ICacheEnable();memset((void *)MAIL,0,4096);
 m[MAGIC]=0x52435033U;m[VERSION]=1;m[HZ]=COUNTS_PER_SECOND;m[LAYOUT_PE]=8;m[STATE]=1;barrier();
 for(;;){
  unsigned h,w,ic,oc,s,oh,ow,n,ni,nw,r,block,lane,j;float *raw=(float *)RAW_WEIGHT;const float *packed=(const float *)PACKED;int error=0;
  XTime cpu,whole,wait,a;float maximum=0;union{float f;uint32_t u;} bits;
  m[HEART]++;if(m[COMMAND]!=1){usleep(1000);continue;}
  m[COMMAND]=0;m[STATE]=2;m[ERROR_CODE]=0;m[BAD_OUTPUTS]=0;m[GUARD_OK]=0;h=m[H];w=m[W];ic=m[IC];oc=m[OC];s=m[STRIDE];
  if(h<1||h>160||w<1||w>160||ic<4||ic>128||ic%4||oc<8||oc>256||oc%8||(s!=1&&s!=2)){m[ERROR_CODE]=1;m[STATE]=4;continue;}
  oh=(h+s-1)/s;ow=(w+s-1)/s;if(oh>80||ow>80){m[ERROR_CODE]=2;m[STATE]=4;continue;}
  ni=h*w*ic*4U;nw=oc*(9U*ic+1U)*4U;n=oh*ow*oc;m[OUTPUT_FLOATS]=n;
  Xil_DCacheInvalidateRange(INPUT,ni);Xil_DCacheInvalidateRange(PACKED,nw);m[ACTUAL_INPUT]=hash((const void *)INPUT,ni);m[ACTUAL_PACKED]=hash((const void *)PACKED,nw);
  if(m[ACTUAL_INPUT]!=m[EXPECT_INPUT]||m[ACTUAL_PACKED]!=m[EXPECT_PACKED]){m[ERROR_CODE]=3;m[STATE]=4;continue;}
  for(block=0;block<oc/8;block++){
   unsigned base=block*(9U*ic+1U)*8U;
   for(lane=0;lane<8;lane++)raw[9U*ic*oc+block*8U+lane]=packed[base+lane];
   for(r=0;r<9U*ic;r++)for(lane=0;lane<8;lane++)raw[r*oc+block*8U+lane]=packed[base+(r+1U)*8U+lane];
  }
  for(j=0;j<4;j++){
   if((j&1U)==0){a=now();road_layer_cpu((const float *)INPUT,raw,(float *)CPU_OUT,(int)h,(int)w,(int)ic,(int)oc,(int)s);cpu=now()-a;error=pl_run(ni,nw,n*4U,&whole,&wait);}
   else {error=pl_run(ni,nw,n*4U,&whole,&wait);a=now();road_layer_cpu((const float *)INPUT,raw,(float *)CPU_OUT,(int)h,(int)w,(int)ic,(int)oc,(int)s);cpu=now()-a;}
   if(error)break;
   ticks(32+j*6,cpu);ticks(34+j*6,whole);ticks(36+j*6,wait);
  }
  if(error){m[ERROR_CODE]=(uint32_t)error;m[STATE]=4;barrier();continue;}
  for(j=0;j<n;j++){
   float a0=((float *)CPU_OUT)[j],b0=((float *)PL_OUT)[j],delta=fabsf(a0-b0);
   if(!isfinite(a0)||!isfinite(b0)||delta>2e-5f+2e-5f*fabsf(a0))m[BAD_OUTPUTS]++;
   if(delta>maximum)maximum=delta;
  }
  bits.f=maximum;m[MAX_ERROR_BITS]=bits.u;m[GUARD_OK]=1;m[CPU_FNV]=hash((const void *)CPU_OUT,n*4U);m[PL_FNV]=hash((const void *)PL_OUT,n*4U);
  Xil_DCacheFlushRange(CPU_OUT,n*4U);Xil_DCacheFlushRange(PL_OUT,n*4U);barrier();
  if(m[BAD_OUTPUTS]){m[ERROR_CODE]=20;m[STATE]=4;}else{m[SEQ]++;m[STATE]=3;}barrier();
 }
}
