/* Q10 activations, per-layer signed16 weights and signed32 biases.
 * Every signed32 accumulation prefix is bounded by the exported proof.
 * All arrays use C,H,W order; temporal input flattens the preceding H2.
 */
#ifndef PLATE_NATIVE_KERNEL_H
#define PLATE_NATIVE_KERNEL_H
#include <stdint.h>
#include <stddef.h>
#include "plate_weights.h"
static void plate_normalize(const uint8_t raw[3072],int16_t output[3072]){
 uint16_t hist[256]={0};int i,count=0,lo=-1,hi=-1,span,center,d,q,v;
 for(i=0;i<3072;i++)hist[raw[i]]++;
 for(i=0;i<256;i++){count+=hist[i];if(lo<0 && count>=154)lo=i;if(count>=2919){hi=i;break;}}
 span=hi-lo;if(span<16)span=16;center=(lo+hi+1)/2;
 for(i=0;i<3072;i++){d=(int)raw[i]-center;q=((d<0?-d:d)*192+span/2)/span;v=128+(d<0?-q:q);if(v<0)v=0;if(v>255)v=255;output[i]=(int16_t)((2*v-255)*4);}
}
static int16_t plate_activate(int32_t value,int fraction){
 int64_t a=value;int64_t v=a<0?-((-a+((int64_t)1<<(fraction-1)))>>fraction):((a+((int64_t)1<<(fraction-1)))>>fraction);
 return (int16_t)(v<0?0:(v>6144?6144:v));
}
static void plate_conv(const PlateLayer *d,const int16_t *in,int16_t *out,int32_t *scores){
 int oc,oy,ox,ic,ky,kx,sy,sx,first,ci=d->cin/d->groups,index,wi;int32_t acc;
 for(oc=0;oc<d->cout;oc++)for(oy=0;oy<d->ho;oy++)for(ox=0;ox<d->wo;ox++){
  acc=d->bias[oc];first=(oc/(d->cout/d->groups))*ci;
  for(ic=0;ic<ci;ic++)for(ky=0;ky<d->kh;ky++)for(kx=0;kx<d->kw;kx++){
   sy=oy*d->sh+ky-d->ph;sx=ox*d->sw+kx-d->pw;
   if(sy>=0 && sy<d->hi && sx>=0 && sx<d->wi){
    index=((first+ic)*d->hi+sy)*d->wi+sx;wi=((oc*ci+ic)*d->kh+ky)*d->kw+kx;
    acc+=(int32_t)in[index]*(int32_t)d->weight[wi];
   }
  }
  index=(oc*d->ho+oy)*d->wo+ox;
  if(d->activation)out[index]=plate_activate(acc,d->fraction);else scores[index]=acc;
 }
}
static void plate_infer(const uint8_t raw[3072],int32_t scores[1632]){
 static int16_t a[12288],b[12288];int i;int16_t *in=a,*out=b,*swap;
 plate_normalize(raw,in);
 for(i=0;i<PLATE_LAYER_COUNT;i++){plate_conv(&PLATE_LAYERS[i],in,out,scores);swap=in;in=out;out=swap;}
}
static int plate_decode(const int32_t scores[1632],uint8_t tokens[24]){
 int t,c,best,previous=-1,n=0;int32_t value;
 for(t=0;t<24;t++){
  best=0;value=scores[t];for(c=1;c<68;c++)if(scores[c*24+t]>value){best=c;value=scores[c*24+t];}
  if(best!=previous && best!=67){tokens[n++]=(uint8_t)best;}
  previous=best;
 }
 return n;
}
static int plate_valid(const uint8_t *tokens,int n){
 int i;if(n!=7 || tokens[0]>=31 || tokens[1]<41 || tokens[1]>64)return 0;
 for(i=2;i<7;i++)if(tokens[i]<31 || tokens[i]>64)return 0;
 return 1;
}
#endif
