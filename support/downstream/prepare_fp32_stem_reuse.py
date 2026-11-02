"""Exact stem row reuse: compare full input windows before copying a result row."""
import prepare_fp32_cpu_pack as common
BASE=common.BASE
ROOT=BASE/'road_fp32_stem_reuse_20261028_r4'

def patch(c):
    service='road_poll_service()' if 'road_pl_try(' in c else '((void)0)'
    if service=='((void)0)':
        c=c.replace('for(y=0;y<out->h;y++)for(x=0;x<out->w;){','for(y=0;y<out->h;y++){for(x=0;x<out->w;){',1)
        c=c.replace('    x+=tile;\n  }\n}', '    x+=tile;\n  }\n  }\n}',1)
    code='''
static int cpu_mode=1;
void road_cpu_set_mode(int mode){cpu_mode=mode;}
'''
    c=c.replace('#include "road_fp32.h"','#include "road_fp32.h"\n#include "road_cpu_pack.h"',1)
    c=c.replace('static void conv(',code+'\nstatic void conv(',1)
    needle='for(y=0;y<out->h;y++){for(x=0;x<out->w;){'
    replacement='''for(y=0;y<out->h;y++){
    /* Exact equality of complete windows implies equal convolution and SiLU.
     * Compare all channels and all six rows; never infer equality from luminance.
     * Boundary rows with spatial padding still use the original computation. */
    if(cpu_mode && op->k==6 && op->s==2 && op->p==2 && y>0){
      int iy=y*op->s-op->p;
      if(iy>=op->s && iy+op->k<=in->h &&
         memcmp(a+iy*in->w*in->c4,a+(iy-op->s)*in->w*in->c4,
                (size_t)op->k*in->w*in->c4*sizeof(float))==0){
        memcpy(b+y*out->w*out->c4,b+(y-1)*out->w*out->c4,
               (size_t)out->w*out->c4*sizeof(float));
        SERVICE();continue;
      }
    }
    for(x=0;x<out->w;){'''.replace('SERVICE()',service)
    assert c.count(needle)==1
    return c.replace(needle,replacement,1)

def main():
    common.ROOT=ROOT;common.patch=patch;common.main()
    p=common.read(ROOT/'protocol.json')
    p.update(arithmetic='Original ordered FP32 MACs. Reuse preceding stem result row only after byte-exact comparison of complete six-row input windows. No arithmetic skipped when windows differ.',layers=[1],packed_bytes=0,packed_floats=0,packed_addr=None,reason='Earlier pointwise candidates were slower. Stem dominates CPU time; repeated letterbox windows have exactly equal outputs. No change to weights, resize, detector input or activation.')
    common.write(ROOT/'protocol.json',p)
    common.write(ROOT/'prepared.json',dict(status='STEM_REUSE_SOURCE_READY',packed_bytes=0,source_sha256=common.sha(ROOT/'firmware/source/road_fp32.c')))
    import check_build_fp32_cpu_pack as run
    run.ROOT=ROOT;run.main()

if __name__=='__main__':main()
