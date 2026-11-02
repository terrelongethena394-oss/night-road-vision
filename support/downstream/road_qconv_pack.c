/* GPL-3.0. KK-IC4-OC4 signed byte weights -> OC16/kernel/IC8/PE16/SIMD8. */
#include <stddef.h>
#include <stdint.h>
int road_qconv_pack(const int8_t *src,int ic4,int oc4,int k,int8_t *dst,size_t capacity){
 int blocks,groups,b,ky,kx,g,o,lane;size_t needed,at=0;
 if(!src||!dst||ic4<4||ic4>512||oc4<16||oc4>256||(k!=1&&k!=3&&k!=6)||(ic4!=4&&ic4%8))return 1;
 blocks=(oc4+15)/16;groups=(ic4+7)/8;needed=(size_t)blocks*k*k*groups*16*8;if(capacity<needed)return 2;
 for(b=0;b<blocks;b++)for(ky=0;ky<k;ky++)for(kx=0;kx<k;kx++)for(g=0;g<groups;g++)for(o=0;o<16;o++)for(lane=0;lane<8;lane++){
  int ic=g*8+lane,oc=b*16+o;dst[at++]=(ic<ic4&&oc<oc4)?src[((ky*k+kx)*ic4+ic)*oc4+oc]:0;
 }
 return at==needed?0:3;
}
