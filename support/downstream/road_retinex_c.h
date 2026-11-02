#ifndef ROAD_RETINEX_C_H
#define ROAD_RETINEX_C_H
#include <stdint.h>
#define ROAD_RETI_W 400U
#define ROAD_RETI_H 240U
#define ROAD_RETI_N (ROAD_RETI_W*ROAD_RETI_H)
#define ROAD_RETI_WORK_FLOATS (17U*ROAD_RETI_N+65536U)
typedef struct {float mean_in,mean_out,noise_proxy,alpha,max_gain;} RoadRetinexStats;
/* Frozen project_strong parameters: tone exponent.25, gain48, denoise.95.
 * Input/output RGB little-endian words, upper byte zero. Workspace external.
 * No allocation, SD access or FPGA register access; caller owns workspace.
 * Derived classical illumination concept: doi10.1109/TCSII.2024.3361561.
 */
int road_retinex_c(const uint32_t *,uint32_t *,unsigned,float *,RoadRetinexStats *,void (*)(void *),void *);
#endif
