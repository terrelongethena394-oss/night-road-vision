/* Three frozen-source zooms plus a small ARM box refiner. No SD/Flash I/O. */
#include "road_balanced_extra.h"
#include "road_balanced_config.h"
#include "road_box_refiner.h"
#include "road_pl.h"
#include "road_camera.h"
#include "xtime_l.h"
#include "xil_cache.h"
#include <math.h>
#include <string.h>
int road_zoom_pixels(const uint8_t *,int,int,uint32_t *);
int road_car_refined_zoom(const RoadBox *,int,const RoadBox *,const int *,float,const float *,float,float,float,RoadBox *,int);
static RoadBox tiles[900];
static uint8_t patch_rgb[3072];
static float metadata[6];
static float lo(float a,float b){return a<b?a:b;}
static float hi(float a,float b){return a>b?a:b;}
static float area(const RoadBox *a){return hi(0.f,a->x2-a->x1)*hi(0.f,a->y2-a->y1);}
static int duplicate(const RoadBox *a,const RoadBox *base,int n){
 int i;float aa=area(a);
 for(i=0;i<n;i++)if(base[i].score>=.25f){
  float v=hi(0.f,lo(a->x2,base[i].x2)-hi(a->x1,base[i].x1))*hi(0.f,lo(a->y2,base[i].y2)-hi(a->y1,base[i].y1));
  float ba=area(base+i);if(v/(aa+ba-v+1e-9f)>=.3f||v/(lo(aa,ba)+1e-9f)>=.8f)return 1;
 }
 return 0;
}
static uint32_t hash(const void *a,unsigned n){const uint8_t *p=a;unsigned i;uint32_t v=2166136261U;for(i=0;i<n;i++)v=(v^p[i])*16777619U;return v;}
int road_balanced_extra(const float *weights,const uint8_t *source,const RoadBox *base,int nb,RoadBox *out,unsigned *calls,uint64_t *net_ticks){
 volatile uint32_t *m=(volatile uint32_t *)RC_MAIL;float *prediction=(float *)BAL_REFINER_PRED;
 int v,i,n,kept,counts[3]={0,0,0};XTime a,b;unsigned active=0;
 if(!weights||!source||!base||!out||!calls||!net_ticks||nb<0||nb>300)return -1;
 *calls=0;*net_ticks=0;memset(prediction,0,900U*5U*4U);
 for(v=0;v<3;v++){
  uint32_t input=BAL_ZOOM_INPUT(v),decoded=BAL_ZOOM_DECODE(v);
  if(road_zoom_pixels(source,v*260,BAL_ZOOM_Y,(uint32_t *)input))return -2;
  m[180+v]=hash((const void *)input,96000U*4U);Xil_DCacheFlushRange(input,96000U*4U);
  road_preprocess400((const uint32_t *)input,(uint8_t *)RC_PREP);road_input320((const uint8_t *)RC_PREP,(float *)RC_ARENA);
  road_pl_begin();XTime_GetTime(&a);if(road_forward(weights,(float *)RC_ARENA,0,0))return -3;XTime_GetTime(&b);
  *calls+=m[73];*net_ticks+=(uint64_t)(b-a);
  road_decode((const float *)RC_ARENA,(float *)RC_DECODE);memcpy((void *)decoded,(const void *)RC_DECODE,ROAD_CANDIDATES*9U*4U);Xil_DCacheFlushRange(decoded,ROAD_CANDIDATES*9U*4U);
  n=road_nms((const float *)RC_DECODE,(RoadBox *)RC_CANDIDATES,(RoadBox *)RC_KEEP,300,.001f,.6f);if(n<0)return -4;
  road_boxes_to400((RoadBox *)RC_KEEP,n);counts[v]=n;m[183+v]=(unsigned)n;memcpy(tiles+v*300,(const void *)RC_KEEP,(unsigned)n*sizeof(RoadBox));
 }
 for(v=0;v<3;v++)for(i=0;i<counts[v];i++){
  RoadBox p=tiles[v*300+i];float *d=prediction+(v*300+i)*5;
  if(p.cls!=1||p.score<.05f||!(p.x1>1.f&&p.y1>1.f&&p.x2<399.f&&p.y2<239.f))continue;
  p.x1=p.x1*.35f+(float)v*130.f;p.x2=p.x2*.35f+(float)v*130.f;p.y1=p.y1*.35f+(float)BAL_ZOOM_Y*.5f;p.y2=p.y2*.35f+(float)BAL_ZOOM_Y*.5f;
  if(duplicate(&p,base,nb))continue;
  {float box[6]={p.x1,p.y1,p.x2,p.y2,p.score,1.f};if(road_patch_features(source,box,patch_rgb,metadata))return -5;}
  if(road_box_refiner((const float *)BAL_REFINER_WEIGHT,patch_rgb,metadata,(float *)BAL_REFINER_WORK,d))return -6;
  active++;
 }
 n=road_car_refined_zoom(base,nb,tiles,counts,.65f,prediction,BAL_STRENGTH,BAL_CAP,BAL_CLASS_GATE,out,300);if(n<0)return -7;
 kept=0;for(i=0;i<n;i++)if(out[i].score>=.25f)out[kept++]=out[i];
 m[190]=3;m[194]=active;Xil_DCacheFlushRange(BAL_REFINER_PRED,900U*5U*4U);return kept;
}
