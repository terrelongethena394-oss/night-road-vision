/* GPL-3.0: FP32 convolution offload boundary, SiLU remains on ARM. */
#ifndef ROAD_PL_H
#define ROAD_PL_H
#include "road_fp32.h"
int road_pl_prepare(const float *weights);
void road_pl_begin(void);
int road_pl_try(int node,const RoadOp *,const RoadTensor *,const RoadTensor *,const float *,const float *,float *,void (*poll)(void));
#ifdef ROAD_PL_EMULATE
extern unsigned road_pl_host_calls;
const float *road_pl_host_packed(void);
#endif
#endif
