#include "road_retinex_c.h"
#include "road_shadowlift.h"
int road_retinex_base(const uint32_t *,uint32_t *,unsigned,float *,RoadRetinexStats *,void (*)(void *),void *);
int road_retinex_c(const uint32_t *raw,uint32_t *out,unsigned n,float *work,RoadRetinexStats *s,void (*cb)(void *),void *opaque){
 RoadShadowStats extra;int e=road_retinex_base(raw,out,n,work,s,cb,opaque);if(e)return e;
 e=road_shadowlift(raw,out,n,work,&extra,cb,opaque);if(e)return e;
 s->mean_out=extra.mean_out;s->max_gain=extra.max_total_gain;return 0;
}
