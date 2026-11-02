/* Bounded gamma0.65 tone curve with one RGB gain, gamma table generated offline. */
#include "road_enhance.h"
#include "road_enhance_tables.h"
#include <stddef.h>
int road_enhance(const uint32_t *raw,uint32_t *out,uint32_t pixels,unsigned mode,unsigned cap,RoadEnhanceStats *s,void (*poll)(void *),void *opaque){
 uint32_t i,sum=0,outsum=0,changed=0,maxd=0;unsigned alpha;uint16_t gain[256];
 if(!raw||!out||!s||!pixels||pixels>96000U||mode>2||cap<1||cap>32)return 1;
 for(i=0;i<pixels;i++){
  uint32_t v=raw[i];sum+=(54U*(v&255U)+183U*((v>>8)&255U)+19U*((v>>16)&255U)+128U)>>8;
  if(poll&&!(i&4095U))poll(opaque);
 }
 s->mean_in=(sum+pixels/2)/pixels;alpha=s->mean_in<=40U?256U:(s->mean_in>=80U?0U:((80U-s->mean_in)*256U+20U)/40U);
 if(mode==0)alpha=0;if(mode==2)alpha=256;
 gain[0]=4096;
 for(i=1;i<256;i++){
  unsigned d=ROAD_GAMMA_LIFT[i];if(d>cap)d=cap;if(d>i)d=i;
  d=(d*(i<192U?192U-i:0U)+96U)/192U;d=(d*alpha+128U)>>8;
  gain[i]=(uint16_t)(((i+d)*4096U+i/2U)/i);
 }
 for(i=0;i<pixels;i++){
  unsigned v=raw[i],r=v&255U,g=(v>>8)&255U,b=(v>>16)&255U,m=r>g?r:g,nr,ng,nb,d;
  if(b>m)m=b;
  nr=(r*gain[m]+2048U)>>12;ng=(g*gain[m]+2048U)>>12;nb=(b*gain[m]+2048U)>>12;
  if(nr>255U)nr=255U;if(ng>255U)ng=255U;if(nb>255U)nb=255U;
  out[i]=nr|(ng<<8)|(nb<<16);if(out[i]!=(v&0xffffffU))changed++;
  d=nr-r;if(ng-g>d)d=ng-g;if(nb-b>d)d=nb-b;if(d>maxd)maxd=d;
  outsum+=(54U*nr+183U*ng+19U*nb+128U)>>8;
  if(poll&&!(i&4095U))poll(opaque);
 }
 s->mean_out=(outsum+pixels/2)/pixels;s->alpha=alpha;s->cap=cap;s->changed=changed;s->max_delta=maxd;return 0;
}
