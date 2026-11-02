#include "road_shadowlift.h"
#include <math.h>
#define W 400
#define H 240
#define N 96000
static float clip(float x,float a,float b){return x<a?a:(x>b?b:x);}
static float smooth(float a,float b,float x){float t=clip((x-a)/(b-a),0.f,1.f);return t*t*(3.f-2.f*t);}
static int mir(int x,int n){while(x<0||x>=n){if(x<0)x=-x;if(x>=n)x=2*n-2-x;}return x;}
static void poll(void (*cb)(void *),void *p,int y){if(cb&&(y&15)==0)cb(p);}
int road_shadowlift(const uint32_t *raw,uint32_t *dst,unsigned n,float *work,RoadShadowStats *s,void (*cb)(void *),void *opaque){
 float *y=work,*weight=y+N,*limit=weight+N,*lum=limit+N,*co=lum+N,*cg=co+N,*guide=cg+N,*cap=guide+N;
 double total=0.;float lo=0.f,hi=5.f,strength,spatial[25],max_gain=1.f;int i,j,k,xx,yy,dx,dy,c;
 if(!raw||!dst||!work||!s||raw==dst||n!=N)return 1;
 for(i=0;i<N;i++){
  uint32_t a=raw[i],b=dst[i];float rr=(float)(a&255U),rg=(float)((a>>8)&255U),rb=(float)((a>>16)&255U),r=(float)(b&255U),g=(float)((b>>8)&255U),bl=(float)((b>>16)&255U);float v=fmaxf(r,fmaxf(g,bl)),rv=fmaxf(rr,fmaxf(rg,rb)),value=v/255.f;
  y[i]=(54.f*r+183.f*g+19.f*bl)/256.f;guide[i]=(54.f*rr+183.f*rg+19.f*rb)/256.f;total+=(double)y[i];
  weight[i]=(1.f-smooth(.25f,.90f,value))*sqrtf(1.f-value)*(guide[i]/(guide[i]+4.f));limit[i]=v>0.f?fmaxf(1.f,fminf(254.f/v,10.f*rv/v)):1.f;cap[i]=fmaxf(v,fminf(254.f,10.f*rv));
 }
 if(total/N>=62.){s->strength=0.f;s->mean_out=(float)(total/N);s->max_total_gain=1.f;return 0;}
 for(k=0;k<16;k++){
  float mid=(lo+hi)*.5f;double mean=0.;
  for(i=0;i<N;i++){float g=fminf(1.f+mid*weight[i],limit[i]);mean+=(double)(y[i]*g);}
  if(mean/N<62.)lo=mid;else hi=mid;
  if(cb)cb(opaque);
 }
 strength=(lo+hi)*.5f;
 for(i=0;i<N;i++){
  uint32_t a=dst[i],value=0;float g=fminf(1.f+strength*weight[i],limit[i]),rgb[3];
  for(c=0;c<3;c++){rgb[c]=floorf(clip((float)((a>>(8*c))&255U)*g,0.f,255.f)+.5f);value|=(uint32_t)rgb[c]<<(8*c);}
  dst[i]=value;lum[i]=(rgb[0]+2.f*rgb[1]+rgb[2])*.25f;co[i]=(rgb[0]-rgb[2])*.5f;cg[i]=(-rgb[0]+2.f*rgb[1]-rgb[2])*.25f;
 }
 k=0;for(dy=-2;dy<=2;dy++)for(dx=-2;dx<=2;dx++)spatial[k++]=expf(-(float)(dx*dx+dy*dy)/3.f);
 total=0.;
 for(yy=0;yy<H;yy++){poll(cb,opaque,yy);for(xx=0;xx<W;xx++){
  float nc=0.f,ng=0.f,den=0.f,v,mix,a,b,d[3],factor=1.f;uint32_t value=0,old=dst[yy*W+xx];i=yy*W+xx;k=0;
  for(dy=-2;dy<=2;dy++)for(dx=-2;dx<=2;dx++){float delta,wt;j=mir(yy+dy,H)*W+mir(xx+dx,W);delta=guide[j]-guide[i];wt=expf(-(delta*delta)/128.f)*spatial[k++];nc+=co[j]*wt;ng+=cg[j]*wt;den+=wt;}
  v=fmaxf((float)(old&255U),fmaxf((float)((old>>8)&255U),(float)((old>>16)&255U)));mix=.85f*(1.f-smooth(30.f,120.f,guide[i]))*(1.f-smooth(180.f,240.f,v));a=co[i]+(nc/den-co[i])*mix;b=cg[i]+(ng/den-cg[i])*mix;d[0]=a-b;d[1]=b;d[2]=-a-b;
  for(c=0;c<3;c++){if(d[c]>0.f)factor=fminf(factor,(cap[i]-lum[i])/d[c]);if(d[c]<0.f)factor=fminf(factor,lum[i]/(-d[c]));}factor=clip(factor,0.f,1.f);
  for(c=0;c<3;c++){value|=(uint32_t)floorf(clip(lum[i]+d[c]*factor,0.f,255.f)+.5f)<<(8*c);}
  dst[i]=value;
  total+=(double)(54U*(value&255U)+183U*((value>>8)&255U)+19U*((value>>16)&255U))/256.;
  {uint32_t z=raw[i];float rv=fmaxf((float)(z&255U),fmaxf((float)((z>>8)&255U),(float)((z>>16)&255U))),ov=fmaxf((float)(value&255U),fmaxf((float)((value>>8)&255U),(float)((value>>16)&255U)));if(rv>0.f)max_gain=fmaxf(max_gain,ov/rv);}
 }}
 s->strength=strength;s->mean_out=(float)(total/N);s->max_total_gain=max_gain;return 0;
}
