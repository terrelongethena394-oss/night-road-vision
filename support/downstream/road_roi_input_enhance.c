/* Frozen ROI enhancement ablation kernels. RGB packed R in low byte.
 * These are input transforms only: no model, label, ROI or detector changes. */
#include <stdint.h>
#include <math.h>
#include <string.h>
#define W 400
#define H 240
#define N 96000
static float clip(float v,float a,float b){return v<a?a:(v>b?b:v);}
static int mirror(int x,int n){return x<0?-x:(x>=n?2*n-2-x:x);}
int road_roi_input_enhance(const uint32_t *src,const uint32_t *learned,uint32_t *dst,int method){
  uint64_t total=0;int i,k,x,y;
  if(!src||!dst||src==dst||method<0||method>9)return -1;
  for(i=0;i<N;i++){uint32_t a=src[i];total+=54U*(a&255U)+183U*((a>>8)&255U)+19U*((a>>16)&255U);}
  if(method==0||total>48ULL*256ULL*N){memcpy(dst,src,N*4U);return 0;}
  if(method>=1&&method<=4){
    static const unsigned ratio[4]={10,25,50,100};unsigned n=ratio[method-1];
    if(!learned)return -2;
    for(i=0;i<N;i++){uint32_t out=0;for(k=0;k<3;k++){
      unsigned a=(src[i]>>(8*k))&255U,b=(learned[i]>>(8*k))&255U;
      out|=((a*(100U-n)+b*n+50U)/100U)<<(8*k);
    }dst[i]=out;}
    return 0;
  }
  for(y=0;y<H;y++)for(x=0;x<W;x++){
    unsigned a[3],m=0;uint32_t q=src[y*W+x],out=0;float v,fade,delta=0;
    for(k=0;k<3;k++){a[k]=(q>>(8*k))&255U;if(a[k]>m)m=a[k];}
    v=(float)m/255.f;fade=1.f-clip((v-.65f)/.33f,0.f,1.f);
    if(method==5||method==6){
      float exponent=method==5?.90f:.75f;
      float g=v>1e-8f?powf(v,exponent)/v:1.f;
      g=1.f+(fminf(g,3.f)-1.f)*fade;
      for(k=0;k<3;k++)out|=(uint32_t)floorf(clip((float)a[k]*g,0.f,255.f)+.5f)<<(8*k);
    }else{
      if(method==7||method==8)delta=(float)(method==7?4:8)*(1.f-v)*fade;
      else{
        unsigned sum=0;int dx,dy;float lum=(float)(54U*a[0]+183U*a[1]+19U*a[2])/256.f;
        for(dy=-5;dy<=5;dy++)for(dx=-5;dx<=5;dx++){
          uint32_t b=src[mirror(y+dy,H)*W+mirror(x+dx,W)];
          sum+=54U*(b&255U)+183U*((b>>8)&255U)+19U*((b>>16)&255U);
        }
        {float illum=(float)sum/(121.f*256.f);
         float gain=1.f+.5f*(1.f-clip(illum/80.f,0.f,1.f))*fade;
         delta=lum*(gain-1.f);}
      }
      delta=fmaxf(0.f,fminf(delta,254.f-(float)m));
      for(k=0;k<3;k++)out|=(uint32_t)floorf(clip((float)a[k]+delta,0.f,255.f)+.5f)<<(8*k);
    }
    dst[y*W+x]=out;
  }
  return 0;
}
