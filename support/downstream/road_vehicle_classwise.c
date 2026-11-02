/* Class-specific multi-view score calibration. GPL-3.0 detector types.
 * Derived from project road_vehicle_multiview.c; network and inputs unchanged. */
#include "road_vehicle_classwise.h"
#include <math.h>
#include <stdlib.h>
typedef struct {RoadBox b;int order;} Row;
static Row rows[1200],final_rows[300];
static RoadBox persons[300];
static unsigned char dead[1200];
static float lo(float a,float b){return a<b?a:b;}
static float hi(float a,float b){return a>b?a:b;}
static float area(const RoadBox *a){return hi(0.f,a->x2-a->x1)*hi(0.f,a->y2-a->y1);}
static float inter(const RoadBox *a,const RoadBox *b){return hi(0.f,lo(a->x2,b->x2)-hi(a->x1,b->x1))*hi(0.f,lo(a->y2,b->y2)-hi(a->y1,b->y1));}
static int cmp(const void *av,const void *bv){const Row *a=av,*b=bv;if(a->b.score>b->b.score)return -1;if(a->b.score<b->b.score)return 1;return a->order<b->order?-1:(a->order>b->order?1:0);}
static float offset_iou(RoadBox a,RoadBox b){float x=(float)a.cls*7680.f,y=(float)b.cls*7680.f,v;a.x1+=x;a.y1+=x;a.x2+=x;a.y2+=x;b.x1+=y;b.y1+=y;b.x2+=y;b.y2+=y;v=inter(&a,&b);return v/(area(&a)+area(&b)-v+1e-9f);}
static int valid(const RoadBox *b){return b->cls>=0&&b->cls<4&&isfinite(b->x1)&&isfinite(b->y1)&&isfinite(b->x2)&&isfinite(b->y2)&&isfinite(b->score);}
int road_vehicle_classwise(const RoadBox *full,int nf,const RoadBox *tiles,const int counts[3],const float weights[4],RoadBox *out,int capacity){
 int i,j,t,n=0,np=0,nv=0,kept,limit;
 if(!full||!tiles||!counts||!weights||!out||nf<0||nf>300||capacity!=300)return -1;
 for(t=0;t<4;t++)if(!isfinite(weights[t])||weights[t]<0.f||weights[t]>1.f)return -5;
 for(i=0;i<nf;i++){
  if(!valid(full+i))return -2;
  if(full[i].cls==0)persons[np++]=full[i];else{rows[n].b=full[i];rows[n].order=n;n++;}
 }
 for(t=0;t<3;t++){
  if(counts[t]<0||counts[t]>300)return -3;
  for(i=0;i<counts[t];i++){
   RoadBox b=tiles[t*300+i];int reject=0;float ba;
   if(!valid(&b))return -4;
   if(b.cls==0||weights[b.cls]<=0.f||b.score<.05f||!(b.x1>1.f&&b.y1>1.f&&b.x2<399.f&&b.y2<239.f))continue;
   b.x1=b.x1*.5f+(float)t*100.f;b.x2=b.x2*.5f+(float)t*100.f;b.y1=b.y1*.5f+60.f;b.y2=b.y2*.5f+60.f;ba=area(&b);
   for(j=0;j<nf;j++)if(full[j].cls==b.cls&&full[j].score>=.25f){float v=inter(&b,full+j),fa=area(full+j);if(v/(ba+fa-v+1e-9f)>=.3f||v/(lo(ba,fa)+1e-9f)>=.8f){reject=1;break;}}
   if(reject)continue;
   b.score*=weights[b.cls];rows[n].b=b;rows[n].order=n;n++;
  }
 }
 qsort(rows,(size_t)n,sizeof(Row),cmp);
 for(i=0;i<n;i++)dead[i]=0;
 limit=capacity-np;
 for(i=0;i<n&&nv<limit;i++){
  if(dead[i])continue;
  final_rows[np+nv].b=rows[i].b;final_rows[np+nv].order=np+nv;nv++;
  for(j=i+1;j<n;j++)if(!dead[j]&&rows[i].b.cls==rows[j].b.cls&&offset_iou(rows[i].b,rows[j].b)>.6f)dead[j]=1;
 }
 for(i=0;i<np;i++){final_rows[i].b=persons[i];final_rows[i].order=i;}
 kept=np+nv;qsort(final_rows,(size_t)kept,sizeof(Row),cmp);
 for(i=0;i<kept;i++)out[i]=final_rows[i].b;
 return kept;
}
