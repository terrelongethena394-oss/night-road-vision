"""Specialized RGB stem with exact repeated-window reuse; model padding is zero."""
import numpy as np
import prepare_fp32_cpu_pack as common
from prepare_fp32_stem_reuse import patch as reuse_patch
BASE=common.BASE
ROOT=BASE/'road_fp32_stem_rgb_20261028_r5'

def patch(c):
    original=c[c.index('static void conv('):c.index('int road_forward(')]
    reused=reuse_patch(c)
    kernel=reused[reused.index('static void conv('):reused.index('int road_forward(')]
    kernel=kernel.replace('static void conv(','static __attribute__((noinline)) void conv_stem_rgb(',1)
    for src,dst in [('out->c4','16'),('out->h','160'),('out->w','160'),('out->c','16'),('in->c4','4'),('in->h','320'),('in->w','320'),('op->k','6'),('op->s','2'),('op->p','2')]:
        kernel=kernel.replace(src,dst)
    assert kernel.count('ic<4')==2
    kernel=kernel.replace('ic<4','ic<3')
    kernel=kernel.replace('if(op->act)','if(1)')
    c=c.replace('#include "road_fp32.h"','#include "road_fp32.h"\n#include "road_cpu_pack.h"',1)
    c=c.replace(original,'static int cpu_mode=1;\nvoid road_cpu_set_mode(int mode){cpu_mode=mode;}\n'+kernel+original,1)
    if 'if(op->kind==1){int offloaded=' in c:
        c=c.replace('if(op->kind==1){int offloaded=','if(i==1&&cpu_mode)conv_stem_rgb(op,in,out,a,weights,b);\n    else if(op->kind==1){int offloaded=',1)
    else:
        c=c.replace('if(op->kind==1)conv(op,in,out,a,weights,b);','if(i==1&&cpu_mode)conv_stem_rgb(op,in,out,a,weights,b);\n    else if(op->kind==1)conv(op,in,out,a,weights,b);',1)
    # Fixed dimensions leave these signature parameters unused in this helper.
    c=c.replace('void conv_stem_rgb(const RoadOp *op,const RoadTensor *in,const RoadTensor *out,const float *a,const float *weights,float *b){','void conv_stem_rgb(const RoadOp *op,const RoadTensor *in,const RoadTensor *out,const float *a,const float *weights,float *b){\n  (void)in;(void)out;',1)
    return c

def main():
    g=common.read(common.NN/'graph.json');t=g['tensors'][1];i=g['tensors'][0]
    assert t['k']==6 and t['s']==2 and t['p']==2 and (t['h'],t['w'],t['c4'])==(160,160,16)
    assert (i['h'],i['w'],i['c4'])==(320,320,4)
    w=np.fromfile(common.CURRENT/'runtime/weights.f32','<f4')
    # road_input320 explicitly writes input channel3 to +0. Padding weights
    # are +0. Nonzero finite biases avoid introducing a -0 accumulator.
    wo=t['woff'];bo=t['boff']
    assert wo is not None and bo is not None,(t.keys())
    assert np.all(w[wo:wo+6*6*4*16].reshape(6,6,4,16)[:,:,3,:].view('<u4')==0)
    assert np.isfinite(w).all() and np.all(w[bo:bo+16]!=0)
    common.ROOT=ROOT;common.patch=patch;common.main()
    p=common.read(ROOT/'protocol.json')
    p.update(arithmetic='Specialize fixed first6x6 RGB convolution; retain ky,kx,RGB reduction order, omit only known +0 padded channel. Exact full-window row reuse as R4; all other layers unchanged.',layers=[1],packed_bytes=0,packed_floats=0,packed_addr=None,reason='First stem row reuse reduces measured stem time but whole-network timing remains noisy. This variant also specializes dimensions and eliminates verified zero padding MACs.',scope='Only frozen weights, road_input320 positive-zero channel3, finite nonzero stem biases. Host and same-ARM86-layer identity required.')
    common.write(ROOT/'protocol.json',p)
    common.write(ROOT/'prepared.json',dict(status='STEM_RGB_SOURCE_READY',packed_bytes=0,source_sha256=common.sha(ROOT/'firmware/source/road_fp32.c')))
    import check_build_fp32_cpu_pack as run
    run.ROOT=ROOT;run.main()

if __name__=='__main__':main()
