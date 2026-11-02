#ifndef ROAD_RETINEX_C_H
#define ROAD_RETINEX_C_H
#include <stdint.h>
#define ROAD_RETI_W 400U
#define ROAD_RETI_H 240U
#define ROAD_RETI_N (ROAD_RETI_W*ROAD_RETI_H)
#define ROAD_RETI_WORK_FLOATS (32U*ROAD_RETI_N+65536U)
typedef struct {float mean_in,mean_out,noise_proxy,alpha,max_gain;} RoadRetinexStats;
/* Detail-balanced: illumination correction, gain<=5, chroma-only patch filter.
 * Original luminance is not spatially filtered. Caller provides workspace. */
int road_retinex_c(const uint32_t *,uint32_t *,unsigned,float *,RoadRetinexStats *,void (*)(void *),void *);
#endif
