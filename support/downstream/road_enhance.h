#ifndef ROAD_ENHANCE_H
#define ROAD_ENHANCE_H
#include <stdint.h>
typedef struct {uint32_t mean_in,mean_out,alpha,cap,changed,max_delta;} RoadEnhanceStats;
/* mode0 raw, mode1 automatic exposure gate, mode2 forced bounded enhancement.
 * Integer RGB ratios are preserved to rounding; no per-pixel pow/division.
 * This is a traditional tone curve, not a learned enhancement network. */
int road_enhance(const uint32_t *,uint32_t *,uint32_t,unsigned,unsigned,RoadEnhanceStats *,void (*)(void *),void *);
#endif
