/* Train-GT proposal verification, FP32, no hardware/SD accesses.
 * CPU implementation of the exact exported3-convolution network.
 */
#include "road_person_verifier.h"
#include <math.h>
static int clamp(int v,int lo,int hi){return v<lo?lo:(v>hi?hi:v);}
int road_person_crop(const uint8_t *src,const RoadBox *b,uint8_t *out){
 double x1,y1,x2,y2,cx,cy,w,h;int l,t,r,d,x,y;
 if(!src||!b||!out)return -1;
 x1=b->x1;y1=b->y1;x2=b->x2;y2=b->y2;cx=x1+x2;cy=y1+y2;w=(x2-x1)*2.;h=(y2-y1)*2.;
 if(!isfinite(w)||!isfinite(h)||w<=0||h<=0)return -1;
 l=clamp((int)floor(cx-.625*w),0,799);t=clamp((int)floor(cy-.625*h),0,479);
 r=clamp((int)ceil(cx+.625*w),l+1,800);d=clamp((int)ceil(cy+.625*h),t+1,480);
 for(y=0;y<48;y++)for(x=0;x<24;x++){
  int sx=l+((2*x+1)*(r-l))/48,sy=t+((2*y+1)*(d-t))/96;const uint8_t *p=src+(sy*800+sx)*3;uint8_t *q=out+(y*24+x)*3;q[0]=p[2];q[1]=p[1];q[2]=p[0];
 }
 return 0;
}
static void conv_relu(const float *input,int ih,int iw,int ic,float *out,int oc,const float *w,const float *bias){
 int oh=(ih+1)/2,ow=(iw+1)/2,y,x,o,ky,kx,c;
 for(y=0;y<oh;y++)for(x=0;x<ow;x++)for(o=0;o<oc;o++){
  float sum=bias[o];
  for(ky=0;ky<3;ky++){int sy=2*y+ky-1;if(sy<0||sy>=ih)continue;
   for(kx=0;kx<3;kx++){int sx=2*x+kx-1;if(sx<0||sx>=iw)continue;
    for(c=0;c<ic;c++)sum+=input[(sy*iw+sx)*ic+c]*w[((o*ic+c)*3+ky)*3+kx];
   }
  }
  out[(y*ow+x)*oc+o]=sum>0.f?sum:0.f;
 }
}
float road_person_probability(const uint8_t *patch,const float *w){
 float in[48*24*3],a[24*12*8],b[12*6*16],c[6*3*16],hidden[32],z;unsigned i,j;
 for(i=0;i<48U*24U*3U;i++)in[i]=(float)patch[i]/255.f;
 conv_relu(in,48,24,3,a,8,w,w+216);w+=224;
 conv_relu(a,24,12,8,b,16,w,w+1152);w+=1168;
 conv_relu(b,12,6,16,c,16,w,w+2304);w+=2320;
 for(i=0;i<32;i++){float s=w[9216+i];for(j=0;j<288;j++)s+=c[(j%18)*16+j/18]*w[i*288+j];hidden[i]=s>0.f?s:0.f;}w+=9248;
 z=w[32];for(i=0;i<32;i++)z+=hidden[i]*w[i];
 if(z>=0.f)return 1.f/(1.f+expf(-z));
 z=expf(z);return z/(1.f+z);
}
