#ifndef ROAD_VEHICLE_MULTIVIEW_H
#define ROAD_VEHICLE_MULTIVIEW_H
#include "road_fp32.h"
/* Non-reentrant scratch is internal; callers run one fusion at a time.
 * tiles contains three consecutive 300-box buffers, in local400 coordinates.
 * No ground-truth labels, image enhancement or hardware I/O are consulted.
 */
int road_vehicle_multiview(const RoadBox *full,int nf,const RoadBox *tiles,const int counts[3],float weight,RoadBox *out,int capacity);
#endif
