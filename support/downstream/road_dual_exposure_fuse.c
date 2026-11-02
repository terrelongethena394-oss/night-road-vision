/* Fixed two-branch car-box fusion; no labels, image IDs or device I/O. */
#include <math.h>
#include <string.h>
typedef struct {float x[6];unsigned order;} PairBox;
static float hi(float a,float b){return a>b?a:b;}
static float lo(float a,float b){return a<b?a:b;}
static float overlap(const float *a,const float *b){
 float z=hi(0.f,lo(a[2],b[2])-hi(a[0],b[0]))*hi(0.f,lo(a[3],b[3])-hi(a[1],b[1]));
 float aa=hi(0.f,a[2]-a[0])*hi(0.f,a[3]-a[1]),bb=hi(0.f,b[2]-b[0])*hi(0.f,b[3]-b[1]);return z/(aa+bb-z+1e-7f);
}
int road_dual_fuse(const float *a,int na,const float *b,int nb,float threshold,float unmatched,int score_mode,int coordinate_mode,float *out){
 PairBox p[600];unsigned used[300]={0},dead[600]={0};int i,j,k,n=0,kept=0;
 if(!a||!b||!out||na<0||na>300||nb<0||nb>300||threshold<=0.f||threshold>=1.f||unmatched<=0.f||unmatched>1.f||score_mode<0||score_mode>1||coordinate_mode<0||coordinate_mode>1)return -1;
 for(i=0;i<na+nb;i++){const float *q=i<na?a+i*6:b+(i-na)*6;for(j=0;j<6;j++)if(!isfinite(q[j]))return -2;if(q[5]!=1.f||q[4]<0.f||q[4]>1.f)return -3;}
 for(i=0;i<na;i++){
  const float *q=a+i*6;int match=-1;float best=threshold;
  for(j=0;j<nb;j++)if(!used[j]){float v=overlap(q,b+j*6);if(v>=best){best=v;match=j;}}
  memcpy(p[n].x,q,6*sizeof(float));
  if(match>=0){
   const float *r=b+match*6;float w=coordinate_mode?.5f:q[4]/hi(q[4]+r[4],1e-12f);used[match]=1;
   for(k=0;k<4;k++)p[n].x[k]=q[k]*w+r[k]*(1.f-w);
   p[n].x[4]=score_mode?(q[4]+r[4])*.5f:sqrtf(q[4]*r[4]);
  }else p[n].x[4]*=unmatched;
  p[n].order=(unsigned)n;n++;
 }
 for(j=0;j<nb;j++)if(!used[j]){memcpy(p[n].x,b+j*6,6*sizeof(float));p[n].x[4]*=unmatched;p[n].order=(unsigned)n;n++;}
 for(i=1;i<n;i++){PairBox q=p[i];j=i;while(j>0&&p[j-1].x[4]<q.x[4]){p[j]=p[j-1];j--;}p[j]=q;}
 for(i=0;i<n&&kept<300;i++)if(!dead[i]){
  memcpy(out+kept*6,p[i].x,6*sizeof(float));kept++;
  for(j=i+1;j<n;j++)if(!dead[j]&&overlap(p[i].x,p[j].x)>.6f)dead[j]=1;
 }
 return kept;
}
