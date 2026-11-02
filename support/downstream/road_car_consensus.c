/* Confidence verification only: no new boxes or changed coordinates. */
#include <math.h>
#include <stddef.h>
static float clip(float x,float a,float b){return x<a?a:(x>b?b:x);}
int road_car_consensus(const float *raw,int nr,const float *helper,int nh,
 float penalty,float boost,float bypass,float *out,int cap){
 int i,j,k,n=0;
 if(nr<0||nr>300||nh<0||nh>300||cap<nr||!out||(nr&&!raw)||(nh&&!helper)||penalty<0.f||penalty>1.f||boost<0.f||boost>1.f)return -1;
 for(i=0;i<nr;i++){
  const float *a=raw+6*i;float support=0.f,w=a[2]-a[0],h=a[3]-a[1],score=a[4];
  if((int)a[5]!=1)continue;
  if(!(bypass>0.f&&(w<bypass||h<bypass))){
   for(j=0;j<nh;j++){
    const float *b=helper+6*j;float iw=fmaxf(0.f,fminf(a[2],b[2])-fmaxf(a[0],b[0]));
    float ih=fmaxf(0.f,fminf(a[3],b[3])-fmaxf(a[1],b[1]));
    float inter=iw*ih,area=fmaxf(0.f,w)*fmaxf(0.f,h);
    float other=fmaxf(0.f,b[2]-b[0])*fmaxf(0.f,b[3]-b[1]);
    float iou=inter/(area+other-inter+1e-9f);
    if((int)b[5]==1&&iou>=.3f){float v=b[4]*fminf(1.f,iou/.5f);if(v>support)support=v;}
   }
   score=score*(1.f-penalty*(1.f-support))+boost*(1.f-score)*support;
  }
  score=clip(score,0.f,1.f);if(score<.001f)continue;
  for(k=0;k<6;k++){out[6*n+k]=a[k];}
  out[6*n+4]=score;n++;
 }
 /* Stable insertion sort, descending new confidence. */
 for(i=1;i<n;i++){
  float a[6];for(k=0;k<6;k++)a[k]=out[6*i+k];j=i-1;
  while(j>=0&&out[6*j+4]<a[4]){for(k=0;k<6;k++)out[6*(j+1)+k]=out[6*j+k];j--;}
  for(k=0;k<6;k++)out[6*(j+1)+k]=a[k];
 }
 return n;
}
