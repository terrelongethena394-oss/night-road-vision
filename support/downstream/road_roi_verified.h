#ifndef ROAD_ROI_VERIFIED_H
#define ROAD_ROI_VERIFIED_H
#include "road_roi_guard.h"
#include "road_person_verifier.h"
int road_roi_verified_fuse(const RoadBox *full,int nf,const RoadBox *roi,int nr,
 const uint8_t *bgr800,const float *person_weights,const RoadRoiPolicy *policy,
 double floor,RoadBox *output,int capacity);
#endif
