/* Display-only learned low-frequency exposure correction.
 * Old validated texture/chroma are retained; only9x9mean luminance residual
 * from the frozen411weight student is mixed at strength.5.
 */
#include "road_retinex_c.h"
#include "road_shadowlift.h"
#include <math.h>
#include <string.h>
int road_retinex_base(const uint32_t *,uint32_t *,unsigned,float *,RoadRetinexStats *,void (*)(void *),void *);
int road_student_restore(const uint32_t *,uint32_t *,unsigned,float *,RoadRetinexStats *,void (*)(void *),void *);
#define W 400
#define H 240
#define N 96000
static int mirrorf(int x,int n){if(x<0)return -x;if(x>=n)return 2*n-2-x;return x;}
static float limitf(float x,float a,float b){return x<a?a:(x>b?b:x);}
static float fadef(float v){float t=limitf((v-.65f)/.33f,0.f,1.f);return 1.f-t*t*(3.f-2.f*t);}
int road_retinex_c(const uint32_t *src,uint32_t *dst,unsigned n,float *work,RoadRetinexStats *s,void (*cb)(void *),void *opaque){
 uint32_t *student=(uint32_t *)(work+31*N);float *diff=work,*tmp=work+N;RoadRetinexStats ns;RoadShadowStats extra;
 uint64_t total=0,outtotal=0;int i,y,x,k,c,e;float maxgain=1.f;
 if(!src||!dst||!work||!s||n!=N||src==dst)return 1;
 for(i=0;i<N;i++){uint32_t q=src[i];total+=54U*(q&255U)+183U*((q>>8)&255U)+19U*((q>>16)&255U);}
 if(total==0||total>48ULL*256ULL*N){memcpy(dst,src,N*4U);s->mean_in=s->mean_out=(float)((double)total/(N*256.));s->noise_proxy=0.f;s->alpha=0.f;s->max_gain=1.f;return 0;}
 e=road_retinex_base(src,dst,n,work,s,cb,opaque);if(e)return e;
 e=road_shadowlift(src,dst,n,work,&extra,cb,opaque);if(e)return e;
 e=road_student_restore(src,student,n,work,&ns,cb,opaque);if(e)return e;
 for(i=0;i<N;i++){
  uint32_t a=student[i],b=dst[i];diff[i]=((54.f*(float)(a&255U)+183.f*(float)((a>>8)&255U)+19.f*(float)((a>>16)&255U))-(54.f*(float)(b&255U)+183.f*(float)((b>>8)&255U)+19.f*(float)((b>>16)&255U)))/256.f;
 }
 for(y=0;y<H;y++){if(cb&&(y&15)==0)cb(opaque);for(x=0;x<W;x++){float sum=0.f;for(k=-4;k<=4;k++)sum+=diff[y*W+mirrorf(x+k,W)];tmp[y*W+x]=sum;}}
 for(y=0;y<H;y++){if(cb&&(y&15)==0)cb(opaque);for(x=0;x<W;x++){
  int at=y*W+x;uint32_t raw=src[at],base=dst[at],out=0;float sum=0.f,rgb[3],lo=255.f,hi=0.f,vraw=0.f,delta;
  for(k=-4;k<=4;k++)sum+=tmp[mirrorf(y+k,H)*W+x];
  for(c=0;c<3;c++){rgb[c]=(float)((base>>(8*c))&255U);lo=fminf(lo,rgb[c]);hi=fmaxf(hi,rgb[c]);vraw=fmaxf(vraw,(float)((raw>>(8*c))&255U));}
  delta=hi>=245.f?0.f:limitf(.5f*sum/81.f*fadef(vraw/255.f),-lo,254.f-hi);
  for(c=0;c<3;c++)out|=(uint32_t)floorf(rgb[c]+delta+.5f)<<(8*c);
  dst[at]=out;outtotal+=54U*(out&255U)+183U*((out>>8)&255U)+19U*((out>>16)&255U);
  if(vraw>0.f)maxgain=fmaxf(maxgain,(hi+delta)/vraw);
 }}
 s->mean_in=(float)((double)total/(N*256.));s->mean_out=(float)((double)outtotal/(N*256.));s->max_gain=maxgain;s->alpha=1.f;s->noise_proxy=0.f;return 0;
}
