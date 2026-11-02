/* GPL-3.0. Exact integer FPGA boundary, experimental quality tradeoff. */
#ifndef ROAD_QCONV_ARM_H
#define ROAD_QCONV_ARM_H
#include "road_fp32.h"
int qhw_prepare(const unsigned char *model);
void qhw_begin(void);
int qhw_try(int,const RoadOp *,const RoadTensor *,const RoadTensor *,const unsigned char *,const unsigned char *,unsigned char *,void (*poll)(void));
#ifdef QCONV_EMULATE
extern unsigned qhw_host_calls;
const void *qhw_host_weights(void);
const void *qhw_host_metadata(void);
#endif
#endif
