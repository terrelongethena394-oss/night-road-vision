/* One model, four unchanged raw input views; called twice on one frozen frame. */
#include "road_car_pair_model.h"
#include "road_car_pair_post.h"
#include "road_pl.h"
#include "road_camera.h"
#include "xtime_l.h"
#include "xil_cache.h"
#include <string.h>
#define OLD_DECODE 0x1B800000U
#define TILE_INPUT(i) (0x1A000000U+(i)*0x60000U)
#define TILE_DECODE(i) (0x1A120000U+(i)*0x40000U)
static RoadBox full[300],tiles[900];
int road_car_pair_model(const float *weights,unsigned which,RoadBox *cars,unsigned *calls,uint64_t *net_ticks){
 volatile uint32_t *m=(volatile uint32_t *)RC_MAIL;int v,n,nf=0,counts[3]={0,0,0};XTime a,b;
 if(which>1U||!weights||!cars||!calls||!net_ticks)return -1;
 *calls=0;*net_ticks=0;
 if(road_pl_prepare(weights))return -2;
 for(v=0;v<4;v++){
  uint32_t source=v?TILE_INPUT(v-1):RC_INPUT;
  uint32_t dest=which?(v?TILE_DECODE(v-1):RC_FULL_DECODE):(OLD_DECODE+(unsigned)v*0x40000U);
  road_preprocess400((const uint32_t *)source,(uint8_t *)RC_PREP);road_input320((const uint8_t *)RC_PREP,(float *)RC_ARENA);
  road_pl_begin();XTime_GetTime(&a);if(road_forward(weights,(float *)RC_ARENA,0,0))return -3;XTime_GetTime(&b);
  *net_ticks+=(uint64_t)(b-a);*calls+=m[73];
  road_decode((const float *)RC_ARENA,(float *)RC_DECODE);memcpy((void *)dest,(const void *)RC_DECODE,ROAD_CANDIDATES*9U*4U);Xil_DCacheFlushRange(dest,ROAD_CANDIDATES*9U*4U);
  n=road_nms((const float *)RC_DECODE,(RoadBox *)RC_CANDIDATES,(RoadBox *)RC_KEEP,300,.001f,.6f);if(n<0)return -4;
  road_boxes_to400((RoadBox *)RC_KEEP,n);
  if(!v){
   nf=n;memcpy(full,(const void *)RC_KEEP,(unsigned)n*sizeof(RoadBox));
   if(which){m[100]=(unsigned)n;memcpy((void *)RC_FULL_BOX,full,(unsigned)n*sizeof(RoadBox));memcpy((void *)RC_FULL_PREP,(const void *)RC_PREP,320U*320U*3U);}
  }else{counts[v-1]=n;memcpy(tiles+(v-1)*300,(const void *)RC_KEEP,(unsigned)n*sizeof(RoadBox));if(which)m[138+v]=(unsigned)n;}
 }
 m[103]=m[73];
 return road_car_multiview(full,nf,tiles,counts,cars,300);
}
