/* FP32 3x3 convolution prototype. GPL-3.0; YOLOv5-derived data layout.
 * Bias and reduction order preserved; SiLU remains outside this unit. */
#ifndef ROAD_CONV3_HLS_H
#define ROAD_CONV3_HLS_H
#include <ap_int.h>
#ifndef RC_PE
#define RC_PE 8
#endif
#if RC_PE!=4 && RC_PE!=8 && RC_PE!=16
#error RC_PE_must_be_4_or_8_or_16
#endif
typedef ap_uint<32*RC_PE> RoadWord;
#define RC_MAX_IC 128
#define RC_MAX_OC 256
#define RC_TILE 16
#define RC_PATCH 33
#define RC_MAX_INPUT (160*160*128)
#define RC_MAX_WEIGHT_WORDS ((256/RC_PE)*(9*128+1))
#define RC_MAX_OUTPUT_WORDS ((80*80*256)/RC_PE)
int road_conv3_fp32(const float *input,const RoadWord *weights_mem,RoadWord *output,int height,int width,int ic4,int oc4,int stride,int kernel);
#endif
