#ifndef ROAD_ROI_VERIFY_HW_H
#define ROAD_ROI_VERIFY_HW_H
#include "road_fp32.h"
#include <stdint.h>
#define ROI_VERIFY_WEIGHT 0x1B000000U
#define ROI_NATIVE_INPUT(i) (0x1D000000U+(unsigned)(i)*0x60000U)
#define ROI_NATIVE_DECODE(i) (0x1D300000U+(unsigned)(i)*0x40000U)
#define ROI_LOCAL_BOXES 0x1D500000U
#define ROI_BASE_FLOAT 0x1D510000U
#define ROI_FINAL_FLOAT 0x1D520000U
#define ROI_PLAN_DATA 0x1D530000U
#define ROI_BASE_STRUCT 0x1D540000U
int road_roi_verify_live(const float *,const uint8_t *,const RoadBox *,int,RoadBox *,unsigned *,uint64_t *);
#endif
