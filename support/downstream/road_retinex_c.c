/* Project-written portable C port of road_retinex_project.py/project_strong.
 * Retinex illumination reference: Upadhyay/Sarawadekar,TCSII2024,
 * doi10.1109/TCSII.2024.3361561. Dark noise/color and scene protection are
 * project adaptations. Float port; no claim of author RTL reproduction.
 */
#include "road_retinex_c.h"
#include <math.h>
#include <stdlib.h>
#include <stddef.h>
#define W 400
#define H 240
#define N 96000
static int bound(int x,int n){return x<0?0:(x>=n?n-1:x);}
static int mirror(int x,int n){while(x<0||x>=n){if(x<0)x=-x;if(x>=n)x=2*n-2-x;}return x;}
static float clamp(float v,float a,float b){return v<a?a:(v>b?b:v);}
static float smooth(float a,float b,float x){float t=clamp((x-a)/(b-a),0.f,1.f);return t*t*(3.f-2.f*t);}
static int floatcmp(const void *a,const void *b){float x=*(const float *)a,y=*(const float *)b;return (x>y)-(x<y);}
static void service(void (*cb)(void *),void *p,int row){if(cb&&(row&7)==0)cb(p);}
int road_retinex_c(const uint32_t *src,uint32_t *dst,unsigned n,float *work,RoadRetinexStats *stats,void (*cb)(void *),void *opaque){
 float *y,*grad,*shadow,*by,*tmp,*fm,*base,*hor,*cs,*table;
 float mean,noise,sigma,alpha,max_gain=1.f;double total=0.;unsigned flat=0;int x,row,c,dx,dy,i,k;double spatial[25];float kernel[9];double ksum=0.;
 if(!src||!dst||!work||!stats||n!=N||src==dst)return 1;
 y=work;grad=y+N;shadow=grad+N;by=shadow+N;tmp=by+N;fm=tmp+N;base=work+8*N;hor=base+3*N;cs=hor+3*N;table=work+17*N;
 for(i=0;i<N;i++){uint32_t v=src[i];float r=(float)(v&255U),g=(float)((v>>8)&255U),b=(float)((v>>16)&255U);y[i]=(54.f*r+183.f*g+19.f*b)/256.f;total+=(double)y[i];}
 mean=(float)(total/N);alpha=clamp((110.f-mean)/70.f,0.f,1.f);
 for(row=0;row<H;row++){service(cb,opaque,row);for(x=0;x<W;x++){
  int at=row*W+x;float avg=0.f,gx=0.f,gy=0.f;
  for(dy=-1;dy<=1;dy++)for(dx=-1;dx<=1;dx++){
   float v=y[bound(row+dy,H)*W+bound(x+dx,W)];avg+=v;
   v=y[mirror(row+dy,H)*W+mirror(x+dx,W)];gx+=v*(float)(dx*(dy==0?2:1));gy+=v*(float)(dy*(dx==0?2:1));
  }
  avg/=9.f;grad[at]=fabsf(gx)+fabsf(gy);if(y[at]<80.f&&grad[at]<40.f)tmp[flat++]=fabsf(y[at]-avg);
 }}
 if(flat>100){qsort(tmp,flat,sizeof(float),floatcmp);noise=(flat&1U)?tmp[flat/2]:(tmp[flat/2-1]+tmp[flat/2])*.5f;}else noise=2.f;
 sigma=clamp(5.f+2.f*noise,7.f,16.f);
 for(i=0;i<65536;i++){float d=(float)i/256.f;table[i]=expf(-(d*d)/(2.f*sigma*sigma));}
 for(dy=-2;dy<=2;dy++)for(dx=-2;dx<=2;dx++)spatial[(dy+2)*5+dx+2]=exp(-(double)(dy*dy+dx*dx)/4.5);
 for(row=0;row<H;row++){service(cb,opaque,row);for(x=0;x<W;x++){
  int at=row*W+x;float sum[3]={0.f,0.f,0.f},den=0.f,mv=0.f;uint32_t v=src[at];
  for(c=0;c<3;c++){float a=(float)((v>>(8*c))&255U);if(a>mv)mv=a;}
  shadow[at]=(1.f-smooth(.08f,.45f,mv/255.f))*.95f;
  for(dy=-2;dy<=2;dy++)for(dx=-2;dx<=2;dx++){
   int ix=bound(row+dy,H)*W+bound(x+dx,W);float d=y[ix]-y[at];unsigned ti=(unsigned)(fabsf(d)*256.f+.5f);double wt=(double)table[ti]*spatial[(dy+2)*5+dx+2];uint32_t a=src[ix];
   den=(float)((double)den+wt);
   for(c=0;c<3;c++)sum[c]=(float)((double)sum[c]+(double)((a>>(8*c))&255U)*wt);
  }
  for(c=0;c<3;c++){float a=(float)((v>>(8*c))&255U);base[at*3+c]=a+(sum[c]/den-a)*shadow[at];}
  by[at]=(54.f*base[at*3]+183.f*base[at*3+1]+19.f*base[at*3+2])/256.f;
  for(c=0;c<3;c++)base[at*3+c]-=by[at];
 }}
 for(k=-4;k<=4;k++){double v=exp(-(double)(k*k)/8.);ksum+=v;kernel[k+4]=(float)v;}
 /* OpenCV getGaussianKernel constructs normalized coefficients in double. */
 for(k=-4;k<=4;k++)kernel[k+4]=(float)(exp(-(double)(k*k)/8.)/ksum);
 for(row=0;row<H;row++){service(cb,opaque,row);for(x=0;x<W;x++)for(c=0;c<3;c++){
  float a=0.f;for(k=-4;k<=4;k++)a+=base[(row*W+bound(x+k,W))*3+c]*kernel[k+4];hor[(row*W+x)*3+c]=a;
 }}
 for(row=0;row<H;row++){service(cb,opaque,row);for(x=0;x<W;x++)for(c=0;c<3;c++){
  float a=0.f;for(k=-4;k<=4;k++)a+=hor[(bound(row+k,H)*W+x)*3+c]*kernel[k+4];cs[(row*W+x)*3+c]=a;
 }}
 /* y/grad/shadow may now be reused: no later read needs their old values. */
 for(i=0;i<N;i++){
  float mix=shadow[i]*(1.f-smooth(30.f,100.f,grad[i]));float confidence=1.f-mix*.4f*(1.f-smooth(4.f,24.f,by[i]));float mv=0.f;
  for(c=0;c<3;c++){float a=base[i*3+c]+(cs[i*3+c]-base[i*3+c])*mix;a*=confidence;a=clamp(by[i]+a,0.f,255.f);base[i*3+c]=a;if(a>mv)mv=a;}
  y[i]=mv;
 }
 /* Separable maximum11x11, then minimum11x1; reflect101 boundaries. */
 for(row=0;row<H;row++){service(cb,opaque,row);for(x=0;x<W;x++){
  float a=0.f;for(k=-5;k<=5;k++){float v=y[row*W+mirror(x+k,W)];if(v>a)a=v;}tmp[row*W+x]=a;
 }}
 for(row=0;row<H;row++){service(cb,opaque,row);for(x=0;x<W;x++){
  float a=0.f;for(k=-5;k<=5;k++){float v=tmp[mirror(row+k,H)*W+x];if(v>a)a=v;}grad[row*W+x]=a;
 }}
 for(row=0;row<H;row++){service(cb,opaque,row);for(x=0;x<W;x++){
  float a=255.f;for(k=-5;k<=5;k++){float v=grad[mirror(row+k,H)*W+x];if(v<a)a=v;}shadow[row*W+x]=a;
 }}
 for(row=0;row<H;row++){service(cb,opaque,row);for(x=0;x<W;x++){
  int at=row*W+x;float num=0.f,den=0.f;
  for(k=-5;k<=5;k++){float v=shadow[row*W+mirror(x+k,W)],d=v-y[at],wt=d>=0.f?expf(-fabsf(d)/32.f):0.f;num+=v*wt;den+=wt;}
  {float f=den>1e-10f?num/den:y[at];if(f<y[at])f=y[at];fm[at]=clamp(f/255.f,0.f,1.f);}
 }}
 total=0.;
 for(row=0;row<H;row++){service(cb,opaque,row);for(x=0;x<W;x++){
  int at=row*W+x;float f=fm[at],modified=sqrtf(sqrtf(f*(2.f-f))),gain=f>1e-8f?modified/f:1.f;
  float cap=1.f+47.f*by[at]/(by[at]+3.f*noise+1.f);uint32_t result=0;
  if(gain>cap)gain=cap;gain=1.f+(gain-1.f)*alpha*(1.f-smooth(.65f,.98f,y[at]/255.f));if(gain>max_gain)max_gain=gain;
  for(c=0;c<3;c++){float a=floorf(clamp(base[at*3+c]*gain,0.f,255.f)+.5f);result|=(uint32_t)a<<(8*c);}
  dst[at]=result;total+=(double)((54U*(result&255U)+183U*((result>>8)&255U)+19U*((result>>16)&255U)+128U)>>8);
 }}
 stats->mean_in=mean;stats->mean_out=(float)(total/N);stats->noise_proxy=noise;stats->alpha=alpha;stats->max_gain=max_gain;
 return 0;
}
