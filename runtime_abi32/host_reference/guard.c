#define ROAD_NATURAL_IMPLEMENTATION
#include "road_natural_guard.h"
int guard(const uint32_t *a,uint32_t *b,unsigned n){return natural_apply(a,b,n,0,0);}
