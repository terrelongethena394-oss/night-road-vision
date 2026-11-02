/* Detection-supervised spatial strength,or frozen rational uniform control.
 * Called afterABI29 brightfusion;its illumination plane remains at work+6*N.
 */
#include "road_retinex_c.h"
#include "road_task_gate_config.h"
#include <math.h>
#include <stdint.h>
int road_fusion_bright(const uint32_t *,uint32_t *,unsigned,float *,RoadRetinexStats *,void (*)(void *),void *);
#define TG_W 400
#define TG_H 240
#define TG_N 96000
int road_retinex_c(const uint32_t *src,uint32_t *dst,unsigned n,float *work,RoadRetinexStats *s,void (*cb)(void *),void *opaque){
 int e=road_fusion_bright(src,dst,n,work,s,cb,opaque),i,c;uint64_t total=0;float maxgain=1.f;
 if(e||s->alpha==0.f)return e;
#if ROAD_TASK_GATE_KIND==0
 for(i=0;i<TG_N;i++){
  uint32_t a=src[i],b=dst[i],out=0;unsigned im=0,om=0;
  for(c=0;c<3;c++){unsigned x=(a>>(8*c))&255U,y=(b>>(8*c))&255U,z=(x*(20U-ROAD_TASK_GATE_K)+y*ROAD_TASK_GATE_K+10U)/20U;out|=z<<(8*c);if(x>im)im=x;if(z>om)om=z;}
  dst[i]=out;total+=54U*(out&255U)+183U*((out>>8)&255U)+19U*((out>>16)&255U);if(im)maxgain=fmaxf(maxgain,(float)om/(float)im);
  if(cb&&!(i&4095))cb(opaque);
 }
 s->alpha=(float)ROAD_TASK_GATE_K/20.f;
#else
 {
  float *feat=work,*a=work+7*TG_N,*b=a+8*TG_N;
  const float *fw=road_task_gate_weights,*fb=fw+56,*dw=fb+8,*db=dw+72,*hw=db+8;float bias=hw[8];double masksum=0.;int o,y,x,dy,dx,j;
  for(i=0;i<TG_N;i++)for(c=0;c<3;c++){feat[c*TG_N+i]=(float)((src[i]>>(8*c))&255U)/255.f;feat[(c+3)*TG_N+i]=(float)((dst[i]>>(8*c))&255U)/255.f;}
  for(o=0;o<8;o++)for(y=0;y<TG_H;y++){if(cb&&!(y&15))cb(opaque);for(x=0;x<TG_W;x++){int at=y*TG_W+x;float v=fb[o];for(c=0;c<7;c++)v+=fw[o*7+c]*feat[c*TG_N+at];a[o*TG_N+at]=fmaxf(v,0.f);}}
  for(o=0;o<8;o++)for(y=0;y<TG_H;y++){if(cb&&!(y&15))cb(opaque);for(x=0;x<TG_W;x++){
   float v=db[o];for(dy=-1;dy<=1;dy++)for(dx=-1;dx<=1;dx++){int yy=y+dy,xx=x+dx;if(yy>=0&&yy<TG_H&&xx>=0&&xx<TG_W)v+=dw[o*9+(dy+1)*3+dx+1]*a[o*TG_N+yy*TG_W+xx];}b[o*TG_N+y*TG_W+x]=fmaxf(v,0.f);
  }}
  for(y=0;y<TG_H;y++){if(cb&&!(y&15))cb(opaque);for(x=0;x<TG_W;x++){
   int at=y*TG_W+x;float v=bias,mask,im=0.f,om=0.f;uint32_t out=0;
   for(j=0;j<8;j++)v+=hw[j]*b[j*TG_N+at];mask=.1f+.9f/(1.f+expf(-v));masksum+=mask;
   for(c=0;c<3;c++){float raw=feat[c*TG_N+at],bright=feat[(c+3)*TG_N+at],z=raw+mask*(bright-raw);unsigned q=(unsigned)floorf(fmaxf(0.f,fminf(1.f,z))*255.f+.5f);out|=q<<(8*c);im=fmaxf(im,raw);om=fmaxf(om,(float)q/255.f);}
   dst[at]=out;total+=54U*(out&255U)+183U*((out>>8)&255U)+19U*((out>>16)&255U);if(im>0.f)maxgain=fmaxf(maxgain,om/im);
  }}
  s->alpha=(float)(masksum/TG_N);
 }
#endif
 s->mean_out=(float)((double)total/(256.*TG_N));s->max_gain=maxgain;return 0;
}
