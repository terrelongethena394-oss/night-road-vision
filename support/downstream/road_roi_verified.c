#include "road_roi_verified.h"
#include <math.h>
#include <string.h>
static int eligible(const RoadBox *full,int nf,const RoadBox *b,const RoadRoiPolicy *p){
 float w=b->x2-b->x1,h=b->y2-b->y1,ba=fmaxf(w*h,1e-9f),border;int j;
 if(b->cls!=0||b->score<.05f||h<=0.f||w<=0.f)return 0;
 border=fminf(fminf(b->x1-100.f,b->y1-60.f),fminf(300.f-b->x2,180.f-b->y2));
 if(border<p->border||w/fmaxf(h,1e-9f)<p->person_aspect_min||w/fmaxf(h,1e-9f)>p->person_aspect_max)return 0;
 for(j=0;j<nf;j++)if(full[j].cls==0&&full[j].score>=.25f){
  float v=fmaxf(0.f,fminf(b->x2,full[j].x2)-fmaxf(b->x1,full[j].x1))*fmaxf(0.f,fminf(b->y2,full[j].y2)-fmaxf(b->y1,full[j].y1));
  float fa=fmaxf(0.f,full[j].x2-full[j].x1)*fmaxf(0.f,full[j].y2-full[j].y1);
  if(v/(ba+fa-v+1e-9f)>=p->dedup_iou||v/(fminf(ba,fa)+1e-9f)>=p->dedup_containment)return 0;
 }
 return 1;
}
int road_roi_verified_fuse(const RoadBox *full,int nf,const RoadBox *roi,int nr,
 const uint8_t *bgr800,const float *weights,const RoadRoiPolicy *policy,
 double floor,RoadBox *output,int capacity){
 RoadBox proposals[300];uint8_t patch[ROAD_PERSON_PATCH_BYTES];int i;
 if(!full||!roi||!bgr800||!weights||!policy||!output||nf<0||nf>300||nr<0||nr>300||floor<0.||floor>1.)return -1;
 memcpy(proposals,roi,(size_t)nr*sizeof(RoadBox));
 for(i=0;i<nr;i++)if(eligible(full,nf,proposals+i,policy)){
  float probability,factor;
  if(road_person_crop(bgr800,proposals+i,patch))return -2;
  probability=road_person_probability(patch,weights);if(!isfinite(probability))return -3;
  factor=(float)(floor+(1.-floor)*(double)probability);proposals[i].score*=factor;
 }
 return road_roi_fuse(full,nf,proposals,nr,policy,output,capacity);
}
