"""Project-written road enhancement, no pretrained enhancement weights.

Classical local illumination compensation with edge-aware dark-region smoothing.
The principles are established image processing, not a claimed new neural model.
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
    y=(54*a[:,:,0]+183*a[:,:,1]+19*a[:,:,2])/256
    v=a.max(2)/255
    # Estimate residual variation in dark, relatively flat areas. This is a
    # noise proxy, not calibrated sensor-noise variance or a lux measurement.
    lp=cv2.blur(y,(3,3),borderType=cv2.BORDER_REPLICATE)
    grad=np.abs(cv2.Sobel(y,cv2.CV_32F,1,0,ksize=3))+np.abs(cv2.Sobel(y,cv2.CV_32F,0,1,ksize=3))
    flat=(y<80)&(grad<40)
    noise=float(np.median(np.abs(y-lp)[flat])) if flat.sum()>100 else 2.
    sigma=float(np.clip(4.+2.*noise,6.,16.))
    # Explicit 3x3 bilateral weights shared by RGB, avoiding independent
    # channel tone curves. Border replication is part of the specification.
    pad=np.pad(a,((1,1),(1,1),(0,0)),mode='edge')
    yp=np.pad(y,((1,1),(1,1)),mode='edge')
    num=np.zeros_like(a);den=np.zeros_like(y)
    for dy in range(3):
        for dx in range(3):
            diff=yp[dy:dy+240,dx:dx+400]-y
            spatial=(2 if dy==1 else 1)*(2 if dx==1 else 1)
            w=np.exp(-(diff*diff)/(2*sigma*sigma))*spatial
            num+=pad[dy:dy+240,dx:dx+400]*w[:,:,None];den+=w
    filtered=num/den[:,:,None]
    shadow=(1-smoothstep(.08,.45,v))*p['denoise']
    base=a+(filtered-a)*shadow[:,:,None]
    value=base.max(2)/255
    # 25x15 illumination map: each cell represents a 16x16 pixel block.
    # Two fixed spatial scales, then pixel-local upper bound protects edges
    # and prevents the output of an isolated bright pixel exceeding its range.
    cells=value.reshape(15,16,25,16).mean((1,3))
    s=cv2.GaussianBlur(cells,(5,5),1.,borderType=cv2.BORDER_REPLICATE)
    l=cv2.GaussianBlur(cells,(9,9),3.,borderType=cv2.BORDER_REPLICATE)
    illum=cv2.resize(.65*s+.35*l,(400,240),interpolation=cv2.INTER_LINEAR)
    illum=np.maximum(illum,value)
    local_gain=np.minimum(np.maximum(illum,1/255)**(p['gamma']-1),p['max_gain'])
    # Bright frames bypass smoothly; local highlight protection is separate
    # so headlights and signs are not simply multiplied by the shadow gain.
    mean=float(y.mean());alpha=float(np.clip((110-mean)/70,0,1))
    protect=1-smoothstep(.65,.98,value)
    gain=1+(local_gain-1)*protect*alpha
    z=np.floor(np.clip(base*gain[:,:,None],0,255)+.5).astype(np.uint8)
    oy=(54*z[:,:,0].astype(np.uint32)+183*z[:,:,1].astype(np.uint32)+19*z[:,:,2].astype(np.uint32)+128)>>8
    return z,dict(mean_in=mean,mean_out=float(oy.mean()),alpha=alpha,noise_proxy=noise,range_sigma=sigma,max_gain=float(gain.max()),gain_p95=float(np.percentile(gain,95)),clipped_fraction=float(np.any(z>=254,axis=2).mean()))
