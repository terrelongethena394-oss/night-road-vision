#ifndef ROAD_BALANCED_EXTRA_H
#define ROAD_BALANCED_EXTRA_H
#include "road_fp32.h"
#include <stdint.h>
#define BAL_ZOOM_INPUT(i) (0x1C000000U+(unsigned)(i)*0x60000U)
#define BAL_ZOOM_DECODE(i) (0x1C120000U+(unsigned)(i)*0x40000U)
#define BAL_REFINER_WEIGHT 0x1C200000U
#define BAL_REFINER_PRED 0x1C240000U
#define BAL_REFINER_WORK 0x1C250000U
int road_balanced_extra(const float *,const uint8_t *,const RoadBox *,int,RoadBox *,unsigned *,uint64_t *);
#endif
