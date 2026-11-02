#ifndef ROAD_PATCH_VERIFIER_H
#define ROAD_PATCH_VERIFIER_H
#include <stdint.h>
#define ROAD_PATCH_WEIGHT_FLOATS 17417U
#define ROAD_PATCH_WORK_FLOATS 6560U
int road_patch_features(const uint8_t *bgr800,const float *box400,uint8_t *rgb32,float metadata[6]);
float road_patch_logit(const float *weights,const uint8_t *rgb32,const float metadata[6],float *work);
float road_patch_probability(const float *weights,const uint8_t *rgb32,const float metadata[6],float *work);
#endif
