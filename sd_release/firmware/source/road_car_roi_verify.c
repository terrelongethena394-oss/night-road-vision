/* Native-detail verification planning/postprocessing. One CPU caller.
 * No labels, filenames or SD/Flash accesses. Scratch is in .bss, not stack. */
#include <math.h>
#include <string.h>
static float rv_current[300][6],rv_shift[300][4],rv_area[300];
static int rv_order[300],rv_dead[300];
static float hi(float a,float b){return a>b?a:b;}
static float lo(float a,float b){return a<b?a:b;}
static float area(const float *a){return hi(0.f,a[2]-a[0])*hi(0.f,a[3]-a[1]);}
static float iou(const float *a,const float *b){float v=hi(0.f,lo(a[2],b[2])-hi(a[0],b[0]))*hi(0.f,lo(a[3],b[3])-hi(a[1],b[1]));return v/(area(a)+area(b)-v+1e-7f);}
static int valid_base(const float *base,int n){int i,j;if(!base||n<0||n>300)return 0;for(i=0;i<n;i++){const float *b=base+i*6;for(j=0;j<6;j++)if(!isfinite(b[j]))return 0;if(b[5]!=1.f||b[4]<0.f||b[4]>1.f)return 0;}return 1;}
int road_roi_plan(const float *base,int n,int *indices,int *xy){
 int order[300],i,j,count=0,k=0;
 if(!indices||!xy||!valid_base(base,n))return -1;
 for(i=0;i<n;i++){
  const float *b=base+i*6;float h=b[3]-b[1];
  if(b[4]>=.15f&&b[4]<.65f&&h>=3.f&&h<20.f&&b[2]-b[0]>=4.f)order[count++]=i;
 }
 for(i=1;i<count;i++){int v=order[i];j=i;while(j>0&&base[order[j-1]*6+4]<base[v*6+4]){order[j]=order[j-1];j--;}order[j]=v;}
 for(i=0;i<count&&k<8;i++){
  const float *b=base+order[i]*6;int x=(int)floor((double)(b[0]+b[2])-80.+.5),y=(int)floor((double)(b[1]+b[3])-48.+.5),duplicate=0;
  if(x<0)x=0;
  if(x>640)x=640;
  if(y<0)y=0;
  if(y>384)y=384;
  for(j=0;j<k;j++)if(xy[j*2]==x&&xy[j*2+1]==y)duplicate=1;
  if(duplicate)continue;
  indices[k]=order[i];xy[k*2]=x;xy[k*2+1]=y;k++;
 }
 return k;
}
int road_roi_refine(const float *base,int n,int k,const int *indices,const int *xy,const float *local,const int *counts,float *out){
 int t,i,j,c,kept=0;
 if(!valid_base(base,n)||!indices||!xy||!local||!counts||!out||k<0||k>8)return -1;
 memcpy(rv_current,base,(unsigned)n*6U*sizeof(float));
 for(t=0;t<k;t++){
  int index=indices[t],match=0;float original[6],chosen[6]={0},best=-1.f;
  if(index<0||index>=n||counts[t]<0||counts[t]>300||xy[t*2]<0||xy[t*2]>640||xy[t*2+1]<0||xy[t*2+1]>384)return -2;
  for(i=0;i<t;i++)if(indices[i]==index)return -2;
  memcpy(original,rv_current[index],6*sizeof(float));
  for(i=0;i<counts[t];i++){
   const float *p=local+(t*300+i)*6;float b[6],ov,metric;
   for(c=0;c<6;c++)if(!isfinite(p[c]))return -3;
   if(p[5]!=1.f||!(p[0]>1.f&&p[1]>1.f&&p[2]<399.f&&p[3]<239.f))continue;
   memcpy(b,p,6*sizeof(float));b[0]=p[0]*.2f+(float)xy[t*2]*.5f;b[2]=p[2]*.2f+(float)xy[t*2]*.5f;b[1]=p[1]*.2f+(float)xy[t*2+1]*.5f;b[3]=p[3]*.2f+(float)xy[t*2+1]*.5f;
   ov=iou(original,b);if(ov<.2f)continue;metric=ov*(.5f+.5f*p[4]);
   if(metric>best){best=metric;memcpy(chosen,b,6*sizeof(float));match=1;}
  }
  if(match){rv_current[index][4]=sqrtf(original[4]*chosen[4]);if(chosen[4]>=.25f)memcpy(rv_current[index],chosen,4*sizeof(float));}
  else rv_current[index][4]*=.5f;
 }
 for(i=0;i<n;i++){rv_order[i]=i;rv_dead[i]=0;for(c=0;c<4;c++)rv_shift[i][c]=rv_current[i][c]+7680.f;rv_area[i]=area(rv_shift[i]);}
 for(i=1;i<n;i++){int v=rv_order[i];j=i;while(j>0&&rv_current[rv_order[j-1]][4]<rv_current[v][4]){rv_order[j]=rv_order[j-1];j--;}rv_order[j]=v;}
 for(t=0;t<n&&kept<300;t++){
  int a=rv_order[t];if(rv_dead[a])continue;memcpy(out+kept*6,rv_current[a],6*sizeof(float));kept++;
  for(j=t+1;j<n;j++){
   int b=rv_order[j];float v,ov;if(rv_dead[b])continue;
   v=hi(0.f,lo(rv_shift[a][2],rv_shift[b][2])-hi(rv_shift[a][0],rv_shift[b][0]))*hi(0.f,lo(rv_shift[a][3],rv_shift[b][3])-hi(rv_shift[a][1],rv_shift[b][1]));ov=v/(rv_area[a]+rv_area[b]-v+1e-9f);if(ov>.6f)rv_dead[b]=1;
  }
 }
 return kept;
}
