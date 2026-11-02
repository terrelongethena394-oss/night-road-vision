#ifndef ROAD_VEHICLE_CLASSWISE_H
#define ROAD_VEHICLE_CLASSWISE_H
#include "road_fp32.h"
/* weights are person/car/truck/bus fusion score multipliers, not NN weights.
 * Internal non-reentrant scratch; tiles are three 300-box local-coordinate buffers. */
int road_vehicle_classwise(const RoadBox *,int,const RoadBox *,const int[3],const float[4],RoadBox *,int);
#endif
