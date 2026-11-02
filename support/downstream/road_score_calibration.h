#ifndef ROAD_SCORE_CALIBRATION_H
#define ROAD_SCORE_CALIBRATION_H
#include "road_fp32.h"
/* In-place score remapping, preserves box geometry and car/person scores. */
int road_score_calibrate(RoadBox *boxes,int count,float gain);
int road_score_calibrate_classwise(RoadBox *boxes,int count,float truck_gain,float bus_gain);
#endif
