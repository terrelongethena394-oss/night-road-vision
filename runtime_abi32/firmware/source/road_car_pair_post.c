#include "road_car_pair_post.h"
#include "road_vehicle_multiview.h"
static RoadBox all[300];
int road_car_multiview(const RoadBox *full,int count,const RoadBox *tiles,const int counts[3],RoadBox *out,int capacity){
 int i,n,kept=0;
 if(!out||capacity!=300)return -1;
 n=road_vehicle_multiview(full,count,tiles,counts,.75f,all,300);
 if(n<0)return n;
 for(i=0;i<n;i++)if(all[i].cls==1)out[kept++]=all[i];
 return kept;
}
