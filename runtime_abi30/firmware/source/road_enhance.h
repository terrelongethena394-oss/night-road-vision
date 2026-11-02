#ifndef ROAD_ENHANCE_H
#define ROAD_ENHANCE_H
#include <stdint.h>
typedef struct {uint32_t mean_in,mean_out,alpha,cap,changed,max_delta;} RoadEnhanceStats;
/* ABI22 custom Retinex; mode0 raw; default cap48. See wrapper for cap semantics. */
int road_enhance(const uint32_t *,uint32_t *,uint32_t,unsigned,unsigned,RoadEnhanceStats *,void (*)(void *),void *);
#endif
