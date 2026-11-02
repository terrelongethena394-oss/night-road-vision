#ifndef ROAD_SHADOWLIFT_H
#define ROAD_SHADOWLIFT_H
#include <stdint.h>
typedef struct {float strength,mean_out,max_total_gain;} RoadShadowStats;
int road_shadowlift(const uint32_t *,uint32_t *,unsigned,float *,RoadShadowStats *,void (*)(void *),void *);
#endif
