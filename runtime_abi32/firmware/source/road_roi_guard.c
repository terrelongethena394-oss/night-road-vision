/* Deterministic center-detail proposal fusion. No labels, SD or hardware I/O.
 * Detector-derived types retain YOLOv5 GPL-3.0 licensing.
 */
#include "road_roi_guard.h"
#include <math.h>
#include <stdlib.h>
typedef struct {RoadBox box;int order;} OrderedBox;
static float maximum(float a,float b){return a>b?a:b;}
static float minimum(float a,float b){return a<b?a:b;}
static float area(const RoadBox *b){return maximum(0.f,b->x2-b->x1)*maximum(0.f,b->y2-b->y1);}
static float overlap(const RoadBox *a,const RoadBox *b){
 return maximum(0.f,minimum(a->x2,b->x2)-maximum(a->x1,b->x1))*maximum(0.f,minimum(a->y2,b->y2)-maximum(a->y1,b->y1));
}
static int compare(const void *x,const void *y){
 const OrderedBox *a=(const OrderedBox *)x,*b=(const OrderedBox *)y;
 if(a->box.score>b->box.score)return -1;
 if(a->box.score<b->box.score)return 1;
 return a->order<b->order?-1:(a->order>b->order?1:0);
}
void road_roi_from_bgr800(const uint8_t *source,uint32_t *roi){
 unsigned x,y;
 for(y=0;y<240U;y++)for(x=0;x<400U;x++){
  const uint8_t *p=source+((y+120U)*800U+x+200U)*3U;
  roi[y*400U+x]=(uint32_t)p[2]|((uint32_t)p[1]<<8)|((uint32_t)p[0]<<16);
 }
}
int road_roi_map400(RoadBox *boxes,int count){
 int i,n=0;if(!boxes||count<0||count>300)return -1;
 for(i=0;i<count;i++){
  RoadBox b=boxes[i];if(!(b.x1>1.f&&b.y1>1.f&&b.x2<399.f&&b.y2<239.f))continue;
  b.x1=b.x1*.5f+100.f;b.x2=b.x2*.5f+100.f;b.y1=b.y1*.5f+60.f;b.y2=b.y2*.5f+60.f;boxes[n++]=b;
 }
 return n;
}
/* Match torchvision's float32 class-offset IoU arithmetic for fusion NMS. */
static float offset_iou(const RoadBox *a,const RoadBox *b){
 RoadBox x=*a,y=*b;float ox=(float)a->cls*7680.f,oy=(float)b->cls*7680.f,v;
 x.x1+=ox;x.y1+=ox;x.x2+=ox;x.y2+=ox;y.x1+=oy;y.y1+=oy;y.x2+=oy;y.y2+=oy;
 v=overlap(&x,&y);return v/(area(&x)+area(&y)-v);
}
int road_roi_fuse(const RoadBox *full,int nf,const RoadBox *roi,int nr,
                  const RoadRoiPolicy *p,RoadBox *output,int capacity){
 OrderedBox merged[600];unsigned char suppressed[600]={0};int i,j,n=0,kept=0;
 if(!full||!roi||!p||!output||nf<0||nf>300||nr<0||nr>300||capacity<0||capacity>300)return -1;
 for(i=0;i<nf;i++){merged[n].box=full[i];merged[n].order=n;n++;}
 for(i=0;i<nr;i++){
  RoadBox b=roi[i];float w=b.x2-b.x1,h=b.y2-b.y1,border,ba;int reject=0;
  if(b.cls<0||b.cls>3||!isfinite(b.score)||w<=0.f||h<=0.f)return -2;
  border=minimum(minimum(b.x1-100.f,b.y1-60.f),minimum(300.f-b.x2,180.f-b.y2));
  if(border<p->border)continue;
  if(b.cls==0&&(w/maximum(h,1e-9f)<p->person_aspect_min||w/maximum(h,1e-9f)>p->person_aspect_max))continue;
  ba=maximum(w*h,1e-9f);
  for(j=0;j<nf;j++)if(full[j].cls==b.cls&&full[j].score>=.25f){
   float v=overlap(&b,full+j),fa=area(full+j);
   if(v/(ba+fa-v+1e-9f)>=p->dedup_iou||v/(minimum(ba,fa)+1e-9f)>=p->dedup_containment){reject=1;break;}
  }
  if(reject)continue;
  b.score*=p->weight[b.cls];merged[n].box=b;merged[n].order=n;n++;
 }
 qsort(merged,(size_t)n,sizeof(merged[0]),compare);
 for(i=0;i<n&&kept<capacity;i++){
  if(suppressed[i])continue;
  output[kept++]=merged[i].box;
  for(j=i+1;j<n;j++)if(!suppressed[j]&&merged[i].box.cls==merged[j].box.cls&&offset_iou(&merged[i].box,&merged[j].box)>.6f)suppressed[j]=1;
 }
 return kept;
}
