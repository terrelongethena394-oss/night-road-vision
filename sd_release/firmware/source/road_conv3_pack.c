/* Shared host/ARM layout adapter, GPL-3.0. No hardware access. */
#include <stddef.h>
int road_pack_conv13(const float *weights,const float *bias,int ic4,int oc4,int pe,int kernel,float *dst,size_t capacity){
 size_t needed;int block,r,lane;
 if((kernel!=1&&kernel!=3)||!weights||!bias||!dst||(pe!=4&&pe!=8&&pe!=16)||ic4<4||ic4>(kernel==1?512:128)||ic4%4||oc4<pe||oc4>256||oc4%pe)return 1;
 needed=(size_t)oc4*(kernel*kernel*ic4+1);if(capacity<needed)return 2;
 for(block=0;block<oc4/pe;block++){
  size_t base=(size_t)block*(kernel*kernel*ic4+1)*pe;
  for(lane=0;lane<pe;lane++)dst[base+lane]=bias[block*pe+lane];
  for(r=0;r<kernel*kernel*ic4;r++)for(lane=0;lane<pe;lane++)dst[base+(r+1)*pe+lane]=weights[(size_t)r*oc4+block*pe+lane];
 }
 return 0;
}
