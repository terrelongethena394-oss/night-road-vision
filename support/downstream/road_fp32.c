/* Inference semantics adapted from Ultralytics YOLOv5 v7.0, GPL-3.0.
 * CPU FP32. ARMv7 NEON and host SSE2 use the same four-output-channel order.
 * No fast-math, approximate activations or claimed integer quantization. */
#include "road_fp32.h"
#include <math.h>
#include <float.h>
#include <stdlib.h>
#include <string.h>
#if !defined(ROAD_FORCE_SCALAR) && (defined(__ARM_NEON) || defined(__ARM_NEON__))
#include <arm_neon.h>
typedef float32x4_t V4;
static V4 load4(const float *p){return vld1q_f32(p);}
static void store4(float *p,V4 x){vst1q_f32(p,x);}
static V4 mac4(V4 a,V4 b,float x){return vmlaq_n_f32(a,b,x);}
#elif !defined(ROAD_FORCE_SCALAR) && defined(__SSE2__)
#include <emmintrin.h>
typedef __m128 V4;
static V4 load4(const float *p){return _mm_loadu_ps(p);}
static void store4(float *p,V4 x){_mm_storeu_ps(p,x);}
static V4 mac4(V4 a,V4 b,float x){return _mm_add_ps(a,_mm_mul_ps(b,_mm_set1_ps(x)));}
#else
typedef struct{float v[4];} V4;
static V4 load4(const float *p){V4 a;int i;for(i=0;i<4;i++)a.v[i]=p[i];return a;}
static void store4(float *p,V4 a){int i;for(i=0;i<4;i++)p[i]=a.v[i];}
static V4 mac4(V4 a,V4 b,float x){int i;for(i=0;i<4;i++)a.v[i]+=b.v[i]*x;return a;}
#endif
static float sigmoid(float x){if(x>=0.0f)return 1.0f/(1.0f+expf(-x));{float e=expf(x);return e/(1.0f+e);}}
void road_preprocess400(const uint32_t *rgb,uint8_t *out){
  int y,x,k;memset(out,114,320U*320U*3U);
  for(y=0;y<192;y++)for(x=0;x<320;x++){
    int ax=10*x+1,ay=10*y+1,ix=ax/8,iy=ay/8,fx=ax%8,fy=ay%8;
    uint32_t a=rgb[iy*400+ix],b=rgb[iy*400+ix+1],c=rgb[(iy+1)*400+ix],d=rgb[(iy+1)*400+ix+1];
    for(k=0;k<3;k++){
      unsigned s=((a>>(8*k))&255U)*(8-fx)*(8-fy)+((b>>(8*k))&255U)*fx*(8-fy)+
                 ((c>>(8*k))&255U)*(8-fx)*fy+((d>>(8*k))&255U)*fx*fy;
      out[((y+64)*320+x)*3+k]=(uint8_t)((s+32U)/64U);
    }
  }
}
void road_input320(const uint8_t *rgb,float *arena){
  uint32_t i;float *out=arena+ROAD_T[0].off;
  for(i=0;i<320U*320U;i++){out[4*i]=rgb[3*i]/255.0f;out[4*i+1]=rgb[3*i+1]/255.0f;out[4*i+2]=rgb[3*i+2]/255.0f;out[4*i+3]=0;}
}
static void conv(const RoadOp *op,const RoadTensor *in,const RoadTensor *out,const float *a,const float *weights,float *b){
  int y,x,o,ky,kx,ic;const float *w=weights+op->wo,*bias=weights+op->bo;
  for(y=0;y<out->h;y++)for(x=0;x<out->w;){
    float *dst=b+(y*out->w+x)*out->c4;
    int tile=(x+3<out->w && y*op->s>=op->p && y*op->s+op->k<=in->h+op->p &&
              x*op->s>=op->p && (x+3)*op->s+op->k<=in->w+op->p)?4:1;
    for(o=0;o<out->c4;o+=4){
      V4 sum=load4(bias+o);
      if(tile==4){
        V4 sum1=sum,sum2=sum,sum3=sum;
        for(ky=0;ky<op->k;ky++)for(kx=0;kx<op->k;kx++){
          int iy=y*op->s+ky-op->p,ix=x*op->s+kx-op->p,step=op->s*in->c4;
          const float *src=a+(iy*in->w+ix)*in->c4,*wp=w+((ky*op->k+kx)*in->c4)*out->c4+o;
          for(ic=0;ic<in->c4;ic++,wp+=out->c4){
            V4 weight=load4(wp);
            sum=mac4(sum,weight,src[ic]);sum1=mac4(sum1,weight,src[ic+step]);
            sum2=mac4(sum2,weight,src[ic+2*step]);sum3=mac4(sum3,weight,src[ic+3*step]);
          }
        }
        store4(dst+o,sum);store4(dst+out->c4+o,sum1);store4(dst+2*out->c4+o,sum2);store4(dst+3*out->c4+o,sum3);
        continue;
      }
      for(ky=0;ky<op->k;ky++){
        int iy=y*op->s+ky-op->p;if(iy<0||iy>=in->h)continue;
        for(kx=0;kx<op->k;kx++){
          int ix=x*op->s+kx-op->p;const float *src,*wp;if(ix<0||ix>=in->w)continue;
          src=a+(iy*in->w+ix)*in->c4;wp=w+((ky*op->k+kx)*in->c4)*out->c4+o;
          for(ic=0;ic<in->c4;ic++,wp+=out->c4)sum=mac4(sum,load4(wp),src[ic]);
        }
      }
      store4(dst+o,sum);
    }
    if(op->act){int p;for(p=0;p<tile;p++)for(o=0;o<out->c;o++){float *v=dst+p*out->c4+o;*v=*v*sigmoid(*v);}}
    x+=tile;
  }
}
int road_forward(const float *weights,float *arena,RoadTrace trace,void *opaque){
  int i;if(!weights||!arena)return -1;
  if(trace)trace(0,arena+ROAD_T[0].off,(uint32_t)(320*320*4),opaque);
  for(i=1;i<ROAD_TENSORS;i++){
    const RoadOp *op=ROAD_OPS+i-1;const RoadTensor *out=ROAD_T+i,*in=ROAD_T+op->in[0];
    float *b=arena+out->off;const float *a=arena+in->off;int y,x,c,j;
    if(op->kind==1)conv(op,in,out,a,weights,b);
    else if(op->kind==2){
      const float *d=arena+ROAD_T[op->in[1]].off;uint32_t n=(uint32_t)(out->h*out->w*out->c4),q;
      for(q=0;q<n;q++)b[q]=a[q]+d[q];
    }else if(op->kind==3){
      for(y=0;y<out->h*out->w;y++){
        float *dst=b+y*out->c4;int off=0;
        for(j=0;j<op->n;j++){
          const RoadTensor *t=ROAD_T+op->in[j];memcpy(dst+off,arena+t->off+y*t->c4,t->c*sizeof(float));off+=t->c;
        }
        for(c=out->c;c<out->c4;c++)dst[c]=0;
      }
    }else if(op->kind==4){
      for(y=0;y<out->h;y++)for(x=0;x<out->w;x++)for(c=0;c<out->c4;c++){
        float best=-FLT_MAX;int ky,kx;
        for(ky=-2;ky<=2;ky++)if(y+ky>=0&&y+ky<in->h)
          for(kx=-2;kx<=2;kx++)if(x+kx>=0&&x+kx<in->w){float v=a[((y+ky)*in->w+x+kx)*in->c4+c];if(v>best)best=v;}
        b[(y*out->w+x)*out->c4+c]=best;
      }
    }else if(op->kind==5){
      for(y=0;y<out->h;y++)for(x=0;x<out->w;x++)memcpy(b+(y*out->w+x)*out->c4,a+((y/2)*in->w+x/2)*in->c4,in->c4*sizeof(float));
    }else return -2;
    if(trace)trace(i,b,(uint32_t)(out->h*out->w*out->c4),opaque);
  }
  return 0;
}
void road_decode(const float *arena,float *decoded){
  int level,anchor,y,x,k,offset=0;
  for(level=0;level<3;level++){
    const RoadTensor *t=ROAD_T+ROAD_HEADS[level];const float *src=arena+t->off;float stride=ROAD_STRIDES[level];
    for(anchor=0;anchor<3;anchor++)for(y=0;y<t->h;y++)for(x=0;x<t->w;x++){
      const float *v=src+(y*t->w+x)*t->c4+anchor*9;float *d=decoded+offset*9;
      float sx=sigmoid(v[0]),sy=sigmoid(v[1]),sw=sigmoid(v[2])*2,sh=sigmoid(v[3])*2;
      d[0]=(sx*2+(float)x-.5f)*stride;d[1]=(sy*2+(float)y-.5f)*stride;
      d[2]=sw*sw*ROAD_ANCHORS[level][anchor][0];d[3]=sh*sh*ROAD_ANCHORS[level][anchor][1];
      for(k=4;k<9;k++)d[k]=sigmoid(v[k]);
      offset++;
    }
  }
}
static int compare_boxes(const void *aa,const void *bb){
  const RoadBox *a=(const RoadBox *)aa,*b=(const RoadBox *)bb;
  if(a->score>b->score)return -1;
  if(a->score<b->score)return 1;
  return a->order-b->order;
}
static float overlap(const RoadBox *a,const RoadBox *b){
  float offset=(float)a->cls*7680.0f;
  float ax1=a->x1+offset,ax2=a->x2+offset,ay1=a->y1+offset,ay2=a->y2+offset;
  float bx1=b->x1+offset,bx2=b->x2+offset,by1=b->y1+offset,by2=b->y2+offset;
  float x1=fmaxf(ax1,bx1),y1=fmaxf(ay1,by1),x2=fminf(ax2,bx2),y2=fminf(ay2,by2);
  float intersection=fmaxf(0,x2-x1)*fmaxf(0,y2-y1),den=(ax2-ax1)*(ay2-ay1)+(bx2-bx1)*(by2-by1)-intersection;
  return den>0?intersection/den:0;
}
int road_nms(const float *decoded,RoadBox *candidates,RoadBox *output,int max_output,float confidence,float iou){
  uint8_t suppressed[ROAD_CANDIDATES];int n=0,i,j,count=0;
  if(max_output<0||confidence<0||confidence>1||iou<0||iou>1)return -1;
  for(i=0;i<ROAD_CANDIDATES;i++){
    const float *v=decoded+i*9;float best=-1;int cls=0,k;
    if(!(v[4]>confidence))continue;
    for(k=0;k<4;k++){float p=v[4]*v[k+5];if(p>best){best=p;cls=k;}}
    if(!(best>confidence))continue;
    candidates[n].x1=v[0]-v[2]/2;candidates[n].y1=v[1]-v[3]/2;
    candidates[n].x2=v[0]+v[2]/2;candidates[n].y2=v[1]+v[3]/2;
    candidates[n].score=best;candidates[n].cls=cls;candidates[n].order=i;n++;
  }
  qsort(candidates,(size_t)n,sizeof(RoadBox),compare_boxes);memset(suppressed,0,(size_t)n);
  for(i=0;i<n&&count<max_output;i++)if(!suppressed[i]){
    output[count++]=candidates[i];
    for(j=i+1;j<n;j++)if(!suppressed[j]&&candidates[i].cls==candidates[j].cls&&overlap(candidates+i,candidates+j)>iou)suppressed[j]=1;
  }
  return count;
}
void road_boxes_to400(RoadBox *boxes,int count){
  int i;for(i=0;i<count;i++){
    boxes[i].x1=fminf(400,fmaxf(0,boxes[i].x1/.8f));boxes[i].x2=fminf(400,fmaxf(0,boxes[i].x2/.8f));
    boxes[i].y1=fminf(240,fmaxf(0,(boxes[i].y1-64)/.8f));boxes[i].y2=fminf(240,fmaxf(0,(boxes[i].y2-64)/.8f));
  }
}
