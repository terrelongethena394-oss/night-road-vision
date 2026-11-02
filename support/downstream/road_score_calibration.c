#include "road_score_calibration.h"
#include <math.h>
#include <stdlib.h>
typedef struct {RoadBox box;int index;} CalibrationRow;
static CalibrationRow scratch[300];
static int compare(const void *av,const void *bv){
 const CalibrationRow *a=av,*b=bv;
 if(a->box.score>b->box.score)return -1;
 if(a->box.score<b->box.score)return 1;
 return a->index<b->index?-1:(a->index>b->index?1:0);
}
int road_score_calibrate_classwise(RoadBox *boxes,int count,float truck_gain,float bus_gain){
 int i;
 if(!boxes||count<0||count>300||!isfinite(truck_gain)||truck_gain<1.f||truck_gain>2.f||!isfinite(bus_gain)||bus_gain<1.f||bus_gain>2.f)return -1;
 for(i=0;i<count;i++){
  const RoadBox *p=boxes+i;
  if(p->cls<0||p->cls>3||!isfinite(p->x1)||!isfinite(p->y1)||!isfinite(p->x2)||!isfinite(p->y2)||!isfinite(p->score)||p->score<0.f||p->score>1.f)return -2;
 }
 for(i=0;i<count;i++){
  scratch[i].box=boxes[i];scratch[i].index=i;
  if(boxes[i].cls==2||boxes[i].cls==3){float gain=boxes[i].cls==2?truck_gain:bus_gain;float s=boxes[i].score;float denominator=1.f+(gain-1.f)*s;scratch[i].box.score=(gain*s)/denominator;}
 }
 qsort(scratch,(size_t)count,sizeof(CalibrationRow),compare);
 for(i=0;i<count;i++)boxes[i]=scratch[i].box;
 return count;
}
int road_score_calibrate(RoadBox *boxes,int count,float gain){return road_score_calibrate_classwise(boxes,count,gain,gain);}
