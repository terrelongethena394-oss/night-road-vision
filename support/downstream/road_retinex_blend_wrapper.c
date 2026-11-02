/* ABI20: retain raw-image texture with an explicit post-enhancement blend.
 * cap0..48 selects mix strength;48=original Retinex,24=50%,0=raw.
 * No changes to the detector or the Retinex core. */
#include "road_enhance.h"
#include "road_retinex_c.h"
#include <string.h>
#include <math.h>
#ifdef ROAD_RETINEX_HOST_WORK
static float reti_work[ROAD_RETI_WORK_FLOATS];
#define RETI_WORK reti_work
#else
#define RETI_WORK ((float *)0x19000000U)
#endif
int road_enhance(const uint32_t *raw,uint32_t *out,uint32_t pixels,unsigned mode,unsigned cap,RoadEnhanceStats *s,void (*poll)(void *),void *opaque){
 uint32_t i,sum=0,outsum=0,changed=0,maxd=0;RoadRetinexStats rs;
 if(!raw||!out||!s||pixels!=96000U||mode>2U||cap>48U)return 1;
 if(mode==0U||cap==0U){memcpy(out,raw,pixels*4U);memset(&rs,0,sizeof(rs));cap=0U;}
 else {
  if(road_retinex_c(raw,out,pixels,RETI_WORK,&rs,poll,opaque))return 2;
  if(cap<48U)for(i=0;i<pixels;i++){
   uint32_t a=raw[i],b=out[i],v=0;unsigned c;
   for(c=0;c<3;c++)v|=((((a>>(8*c))&255U)*(48U-cap)+((b>>(8*c))&255U)*cap+24U)/48U)<<(8*c);
   out[i]=v;
  }
 }
 for(i=0;i<pixels;i++){
  uint32_t a=raw[i],b=out[i];int c;
  sum+=(54U*(a&255U)+183U*((a>>8)&255U)+19U*((a>>16)&255U)+128U)>>8;
  outsum+=(54U*(b&255U)+183U*((b>>8)&255U)+19U*((b>>16)&255U)+128U)>>8;
  if((a&0xffffffU)!=b)changed++;
  for(c=0;c<3;c++){int d=(int)((b>>(c*8))&255U)-(int)((a>>(c*8))&255U);if(d>(int)maxd)maxd=(uint32_t)d;}
  if(poll&&!(i&4095U))poll(opaque);
 }
 s->mean_in=(sum+pixels/2U)/pixels;s->mean_out=(outsum+pixels/2U)/pixels;s->alpha=(uint32_t)floorf(rs.alpha*(float)cap*256.f/48.f+.5f);s->cap=cap;s->changed=changed;s->max_delta=maxd;
 return 0;
}
