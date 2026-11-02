"""Static-photo road enhancement with full RGB888 and dark chroma smoothing.

Own implementation using classical operators; no enhancement model weights.
"""
import cv2
import numpy as np

PRESETS={
 'local_mild':dict(gamma=.50,max_gain=6.,denoise=.50),
 'local_balanced':dict(gamma=.42,max_gain=8.,denoise=.75),
 'local_strong':dict(gamma=.34,max_gain=12.,denoise=.90),
}
def smoothstep(a,b,x):
    t=np.clip((x-a)/(b-a),0,1)
    return t*t*(3-2*t)
def enhance(rgb,preset='local_balanced'):
    assert rgb.shape==(240,400,3) and rgb.dtype==np.uint8
    p=PRESETS[preset] if isinstance(preset,str) else preset
    a=rgb.astype(np.float32)
    yu=((54*rgb[:,:,0].astype(np.uint32)+183*rgb[:,:,1].astype(np.uint32)+19*rgb[:,:,2].astype(np.uint32)+128)>>8).astype(np.uint8)
    y=yu.astype(np.float32);v=a.max(2)/255
    lp=cv2.blur(y,(3,3),borderType=cv2.BORDER_REPLICATE)
    grad=np.abs(cv2.Sobel(y,cv2.CV_32F,1,0,ksize=3))+np.abs(cv2.Sobel(y,cv2.CV_32F,0,1,ksize=3))
    flat=(y<80)&(grad<40)
    noise=float(np.median(np.abs(y-lp)[flat])) if flat.sum()>100 else 2.
    sigma=float(np.clip(4+2*noise,6,16))
    lut=np.exp(-(np.arange(256,dtype=np.float32)**2)/(2*sigma*sigma))
    pad=np.pad(a,((1,1),(1,1),(0,0)),mode='edge');yp=np.pad(yu.astype(np.int16),((1,1),(1,1)),mode='edge')
    num=np.zeros_like(a);den=np.zeros_like(y)
    for dy in range(3):
        for dx in range(3):
            diff=np.abs(yp[dy:dy+240,dx:dx+400]-yu.astype(np.int16))
            w=lut[diff]*((2 if dy==1 else 1)*(2 if dx==1 else 1))
            num+=pad[dy:dy+240,dx:dx+400]*w[:,:,None];den+=w
    filtered=num/den[:,:,None]
    shadow=(1-smoothstep(.08,.45,v))*p['denoise']
    base=a+(filtered-a)*shadow[:,:,None]
    by=(54*base[:,:,0]+183*base[:,:,1]+19*base[:,:,2])/256
    chroma=base-by[:,:,None]
    cs=cv2.GaussianBlur(chroma,(7,7),1.5,borderType=cv2.BORDER_REPLICATE)
    # Bright edges keep color detail. Very dark regions prefer spatially
    # coherent color, reducing amplification of JPEG/sensor chroma fluctuations.
    mix=shadow*(1-smoothstep(30,100,grad))
    chroma=chroma+(cs-chroma)*mix[:,:,None]
    confidence=1-mix*.35*(1-smoothstep(4,24,by))
    base=np.maximum(0,by[:,:,None]+chroma*confidence[:,:,None])
    value=base.max(2)/255
    cells=value.reshape(15,16,25,16).mean((1,3))
    s=cv2.GaussianBlur(cells,(5,5),1.,borderType=cv2.BORDER_REPLICATE)
    l=cv2.GaussianBlur(cells,(9,9),3.,borderType=cv2.BORDER_REPLICATE)
    illum=np.maximum(cv2.resize(.65*s+.35*l,(400,240),interpolation=cv2.INTER_LINEAR),value)
    confidence_cap=1+(p['max_gain']-1)*by/(by+3*noise+2)
    local_gain=np.minimum(np.maximum(illum,1/255)**(p['gamma']-1),confidence_cap)
    alpha=float(np.clip((110-float(y.mean()))/70,0,1))
    gain=1+(local_gain-1)*(1-smoothstep(.65,.98,value))*alpha
    z=np.floor(np.clip(base*gain[:,:,None],0,255)+.5).astype(np.uint8)
    oy=(54*z[:,:,0].astype(np.uint32)+183*z[:,:,1].astype(np.uint32)+19*z[:,:,2].astype(np.uint32)+128)>>8
    return z,dict(mean_in=float(y.mean()),mean_out=float(oy.mean()),alpha=alpha,noise_proxy=noise,range_sigma=sigma,max_gain=float(gain.max()),gain_p95=float(np.percentile(gain,95)),clipped_fraction=float(np.any(z>=254,axis=2).mean()))

def gamma_baseline(rgb,gamma):
    """Uncapped global Gamma control, tuned on same paired validation only."""
    lut=np.floor((np.arange(256)/255)**gamma*255+.5).astype(np.uint8)
    return lut[rgb]
