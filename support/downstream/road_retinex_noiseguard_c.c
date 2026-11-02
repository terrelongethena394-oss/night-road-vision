/* ABI22 guard_light: tone .40, gain <=4.5, smooth rational black
 * protection, patch h10, chroma mix .60, luminance mix at most .30.
 * Classical Retinex / patch filtering, with no enhancement NN weights.
 */
#include "road_retinex_c.h"
#include <math.h>
#include <stddef.h>
#define W 400
#define H 240
#define N 96000
static int mir(int x,int n){while(x<0||x>=n){if(x<0)x=-x;if(x>=n)x=2*n-2-x;}return x;}
static float clip(float x,float a,float b){return x<a?a:(x>b?b:x);}
static float smooth(float a,float b,float x){float t=clip((x-a)/(b-a),0.f,1.f);return t*t*(3.f-2.f*t);}
static void poll(void (*cb)(void *),void *p,int y){if(cb&&(y&15)==0)cb(p);}
int road_retinex_c(const uint32_t *src,uint32_t *dst,unsigned n,float *work,RoadRetinexStats *s,void (*cb)(void *),void *opaque){
 float *g=work,*tmp=g+N,*coarse=tmp+N,*mn=coarse+N,*f=mn+N,*gain=f+N,*yy=gain+N,*co=yy+N,*cg=co+N,*den=cg+N,*nc=den+N,*ng=nc+N,*ny=ng+N;
 double total=0.;float alpha,max_gain=1.f;int y,x,k,i,dx,dy,c;
 if(!src||!dst||!work||!s||src==dst||n!=N)return 1;
 for(i=0;i<N;i++){
  uint32_t a=src[i];float r=(float)(a&255U),v=(float)((a>>8)&255U),b=(float)((a>>16)&255U);g[i]=fmaxf(r,fmaxf(v,b));total+=(54.f*r+183.f*v+19.f*b)/256.f;
 }
 s->mean_in=(float)(total/N);alpha=clip((110.f-s->mean_in)/70.f,0.f,1.f);
 for(y=0;y<H;y++){poll(cb,opaque,y);for(x=0;x<W;x++){float v=0.f;for(k=-5;k<=5;k++)v=fmaxf(v,g[y*W+mir(x+k,W)]);tmp[y*W+x]=v;}}
 for(y=0;y<H;y++){poll(cb,opaque,y);for(x=0;x<W;x++){float v=0.f;for(k=-5;k<=5;k++)v=fmaxf(v,tmp[mir(y+k,H)*W+x]);coarse[y*W+x]=v;}}
 for(y=0;y<H;y++){poll(cb,opaque,y);for(x=0;x<W;x++){float v=255.f;for(k=-5;k<=5;k++)v=fminf(v,coarse[mir(y+k,H)*W+x]);mn[y*W+x]=v;}}
 for(y=0;y<H;y++){poll(cb,opaque,y);for(x=0;x<W;x++){
  int at=y*W+x;float num=0.f,dn=0.f;
  for(k=-5;k<=5;k++){float v=mn[y*W+mir(x+k,W)],d=v-g[at],wt=d>=0.f?expf(-fabsf(d)/32.f):0.f;num+=v*wt;dn+=wt;}
  f[at]=clip(fmaxf(dn>1e-10f?num/dn:g[at],g[at])/255.f,0.f,1.f);
 }}
 for(y=0;y<H;y++){poll(cb,opaque,y);for(x=0;x<W;x++){
  int at=y*W+x;uint32_t a=src[at];float il=f[at],modified=powf(il*(2.f-il),.40f),gg=il>1e-8f?modified/il:1.f;float rgb[3];
  float raw_y=(54.f*(float)(a&255U)+183.f*(float)((a>>8)&255U)+19.f*(float)((a>>16)&255U))/256.f;
  float confidence=raw_y/(raw_y+4.f);
  gg=fminf(gg,4.5f);gg=1.f+(gg-1.f)*alpha*confidence*(1.f-smooth(.65f,.98f,g[at]/255.f));gain[at]=gg;if(gg>max_gain)max_gain=gg;
  for(c=0;c<3;c++)rgb[c]=clip((float)((a>>(8*c))&255U)*gg,0.f,255.f);
  yy[at]=(rgb[0]+2.f*rgb[1]+rgb[2])*.25f;co[at]=(rgb[0]-rgb[2])*.5f;cg[at]=(-rgb[0]+2.f*rgb[1]-rgb[2])*.25f;den[at]=nc[at]=ng[at]=ny[at]=0.f;
 }}
 for(dy=-3;dy<=3;dy++)for(dx=-3;dx<=3;dx++){
  for(y=0;y<H;y++){poll(cb,opaque,y);for(x=0;x<W;x++){
   int at=y*W+x,j=mir(y+dy,H)*W+mir(x+dx,W);float a=yy[j]-yy[at],b=co[j]-co[at],v=cg[j]-cg[at];tmp[at]=(a*a*.25f+b*b+v*v)/2.25f;
  }}
  for(y=0;y<H;y++)for(x=0;x<W;x++)coarse[y*W+x]=tmp[y*W+mir(x-1,W)]+tmp[y*W+x]+tmp[y*W+mir(x+1,W)];
  for(y=0;y<H;y++){poll(cb,opaque,y);for(x=0;x<W;x++){
   int at=y*W+x,j=mir(y+dy,H)*W+mir(x+dx,W);float d=(coarse[mir(y-1,H)*W+x]+coarse[y*W+x]+coarse[mir(y+1,H)*W+x])/9.f;
   float wt=expf(-fmaxf(d-18.f,0.f)/100.f);nc[at]+=co[j]*wt;ng[at]+=cg[j]*wt;ny[at]+=yy[j]*wt;den[at]+=wt;
  }}
 }
 total=0.;
 for(y=0;y<H;y++){poll(cb,opaque,y);for(x=0;x<W;x++){
  int at=y*W+x;float dark=1.f-smooth(.10f,.65f,g[at]/255.f),mix=.6f*dark;
  float lum=yy[at]+(ny[at]/den[at]-yy[at])*(.3f*dark);
  float a=co[at]+(nc[at]/den[at]-co[at])*mix,b=cg[at]+(ng[at]/den[at]-cg[at])*mix;
  float rgb[3]={lum+a-b,lum+b,lum-a-b};uint32_t value=0;
  for(c=0;c<3;c++)value|=(uint32_t)floorf(clip(rgb[c],0.f,255.f)+.5f)<<(8*c);dst[at]=value;
  total+=(double)((54U*(value&255U)+183U*((value>>8)&255U)+19U*((value>>16)&255U)+128U)>>8);
 }}
 s->mean_out=(float)(total/N);s->alpha=alpha;s->max_gain=max_gain;s->noise_proxy=0.f;return 0;
}
