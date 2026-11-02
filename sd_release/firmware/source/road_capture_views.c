#include "road_capture_views.h"
int road_capture_views(const uint8_t *src,uint32_t *full,uint32_t *a,uint32_t *b,uint32_t *c){
 unsigned x,y,k,t;uint32_t *tiles[3]={a,b,c};
 if(!src||!full||!a||!b||!c)return 1;
 for(y=0;y<240;y++)for(x=0;x<400;x++){
  unsigned p=(y*1600U+2U*x)*3U;uint32_t z[3];
  for(k=0;k<3;k++)z[k]=(src[p+k]+src[p+3U+k]+src[p+2400U+k]+src[p+2403U+k]+2U)/4U;
  full[y*400U+x]=z[2]|z[1]<<8|z[0]<<16;
 }
 for(t=0;t<3;t++)for(y=0;y<240;y++)for(x=0;x<400;x++){
  const uint8_t *p=src+((y+120U)*800U+x+t*200U)*3U;
  tiles[t][y*400U+x]=(uint32_t)p[2]|((uint32_t)p[1]<<8)|((uint32_t)p[0]<<16);
 }
 return 0;
}
