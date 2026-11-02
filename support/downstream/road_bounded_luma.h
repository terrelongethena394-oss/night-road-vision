#ifndef ROAD_BOUNDED_LUMA_H
#define ROAD_BOUNDED_LUMA_H
#include <stdint.h>
/* Parameters: strength0..256, cap0..64, threshold1..255. No ground truth input. */
static void road_bounded_luma(const uint8_t *raw,const uint8_t *net,uint8_t *out,
                             uint32_t pixels,unsigned strength,unsigned cap,unsigned threshold) {
    const unsigned denominator=256u*threshold;
    for(uint32_t i=0;i<pixels;i++) {
        const unsigned j=3u*i;
        int y0=(54*raw[j]+183*raw[j+1]+19*raw[j+2]+128)>>8;
        int y1=(54*net[j]+183*net[j+1]+19*net[j+2]+128)>>8;
        int delta=y1-y0;if(delta<0)delta=0;if(delta>(int)cap)delta=(int)cap;
        int mask=(int)threshold-y0;if(mask<0)mask=0;
        unsigned add=((unsigned)delta*strength*(unsigned)mask+denominator/2u)/denominator;
        for(unsigned c=0;c<3;c++) { unsigned v=raw[j+c]+add;out[j+c]=(uint8_t)(v>255u?255u:v); }
    }
}
#endif
