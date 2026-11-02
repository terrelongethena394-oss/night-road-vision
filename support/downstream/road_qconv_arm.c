/* GPL-3.0. Model-independent integer engine adapter; no SD/Flash calls. */
#include "road_qconv_arm.h"
#include "road_q8_tables.h"
#include "road_qconv_layout.h"
#include <stdint.h>
#include <stddef.h>
#include <string.h>
int road_qconv_pack(const int8_t *,int,int,int,int8_t *,size_t);
#ifdef QCONV_EMULATE
static int8_t packed_data[QCONV_PACKED_BYTES];static int32_t meta_data[QCONV_METADATA_BYTES/4],head_data[65536*4];
static int8_t *const packed=packed_data;static int32_t *const metadata=meta_data,*const rawhead=head_data;
unsigned qhw_host_calls;
const void *qhw_host_weights(void){return packed;}const void *qhw_host_metadata(void){return metadata;}
#else
#include "xil_cache.h"
#include "xil_io.h"
#include "xtime_l.h"
#include "sleep.h"
#include "xroad_qconv_hw.h"
#define CORE 0x43C30000U
static int8_t *const packed=(int8_t *)0x18000000U;
static int32_t *const metadata=(int32_t *)0x18800000U,*const rawhead=(int32_t *)0x19000000U;
static volatile uint32_t *const m=(volatile uint32_t *)(0x13800000U+72U*4U);
static void barrier(void){__asm__ volatile("dsb sy" ::: "memory");}
static XTime now(void){XTime t;XTime_GetTime(&t);return t;}
static unsigned rd(unsigned a){return Xil_In32(CORE+a);}static void wr(unsigned a,unsigned v){Xil_Out32(CORE+a,v);}
static void ptr(unsigned a,const void *p){wr(a,(unsigned)p);wr(a+4,0);}
#endif
static int ready;
int qhw_prepare(const unsigned char *model){
 unsigned id,c;memset(packed,0,QCONV_PACKED_BYTES);
 for(id=1;id<ROAD_TENSORS;id++)if(QCONV_LAYOUT[id].bytes){
  const RoadOp *op=ROAD_OPS+id-1;const RoadTensor *in=ROAD_T+op->in[0],*out=ROAD_T+id;
  if(road_qconv_pack((const int8_t *)(model+Q_NODES[id].wo),in->c4,out->c4,op->k,packed+QCONV_LAYOUT[id].offset,QCONV_LAYOUT[id].bytes))return 1;
 }
 for(c=0;c<QCONV_METADATA_BYTES/32;c++){
  const QChannel *ch=Q_CHANNELS+c;int32_t *d=metadata+8*c;
  d[0]=ch->split;d[1]=ch->lb;d[2]=ch->ln;d[3]=ch->lo;d[4]=ch->rb;d[5]=ch->rn;d[6]=ch->ro;d[7]=0;
 }
#ifndef QCONV_EMULATE
 Xil_DCacheFlushRange((INTPTR)packed,QCONV_PACKED_BYTES);Xil_DCacheFlushRange((INTPTR)metadata,QCONV_METADATA_BYTES);Xil_DCacheFlushRange((INTPTR)(model+Q_THRESH_BASE),QCONV_TABLE_COUNT*4U);barrier();m[5]=0x5138504BU;
#endif
 ready=1;return 0;
}
void qhw_begin(void){
#ifdef QCONV_EMULATE
 qhw_host_calls=0;
#else
 m[1]=0;m[2]=0;m[3]=0;m[4]=0;
#endif
}
#ifdef QCONV_EMULATE
static int count_upper(const int32_t *table,int n,int key){int a=0,b=n;while(a<b){int mid=a+(b-a)/2;if(table[mid]<=key)a=mid+1;else b=mid;}return a;}
#endif
int qhw_try(int id,const RoadOp *op,const RoadTensor *in,const RoadTensor *out,const unsigned char *input,const unsigned char *model,unsigned char *output,void (*poll)(void)){
 const QNode *n=Q_NODES+id;const int8_t *w=packed+QCONV_LAYOUT[id].offset;unsigned pixels=(unsigned)out->h*out->w;
#ifndef QCONV_EMULATE
 if(m[0]==0)return 0;
#endif
 if(!ready||!QCONV_LAYOUT[id].bytes)return -1;
#ifdef QCONV_EMULATE
 {
  int y,x,o,ky,kx,c,groups=(in->c4+7)/8,red=op->k*op->k*groups;const int32_t *table=(const int32_t *)(model+Q_THRESH_BASE);
  for(y=0;y<out->h;y++)for(x=0;x<out->w;x++)for(o=0;o<(n->head?32:out->c4);o++){
   int32_t acc=0;
   for(ky=0;ky<op->k;ky++)for(kx=0;kx<op->k;kx++){
    int iy=y*op->s+ky-op->p,ix=x*op->s+kx-op->p;if(iy<0||iy>=in->h||ix<0||ix>=in->w)continue;
    for(c=0;c<in->c4;c++){
     int r=(ky*op->k+kx)*groups+c/8,at=(iy*in->w+ix)*in->c4+c;
     int a=op->in[0]==0?input[at]:((const int8_t *)input)[at];int atw=((o/16*red+r)*16+(o%16))*8+c%8;
     acc+=a*w[atw];
    }
   }
   if(n->head)rawhead[(y*out->w+x)*32+o]=acc;
   else {const int32_t *ch=metadata+8*(n->ch+o);int value=acc<=ch[0]?ch[1]+count_upper(table+ch[3],ch[2],-acc):ch[4]+count_upper(table+ch[6],ch[5],acc);((int8_t *)output)[(y*out->w+x)*out->c4+o]=(int8_t)value;}
  }
  qhw_host_calls++;
 }
#else
 {
  unsigned ni=(unsigned)in->h*in->w*in->c4,no=pixels*(n->head?128U:(unsigned)out->c4);void *dest=n->head?(void *)rawhead:(void *)output;
  XTime start=now(),last,t;uint64_t total;
  Xil_DCacheFlushRange((INTPTR)input,ni);Xil_DCacheFlushRange((INTPTR)dest,no);Xil_DCacheInvalidateRange((INTPTR)dest,no);barrier();
  if(!(rd(XROAD_QCONV_CONTROL_ADDR_AP_CTRL)&4U)){m[2]=11;return -11;}
  ptr(XROAD_QCONV_CONTROL_ADDR_INPUT_R_DATA,input);ptr(XROAD_QCONV_CONTROL_ADDR_WEIGHTS_DATA,w);ptr(XROAD_QCONV_CONTROL_ADDR_METADATA_DATA,metadata+8*n->ch);ptr(XROAD_QCONV_CONTROL_ADDR_TABLES_DATA,model+Q_THRESH_BASE);ptr(XROAD_QCONV_CONTROL_ADDR_OUTPUT_R_DATA,dest);
  wr(XROAD_QCONV_CONTROL_ADDR_HEIGHT_DATA,(unsigned)in->h);wr(XROAD_QCONV_CONTROL_ADDR_WIDTH_DATA,(unsigned)in->w);wr(XROAD_QCONV_CONTROL_ADDR_IC4_DATA,(unsigned)in->c4);wr(XROAD_QCONV_CONTROL_ADDR_OC4_DATA,(unsigned)out->c4);wr(XROAD_QCONV_CONTROL_ADDR_KERNEL_DATA,(unsigned)op->k);wr(XROAD_QCONV_CONTROL_ADDR_STRIDE_DATA,(unsigned)op->s);wr(XROAD_QCONV_CONTROL_ADDR_UNSIGNED_INPUT_DATA,op->in[0]==0);wr(XROAD_QCONV_CONTROL_ADDR_HEAD_DATA,(unsigned)n->head);wr(XROAD_QCONV_CONTROL_ADDR_TABLE_COUNT_DATA,QCONV_TABLE_COUNT);
  barrier();last=now();wr(XROAD_QCONV_CONTROL_ADDR_AP_CTRL,1);
  while(!(rd(XROAD_QCONV_CONTROL_ADDR_AP_CTRL)&2U)){
   t=now();if(t-start>(XTime)COUNTS_PER_SECOND*5U){m[2]=12;return -12;}
   if(t-last>COUNTS_PER_SECOND/1000U){if(poll)poll();last=now();}usleep(10);
  }
  if(rd(XROAD_QCONV_CONTROL_ADDR_AP_RETURN)){m[2]=13;return -13;}
  Xil_DCacheInvalidateRange((INTPTR)dest,no);barrier();total=m[3]|((uint64_t)m[4]<<32);total+=now()-start;m[3]=(unsigned)total;m[4]=(unsigned)(total>>32);m[1]++;
 }
#endif
 if(n->head){
  const float *f=(const float *)(model+Q_FLOAT_BASE);unsigned p,c;
  for(p=0;p<pixels;p++)for(c=0;c<(unsigned)out->c4;c++){float v=(float)rawhead[p*32+c]*f[n->ws+c];((float *)output)[p*out->c4+c]=v+f[n->bo+c];}
 }
 if(poll){poll();}
 return 1;
}
