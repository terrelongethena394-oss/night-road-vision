#include "road_camera.h"
void road_camera_average(const uint8_t *src,uint32_t *dest){
 uint32_t x,y,k;
 for(y=0;y<240;y++)for(x=0;x<400;x++){
  uint32_t at=(y*1600U+2U*x)*3U,bgr[3];
  for(k=0;k<3;k++)bgr[k]=(src[at+k]+src[at+3+k]+src[at+2400+k]+src[at+2403+k]+2U)/4U;
  dest[y*400+x]=bgr[2]|(bgr[1]<<8)|(bgr[0]<<16);
 }
}
