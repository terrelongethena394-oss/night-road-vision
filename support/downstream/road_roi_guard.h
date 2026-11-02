#ifndef ROAD_ROI_GUARD_H
#define ROAD_ROI_GUARD_H
#include <stdint.h>
#include "road_fp32.h"
typedef struct {
 float border,person_aspect_min,person_aspect_max,weight[4],dedup_iou,dedup_containment;
} RoadRoiPolicy;
void road_roi_from_bgr800(const uint8_t *source,uint32_t *roi);
int road_roi_map400(RoadBox *boxes,int count);
int road_roi_fuse(const RoadBox *full,int nf,const RoadBox *mapped_roi,int nr,
                  const RoadRoiPolicy *policy,RoadBox *output,int capacity);
#endif
