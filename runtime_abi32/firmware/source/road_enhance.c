/* ABI19 adapter for the existing application enhancement interface.
 * Dedicated CPU-only DDR workspace; no SD/Flash or PL accesses here. */
#include "road_enhance.h"
#include "road_retinex_c.h"
#include <string.h>
#include <math.h>
#define RETINEX_WORK_ADDRESS 0x19000000U
int road_enhance(const uint32_t *raw,uint32_t *out,uint32_t pixels,unsigned mode,unsigned cap,RoadEnhanceStats *s,void (*poll)(void *),void *opaque){
 uint32_t i,sum=0,outsum=0,changed=0,maxd=0;RoadRetinexStats rs;(void)cap;
 if(!raw||!out||!s||pixels!=96000U||mode>2U)return 1;
 if(mode==0U){memcpy(out,raw,pixels*4U);memset(&rs,0,sizeof(rs));}
 else if(road_retinex_c(raw,out,pixels,(float *)RETINEX_WORK_ADDRESS,&rs,poll,opaque))return 2;
 for(i=0;i<pixels;i++){
  uint32_t a=raw[i],b=out[i];int c;
  sum+=(54U*(a&255U)+183U*((a>>8)&255U)+19U*((a>>16)&255U)+128U)>>8;
  outsum+=(54U*(b&255U)+183U*((b>>8)&255U)+19U*((b>>16)&255U)+128U)>>8;
  if((a&0xffffffU)!=b)changed++;
  for(c=0;c<3;c++){int delta=(int)((b>>(c*8))&255U)-(int)((a>>(c*8))&255U);if(delta>(int)maxd)maxd=(uint32_t)delta;}
  if(poll&&!(i&4095U))poll(opaque);
 }
 s->mean_in=(sum+pixels/2U)/pixels;s->mean_out=(outsum+pixels/2U)/pixels;
 s->alpha=mode==0U?0U:(uint32_t)floorf(rs.alpha*256.f+.5f);s->cap=0U;s->changed=changed;s->max_delta=maxd;
 return 0;
}
