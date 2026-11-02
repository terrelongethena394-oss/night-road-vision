#include <stdint.h>
#define ROAD_REFINER_WEIGHT_FLOATS 17549U
#define ROAD_REFINER_WORK_FLOATS 6560U
int road_patch_features(const uint8_t *,const float *,uint8_t *,float *);
int road_box_refiner(const float *,const uint8_t *,const float *,float *,float *);
