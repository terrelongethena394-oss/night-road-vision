#include <stdint.h>
/* Return1 only for global unenhanced meanY<=48, no frame modification. */
int road_brightness_route(const uint32_t *rgb,unsigned pixels){
 uint64_t sum=0;unsigned i;
 if(!rgb||pixels!=96000U)return -1;
 for(i=0;i<pixels;i++){uint32_t p=rgb[i];sum+=54U*(p&255U)+183U*((p>>8)&255U)+19U*((p>>16)&255U);}
 return sum<=(uint64_t)48U*256U*pixels;
}
