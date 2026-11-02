/* Shared existing PL convolution core, native-detail RAW car verification. */
#include "road_roi_verify_hw.h"
#include "road_camera.h"
#include "road_pl.h"
#include "xtime_l.h"
#include "xil_cache.h"
#include <string.h>
int road_roi_plan(const float *,int,int *,int *);
int road_roi_refine(const float *,int,int,const int *,const int *,const float *,const int *,float *);
int road_native_car_roi(const uint8_t *,int,int,uint32_t *);
static uint32_t hash(const void *a,unsigned n){const uint8_t *p=a;uint32_t v=2166136261U;unsigned i;for(i=0;i<n;i++)v=(v^p[i])*16777619U;return v;}
int road_roi_verify_live(const float *weights,const uint8_t *source,const RoadBox *base,int nb,RoadBox *out,unsigned *calls,uint64_t *net_ticks){
 volatile uint32_t *m=(volatile uint32_t *)RC_MAIL;float *base6=(float *)ROI_BASE_FLOAT,*local=(float *)ROI_LOCAL_BOXES,*final=(float *)ROI_FINAL_FLOAT;
 int *indices=(int *)ROI_PLAN_DATA,*xy=indices+8,*counts=xy+16;int k,i,j,n;XTime a,b;
 if(!weights||!source||!base||!out||!calls||!net_ticks||nb<0||nb>300)return -1;
 *calls=0;*net_ticks=0;memset((void *)ROI_PLAN_DATA,0,128U);memset(local,0,8U*300U*6U*4U);
 for(i=0;i<nb;i++){base6[i*6]=base[i].x1;base6[i*6+1]=base[i].y1;base6[i*6+2]=base[i].x2;base6[i*6+3]=base[i].y2;base6[i*6+4]=base[i].score;base6[i*6+5]=(float)base[i].cls;}
 k=road_roi_plan(base6,nb,indices,xy);if(k<0)return -2;m[209]=(unsigned)k;
 for(i=0;i<8;i++){m[220+i]=m[228+i]=m[236+i]=m[244+i]=m[252+i]=0;}
 if(k&&road_pl_prepare(weights))return -3;
 for(i=0;i<k;i++){
  uint32_t input=ROI_NATIVE_INPUT(i),decoded=ROI_NATIVE_DECODE(i);const RoadBox *p;
  if(road_native_car_roi(source,xy[i*2],xy[i*2+1],(uint32_t *)input))return -4;
  m[220+i]=hash((const void *)input,96000U*4U);m[228+i]=(unsigned)xy[i*2];m[236+i]=(unsigned)xy[i*2+1];m[252+i]=(unsigned)indices[i];Xil_DCacheFlushRange(input,96000U*4U);
  road_preprocess400((const uint32_t *)input,(uint8_t *)RC_PREP);road_input320((const uint8_t *)RC_PREP,(float *)RC_ARENA);
  road_pl_begin();XTime_GetTime(&a);if(road_forward(weights,(float *)RC_ARENA,0,0))return -5;XTime_GetTime(&b);*calls+=m[73];*net_ticks+=(uint64_t)(b-a);
  road_decode((const float *)RC_ARENA,(float *)RC_DECODE);memcpy((void *)decoded,(const void *)RC_DECODE,ROAD_CANDIDATES*9U*4U);Xil_DCacheFlushRange(decoded,ROAD_CANDIDATES*9U*4U);
  n=road_nms((const float *)RC_DECODE,(RoadBox *)RC_CANDIDATES,(RoadBox *)RC_KEEP,300,.001f,.6f);if(n<0)return -6;
  road_boxes_to400((RoadBox *)RC_KEEP,n);counts[i]=n;m[244+i]=(unsigned)n;p=(const RoadBox *)RC_KEEP;
  for(j=0;j<n;j++){float *q=local+(i*300+j)*6;q[0]=p[j].x1;q[1]=p[j].y1;q[2]=p[j].x2;q[3]=p[j].y2;q[4]=p[j].score;q[5]=(float)p[j].cls;}
 }
 n=road_roi_refine(base6,nb,k,indices,xy,local,counts,final);if(n<0)return -7;
 for(i=0;i<n;i++){const float *q=final+i*6;out[i].x1=q[0];out[i].y1=q[1];out[i].x2=q[2];out[i].y2=q[3];out[i].score=q[4];out[i].cls=(int)q[5];out[i].order=i;}
 Xil_DCacheFlushRange(ROI_BASE_FLOAT,300U*6U*4U);Xil_DCacheFlushRange(ROI_FINAL_FLOAT,300U*6U*4U);Xil_DCacheFlushRange(ROI_LOCAL_BOXES,8U*300U*6U*4U);Xil_DCacheFlushRange(ROI_PLAN_DATA,128U);return n;
}
