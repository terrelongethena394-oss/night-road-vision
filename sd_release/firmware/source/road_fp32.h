/* YOLOv5n FP32 inference prototype. GPL-3.0; see YOLOv5_LICENSE.
 * This header declares real implemented operators, not a hardware IP wrapper. */
#ifndef ROAD_FP32_H
#define ROAD_FP32_H
#include <stdint.h>
#include "road_graph.h"
typedef void (*RoadTrace)(int,const float *,uint32_t,void *);
typedef struct {float x1,y1,x2,y2,score;int cls,order;} RoadBox;
void road_preprocess400(const uint32_t *rgb400,uint8_t *rgb320);
void road_input320(const uint8_t *rgb320,float *arena);
int road_forward(const float *weights,float *arena,RoadTrace trace,void *opaque);
void road_decode(const float *arena,float *decoded);
int road_nms(const float *decoded,RoadBox *candidates,RoadBox *output,int max_output,float confidence,float iou);
void road_boxes_to400(RoadBox *boxes,int count);
#endif
