/* Frozen detection preprocessing control. No learned weights in this kernel.
 * Kind0:maxRGBgamma (.8/.65),cap3,highlightfade. Kind1:paper floatreference.
 */
#include "road_retinex_c.h"
#include "road_allview_config.h"
#include <math.h>
#include <string.h>
#include <stdint.h>
#define AV_W 400
#define AV_H 240
#define AV_N 96000
static float avclip(float x,float a,float b){return x<a?a:(x>b?b:x);}
#if ROAD_ALLVIEW_KIND==1
static int avmirror(int x,int n){if(x<0)return -x;if(x>=n)return 2*n-2-x;return x;}
#endif
int road_retinex_c(const uint32_t *src,uint32_t *dst,unsigned n,float *work,RoadRetinexStats *s,void (*cb)(void *),void *opaque){
 uint64_t total=0,outtotal=0;int i,c;float maxgain=1.f;
 if(!src||!dst||!work||!s||n!=AV_N||src==dst)return 1;
 for(i=0;i<AV_N;i++){uint32_t q=src[i];total+=54U*(q&255U)+183U*((q>>8)&255U)+19U*((q>>16)&255U);}
 s->mean_in=(float)((double)total/(256.*AV_N));s->mean_out=s->mean_in;s->noise_proxy=0.f;s->alpha=0.f;s->max_gain=1.f;
 if(total==0||total>48ULL*256ULL*AV_N){memcpy(dst,src,AV_N*4U);return 0;}
#if ROAD_ALLVIEW_KIND==0
 {
  float lut[256];lut[0]=1.f;
  for(i=1;i<256;i++){float v=(float)i/255.f,g=powf(v,ROAD_ALLVIEW_GAMMA)/v;g=fminf(g,3.f);lut[i]=1.f+(g-1.f)*(1.f-avclip((v-.65f)/.33f,0.f,1.f));}
  for(i=0;i<AV_N;i++){
   uint32_t a=src[i],out=0;unsigned r=a&255U,g=(a>>8)&255U,b=(a>>16)&255U,m=r>g?(r>b?r:b):(g>b?g:b);float gain=lut[m];maxgain=fmaxf(maxgain,gain);
   for(c=0;c<3;c++)out|=(uint32_t)floorf(avclip((float)((a>>(8*c))&255U)*gain,0.f,255.f)+.5f)<<(8*c);
   dst[i]=out;outtotal+=54U*(out&255U)+183U*((out>>8)&255U)+19U*((out>>16)&255U);if(cb&&!(i&4095))cb(opaque);
  }
 }
#else
 {
  float *g=work,*tmp=g+AV_N,*coarse=tmp+AV_N,*mn=coarse+AV_N,*f=mn+AV_N,lut[256];int x,y,k;
  for(i=0;i<256;i++)lut[i]=expf(-(float)i/32.f);
  for(i=0;i<AV_N;i++){uint32_t q=src[i];g[i]=fmaxf((float)(q&255U),fmaxf((float)((q>>8)&255U),(float)((q>>16)&255U)));}
  for(y=0;y<AV_H;y++){if(cb&&!(y&15))cb(opaque);for(x=0;x<AV_W;x++){float v=0.f;for(k=-5;k<=5;k++)v=fmaxf(v,g[y*AV_W+avmirror(x+k,AV_W)]);tmp[y*AV_W+x]=v;}}
  for(y=0;y<AV_H;y++){if(cb&&!(y&15))cb(opaque);for(x=0;x<AV_W;x++){float v=0.f;for(k=-5;k<=5;k++)v=fmaxf(v,tmp[avmirror(y+k,AV_H)*AV_W+x]);coarse[y*AV_W+x]=v;}}
  for(y=0;y<AV_H;y++){if(cb&&!(y&15))cb(opaque);for(x=0;x<AV_W;x++){float v=255.f;for(k=-5;k<=5;k++)v=fminf(v,coarse[avmirror(y+k,AV_H)*AV_W+x]);mn[y*AV_W+x]=v;}}
  for(y=0;y<AV_H;y++){if(cb&&!(y&15))cb(opaque);for(x=0;x<AV_W;x++){int at=y*AV_W+x;float sum=0.f,den=0.f;for(k=-5;k<=5;k++){float v=mn[y*AV_W+avmirror(x+k,AV_W)],d=v-g[at];if(d>=0.f){float w=lut[(unsigned)d];sum+=v*w;den+=w;}}f[at]=avclip(fmaxf(den>1e-10f?sum/den:g[at],g[at])/255.f,0.f,1.f);}}
  for(i=0;i<AV_N;i++){
   uint32_t a=src[i],out=0;float v=f[i],gain=v>1e-8f?sqrtf(v*(2.f-v))/v:1.f;maxgain=fmaxf(maxgain,gain);
   for(c=0;c<3;c++)out|=(uint32_t)floorf(avclip((float)((a>>(8*c))&255U)*gain,0.f,255.f)+.5f)<<(8*c);
   dst[i]=out;outtotal+=54U*(out&255U)+183U*((out>>8)&255U)+19U*((out>>16)&255U);if(cb&&!(i&4095))cb(opaque);
  }
 }
#endif
 s->mean_out=(float)((double)outtotal/(256.*AV_N));s->max_gain=maxgain;s->alpha=1.f;return 0;
}
