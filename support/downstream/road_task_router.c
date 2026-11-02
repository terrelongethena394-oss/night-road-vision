/* 68 image statistics + tiny learned three-class enhancement controller.
 * No labels/filenames/detection results and no SD/Flash/device I/O. */
#include <stdint.h>
#include <math.h>
static unsigned lum(uint32_t p){return (54U*(p&255U)+183U*((p>>8)&255U)+19U*((p>>16)&255U)+128U)>>8;}
int road_task_router_features(const uint32_t *src,unsigned n,float *out){
 uint64_t sums[32]={0},sq[32]={0},grad=0,black=0;int64_t rg=0,bg=0;unsigned x,y,i;
 if(!src||!out||n!=96000U)return 1;
 for(y=0;y<240U;y++)for(x=0;x<400U;x++){
  unsigned at=y*400U+x,k=y/60U*8U+x/50U,v=lum(src[at]);uint32_t p=src[at];
  sums[k]+=v;sq[k]+=v*v;rg+=(int)(p&255U)-(int)((p>>8)&255U);bg+=(int)((p>>16)&255U)-(int)((p>>8)&255U);if(v<=8U)black++;
  if(x){int d=(int)v-(int)lum(src[at-1]);grad+=(unsigned)(d<0?-d:d);}
  if(y){int d=(int)v-(int)lum(src[at-400]);grad+=(unsigned)(d<0?-d:d);}
 }
 for(i=0;i<32;i++){double m=(double)sums[i]/3000.;out[i]=(float)(m/255.);out[32+i]=(float)(((double)sq[i]/3000.-m*m)/65025.);}
 out[64]=(float)((double)rg/(96000.*255.));out[65]=(float)((double)bg/(96000.*255.));out[66]=(float)((double)grad/(255.*(240.*399.+239.*400.)));out[67]=(float)((double)black/96000.);return 0;
}
int road_task_router_predict(const float *feat,const float *w,const float *mean,const float *scale,float *prob,float *score){
 float x[68],hidden[16],logit[3],maximum,total=0.f;unsigned i,j;
 if(!feat||!w||!mean||!scale||!prob||!score)return 1;
 for(i=0;i<68;i++){if(!isfinite(feat[i])||!isfinite(mean[i])||!isfinite(scale[i])||scale[i]<=0.f)return 2;x[i]=(feat[i]-mean[i])/scale[i];}
 for(i=0;i<16;i++){float sum=w[1088+i];for(j=0;j<68;j++)sum+=w[i*68+j]*x[j];hidden[i]=sum>0.f?sum:0.f;}
 for(i=0;i<3;i++){float sum=w[1152+i];for(j=0;j<16;j++)sum+=w[1104+i*16+j]*hidden[j];logit[i]=sum;}
 maximum=fmaxf(logit[0],fmaxf(logit[1],logit[2]));for(i=0;i<3;i++){prob[i]=expf(logit[i]-maximum);total+=prob[i];}
 if(!isfinite(total)||total<=0.f)return 3;
 for(i=0;i<3;i++)prob[i]/=total;
 *score=prob[2]-prob[0];return 0;
}
