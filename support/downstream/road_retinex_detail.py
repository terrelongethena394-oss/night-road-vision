"""Texture-preserving revision: spatial smoothing never touches luminance.

Retinex illumination is estimated separately. A small nonlocal patch filter
acts only on two chrominance channels; original luminance/geometry is retained.
No learned enhancement weights. Established Retinex/NLM principles, own code.
"""
import cv2
import numpy as np
from road_retinex_project import illumination
from road_local_enhance_v2 import smoothstep
PRESETS={
 'detail_mild':dict(tone=.42,max_gain=4.,h=4.,chroma_mix=.40),
 'detail_balanced':dict(tone=.38,max_gain=5.,h=6.,chroma_mix=.60),
 'detail_strong':dict(tone=.34,max_gain=6.,h=8.,chroma_mix=.80),
}
def enhance(rgb,preset='detail_balanced'):
    assert rgb.shape==(240,400,3) and rgb.dtype==np.uint8
    p=PRESETS[preset] if isinstance(preset,str) else preset
    a=rgb.astype(np.float32);value=a.max(2)/255
    raw_y=(54*a[:,:,0]+183*a[:,:,1]+19*a[:,:,2])/256
    f=illumination(a);target=(f*(2-f))**p['tone']
    gain=np.divide(target,f,out=np.ones_like(f),where=f>1e-8)
    gain=np.minimum(gain,p['max_gain'])
    alpha=float(np.clip((110-float(raw_y.mean()))/70,0,1))
    gain=1+(gain-1)*alpha*(1-smoothstep(.65,.98,value))
    lit=np.clip(a*gain[:,:,None],0,255)
    # YCoCg is invertible in float and keeps luminance outside the filter.
    y=(lit[:,:,0]+2*lit[:,:,1]+lit[:,:,2])*.25
    co=(lit[:,:,0]-lit[:,:,2])*.5
    cg=(-lit[:,:,0]+2*lit[:,:,1]-lit[:,:,2])*.25
    planes=np.stack([y,co,cg],2)
    pad=np.pad(planes,((3,3),(3,3),(0,0)),mode='reflect')
    num_co=np.zeros_like(y);num_cg=np.zeros_like(y);den=np.zeros_like(y)
    # Search7x7, patch3x3. Patch matching makes smoothing less dependent on
    # whether a single pixel has a large gradient; no detector boxes are used.
    for dy in range(7):
        for dx in range(7):
            shifted=pad[dy:dy+240,dx:dx+400]
            delta=shifted-planes
            distance=(delta[:,:,0]**2*.25+delta[:,:,1]**2+delta[:,:,2]**2)/2.25
            distance=cv2.boxFilter(distance,cv2.CV_32F,(3,3),normalize=True,borderType=cv2.BORDER_REFLECT_101)
            weight=np.exp(-np.maximum(distance-18.,0)/(p['h']**2))
            num_co+=shifted[:,:,1]*weight;num_cg+=shifted[:,:,2]*weight;den+=weight
    mix=p['chroma_mix']*(1-smoothstep(.10,.65,value))
    co+=(num_co/den-co)*mix;cg+=(num_cg/den-cg)*mix
    result=np.stack([y+co-cg,y+cg,y-co-cg],2)
    reconstructed_y=(result[:,:,0]+2*result[:,:,1]+result[:,:,2])*.25
    error=float(np.max(np.abs(reconstructed_y-y)))
    out=np.floor(np.clip(result,0,255)+.5).astype(np.uint8)
    out_y=(54*out[:,:,0].astype(np.float32)+183*out[:,:,1].astype(np.float32)+19*out[:,:,2].astype(np.float32))/256
    return out,dict(mean_in=float(raw_y.mean()),mean_out=float(out_y.mean()),gain_max=float(gain.max()),gain_mean=float(gain.mean()),alpha=alpha,luminance_filter='none',luminance_reconstruction_max_float_error=error,clipping_fraction=float(np.any(out>=254,axis=2).mean()))
