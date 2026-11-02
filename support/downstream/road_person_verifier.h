#ifndef ROAD_PERSON_VERIFIER_H
#define ROAD_PERSON_VERIFIER_H
#include <stdint.h>
#include "road_fp32.h"
#define ROAD_PERSON_WEIGHTS 12993U
#define ROAD_PERSON_PATCH_BYTES (24U*48U*3U)
int road_person_crop(const uint8_t *bgr800,const RoadBox *box,uint8_t *rgb_patch);
float road_person_probability(const uint8_t *rgb_patch,const float *weights);
#endif
