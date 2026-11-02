/* Paper-guided residual restoration, independently written411weight student.
 * Input/output RGB888 words,400x240, caller-owned31*Nfloat workspace.
 * No detector, filesystem, DMA or peripheral accesses in this kernel.
 */
#include "road_retinex_c.h"
#include "road_student_weights.h"
#include <math.h>
#include <string.h>
#include <stdint.h>
#define W 400
#define H 240
#define N 96000
static int mirror(int x,int n){if(x<0)return -x;if(x>=n)return 2*n-2-x;return x;}
static float clipf(float v,float lo,float hi){return v<lo?lo:(v>hi?hi:v);}
static float protect(float v){float t=clipf((v-.65f)/.33f,0.f,1.f);return 1.f-t*t*(3.f-2.f*t);}
static void ping(void (*cb)(void *),void *p,int y){if(cb&&(y&15)==0)cb(p);}
int road_student_restore(const uint32_t *src,uint32_t *dst,unsigned n,float *work,RoadRetinexStats *s,void (*cb)(void *),void *opaque){
 float *g=work,*tmp=g+N,*coarse=tmp+N,*mn=coarse+N,*f=mn+N;
 float *feat=work,*a=feat+7*N,*b=a+12*N;float lut[256];
 const float *fw=road_student_weights,*fb=fw+84,*dw=fb+12,*db=dw+108,*pw=db+12,*pb=pw+144,*hw=pb+12,*hb=hw+36;
 uint64_t total=0,outtotal=0;int x,y,i,k,c,o,j,dy,dx;float maxgain=1.f;
 if(!src||!dst||!work||!s||src==dst||n!=N)return 1;
 for(i=0;i<N;i++){uint32_t q=src[i];total+=54U*(q&255U)+183U*((q>>8)&255U)+19U*((q>>16)&255U);}
 s->mean_in=(float)((double)total/(256.0*N));s->noise_proxy=0.f;s->alpha=1.f;s->max_gain=1.f;
 if(total==0||total>48ULL*256ULL*N){memcpy(dst,src,N*4U);s->mean_out=s->mean_in;s->alpha=0.f;return 0;}
 for(i=0;i<256;i++)lut[i]=expf(-(float)i/32.f);
 for(i=0;i<N;i++){uint32_t q=src[i];unsigned r=q&255U,v=(q>>8)&255U,z=(q>>16)&255U;g[i]=(float)(r>v?(r>z?r:z):(v>z?v:z));}
 for(y=0;y<H;y++){ping(cb,opaque,y);for(x=0;x<W;x++){float v=0.f;for(k=-5;k<=5;k++)v=fmaxf(v,g[y*W+mirror(x+k,W)]);tmp[y*W+x]=v;}}
 for(y=0;y<H;y++){ping(cb,opaque,y);for(x=0;x<W;x++){float v=0.f;for(k=-5;k<=5;k++)v=fmaxf(v,tmp[mirror(y+k,H)*W+x]);coarse[y*W+x]=v;}}
 for(y=0;y<H;y++){ping(cb,opaque,y);for(x=0;x<W;x++){float v=255.f;for(k=-5;k<=5;k++)v=fminf(v,coarse[mirror(y+k,H)*W+x]);mn[y*W+x]=v;}}
 for(y=0;y<H;y++){ping(cb,opaque,y);for(x=0;x<W;x++){
  int at=y*W+x;float sum=0.f,den=0.f;
  for(k=-5;k<=5;k++){float v=mn[y*W+mirror(x+k,W)],d=v-g[at];if(d>=0.f){float wt=lut[(unsigned)d];sum+=v*wt;den+=wt;}}
  f[at]=clipf(fmaxf(den>1e-10f?sum/den:g[at],g[at])/255.f,0.f,1.f);
 }}
 /* Move illumination before feature channels3..5 overwrite old scratch. */
 memcpy(feat+6*N,f,N*sizeof(float));
 for(i=0;i<N;i++){
  uint32_t q=src[i];float r=(float)(q&255U)/255.f,v=(float)((q>>8)&255U)/255.f,z=(float)((q>>16)&255U)/255.f;
  float il=feat[6*N+i],gain=il>1e-8f?sqrtf(il*(2.f-il))/il:1.f,gate=protect(fmaxf(r,fmaxf(v,z)));
  float gainp=1.f+(gain-1.f)*gate;feat[i]=r;feat[N+i]=v;feat[2*N+i]=z;feat[3*N+i]=r*gainp;feat[4*N+i]=v*gainp;feat[5*N+i]=z*gainp;
 }
 for(o=0;o<12;o++){
  for(y=0;y<H;y++){ping(cb,opaque,y);for(x=0;x<W;x++){int at=y*W+x;float v=fb[o];for(c=0;c<7;c++)v+=fw[o*7+c]*feat[c*N+at];a[o*N+at]=fmaxf(v,0.f);}}
 }
 for(o=0;o<12;o++){
  for(y=0;y<H;y++){ping(cb,opaque,y);for(x=0;x<W;x++){
   float v=db[o];for(dy=-1;dy<=1;dy++)for(dx=-1;dx<=1;dx++){int yy=y+dy,xx=x+dx;if(yy>=0&&yy<H&&xx>=0&&xx<W)v+=dw[o*9+(dy+1)*3+dx+1]*a[o*N+yy*W+xx];}b[o*N+y*W+x]=fmaxf(v,0.f);
  }}
 }
 for(o=0;o<12;o++){
  for(y=0;y<H;y++){ping(cb,opaque,y);for(x=0;x<W;x++){int at=y*W+x;float v=pb[o];for(c=0;c<12;c++)v+=pw[o*12+c]*b[c*N+at];a[o*N+at]=fmaxf(v,0.f);}}
 }
 for(y=0;y<H;y++){ping(cb,opaque,y);for(x=0;x<W;x++){
  int at=y*W+x;uint32_t out=0;float gate=protect(fmaxf(feat[at],fmaxf(feat[N+at],feat[2*N+at]))),maxin=0.f,maxout=0.f;
  for(o=0;o<3;o++){
   float v=hb[o];for(j=0;j<12;j++)v+=hw[o*12+j]*a[j*N+at];v=clipf(feat[(o+3)*N+at]+v*gate,0.f,1.f);
   out|=(uint32_t)floorf(v*255.f+.5f)<<(8*o);maxin=fmaxf(maxin,feat[o*N+at]);maxout=fmaxf(maxout,v);
  }
  if(maxin>0.f)maxgain=fmaxf(maxgain,maxout/maxin);
  dst[at]=out;outtotal+=54U*(out&255U)+183U*((out>>8)&255U)+19U*((out>>16)&255U);
 }}
 s->mean_out=(float)((double)outtotal/(256.0*N));s->max_gain=maxgain;return 0;
}
