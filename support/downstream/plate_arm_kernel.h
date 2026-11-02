/* ARM-only scheduling optimization. Frozen scalar kernel/weights are unchanged.
 * Vector lanes cover independent pixels; each lane uses the same channel order.
 * Absolute-prefix bounds still apply to every signed32 accumulation.
 */
#ifndef PLATE_ARM_KERNEL_H
#define PLATE_ARM_KERNEL_H
#define plate_infer __attribute__((unused)) plate_infer_scalar
#include "plate_native_kernel.h"
#undef plate_infer
#if defined(__ARM_NEON)
#include <arm_neon.h>
static int16x4_t plate_relu4(int32x4_t value,int fraction){
 int32x4_t v=vrshlq_s32(value,vdupq_n_s32(-fraction));
 /* Signed rounding differs for negative ties; both values clip to zero. */
 v=vmaxq_s32(v,vdupq_n_s32(0));v=vminq_s32(v,vdupq_n_s32(6144));return vqmovn_s32(v);
}
static void plate_pointwise_neon(const PlateLayer *d,const int16_t *in,int16_t *out,int32_t *scores){
 int oc,p,ic,n=d->hi*d->wi;int32_t sum;int16_t w;int32x4_t lo,hi;int16x8_t x;
 for(oc=0;oc<d->cout;oc++){
  for(p=0;p+7<n;p+=8){
   lo=vdupq_n_s32(d->bias[oc]);hi=lo;
   for(ic=0;ic<d->cin;ic++){
    x=vld1q_s16(in+ic*n+p);w=d->weight[oc*d->cin+ic];
    lo=vmlal_n_s16(lo,vget_low_s16(x),w);hi=vmlal_n_s16(hi,vget_high_s16(x),w);
   }
   if(d->activation)vst1q_s16(out+oc*n+p,vcombine_s16(plate_relu4(lo,d->fraction),plate_relu4(hi,d->fraction)));
   else{vst1q_s32(scores+oc*n+p,lo);vst1q_s32(scores+oc*n+p+4,hi);}
  }
  for(;p<n;p++){
   sum=d->bias[oc];for(ic=0;ic<d->cin;ic++)sum+=(int32_t)in[ic*n+p]*(int32_t)d->weight[oc*d->cin+ic];
   if(d->activation)out[oc*n+p]=plate_activate(sum,d->fraction);else scores[oc*n+p]=sum;
  }
 }
}
static void plate_temporal_neon(const PlateLayer *d,const int16_t *in,int16_t *out){
 int oc,p,ic,k,sx;int32_t sum;int32x4_t acc;int16_t w;
 for(oc=0;oc<d->cout;oc++){
  for(p=1;p+3<d->wi-1;p+=4){
   acc=vdupq_n_s32(d->bias[oc]);
   for(ic=0;ic<d->cin;ic++)for(k=0;k<3;k++){
    w=d->weight[(oc*d->cin+ic)*3+k];acc=vmlal_n_s16(acc,vld1_s16(in+ic*d->wi+p+k-1),w);
   }
   vst1_s16(out+oc*d->wo+p,plate_relu4(acc,d->fraction));
  }
  for(p=0;p<d->wo;p++)if(p==0 || p>=21){
   sum=d->bias[oc];for(ic=0;ic<d->cin;ic++)for(k=0;k<3;k++){
    sx=p+k-1;if(sx>=0 && sx<d->wi)sum+=(int32_t)in[ic*d->wi+sx]*(int32_t)d->weight[(oc*d->cin+ic)*3+k];
   }
   out[oc*d->wo+p]=plate_activate(sum,d->fraction);
  }
 }
}
#endif
static void plate_infer(const uint8_t raw[3072],int32_t scores[1632]){
 static int16_t a[12288],b[12288];int i;int16_t *in=a,*out=b,*swap;const PlateLayer *d;
 plate_normalize(raw,in);
 for(i=0;i<PLATE_LAYER_COUNT;i++){
  d=&PLATE_LAYERS[i];
#if defined(__ARM_NEON)
  if(d->groups==1 && d->kh==1 && d->kw==1 && d->sh==1 && d->sw==1 && d->ph==0 && d->pw==0)
   plate_pointwise_neon(d,in,out,scores);
  else if(d->groups==1 && d->kh==1 && d->kw==3 && d->hi==1 && d->wi==24 && d->sh==1 && d->sw==1 && d->pw==1 && d->activation)
   plate_temporal_neon(d,in,out);
  else
#endif
   plate_conv(d,in,out,scores);
  swap=in;in=out;out=swap;
 }
}
#endif
