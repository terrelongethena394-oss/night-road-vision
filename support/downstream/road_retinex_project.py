"""Paper-informed, project-written classical Retinex processing.

Reference equations2-12: Upadhyay & Sarawadekar, TCSII2024,
doi:10.1109/TCSII.2024.3361561. This is an independent floating reference,
not the authors' RTL or a bit-exact reproduction of their approximation.
Project variants add dark color smoothing, adaptive exposure and gain limits.
"""
import cv2
import numpy as np
from road_local_enhance_v2 import smoothstep

PRESETS={
 'project_mild':dict(tone_power=.42,max_gain=16.,denoise=.70),
 'project_balanced':dict(tone_power=.34,max_gain=32.,denoise=.90),
 'project_strong':dict(tone_power=.25,max_gain=48.,denoise=.95),
}

def illumination(rgb):
    g=np.max(rgb,axis=2).astype(np.float32)
    coarse=cv2.dilate(g,np.ones((11,11),np.uint8),borderType=cv2.BORDER_REFLECT_101)
    col_min=cv2.erode(coarse,np.ones((11,1),np.uint8),borderType=cv2.BORDER_REFLECT_101)
    pad=np.pad(col_min,((0,0),(5,5)),mode='reflect')
    num=np.zeros_like(g);den=np.zeros_like(g)
    for k in range(11):
        v=pad[:,k:k+g.shape[1]];d=v-g
        w=np.exp(-np.abs(d)/32.)*(d>=0) # paper sigma4, ABS difference, not squared
        num+=v*w;den+=w
    # Float rounding safety and explicit all-black handling are implementation
    # details; reference hardware's fixed-point rounding is not specified here.
    f=np.maximum(np.divide(num,den,out=g.copy(),where=den>1e-10),g)
    return np.clip(f/255,0,1)

def paper_reference(rgb):
    assert rgb.dtype==np.uint8 and rgb.shape==(240,400,3)
    f=illumination(rgb);modified=np.sqrt(f*(2-f))
    gain=np.divide(modified,f,out=np.ones_like(f),where=f>1e-8)
    z=np.floor(np.clip(rgb.astype(np.float32)*gain[:,:,None],0,255)+.5).astype(np.uint8)
    return z,dict(reference='equations2-12 floating,11x11,sigma4,mirror reflect101, no piecewise arithmetic approximation',max_gain=float(gain.max()))

def enhance(rgb,preset='project_balanced'):
    assert rgb.dtype==np.uint8 and rgb.shape==(240,400,3)
    p=PRESETS[preset] if isinstance(preset,str) else preset
    a=rgb.astype(np.float32);y=(54*a[:,:,0]+183*a[:,:,1]+19*a[:,:,2])/256;v=a.max(2)/255
    low=cv2.blur(y,(3,3),borderType=cv2.BORDER_REPLICATE)
    grad=np.abs(cv2.Sobel(y,cv2.CV_32F,1,0,ksize=3))+np.abs(cv2.Sobel(y,cv2.CV_32F,0,1,ksize=3))
    flat=(y<80)&(grad<40);noise=float(np.median(np.abs(y-low)[flat])) if flat.sum()>100 else 2.
    sigma=float(np.clip(5+2*noise,7,16))
    # Project implementation: 5x5 edge-aware luminance/RGB filtering, then
    # 9x9 dark chroma smoothing; high-gradient/bright color is protected.
    pad=np.pad(a,((2,2),(2,2),(0,0)),mode='edge');yp=np.pad(y,((2,2),(2,2)),mode='edge')
    num=np.zeros_like(a);den=np.zeros_like(y)
    for dy in range(5):
        for dx in range(5):
            delta=yp[dy:dy+240,dx:dx+400]-y
            w=np.exp(-(delta*delta)/(2*sigma*sigma))*np.exp(-((dy-2)**2+(dx-2)**2)/4.5)
            num+=pad[dy:dy+240,dx:dx+400]*w[:,:,None];den+=w
    shadow=(1-smoothstep(.08,.45,v))*p['denoise']
    base=a+(num/den[:,:,None]-a)*shadow[:,:,None]
    by=(54*base[:,:,0]+183*base[:,:,1]+19*base[:,:,2])/256
    chroma=base-by[:,:,None];smooth=cv2.GaussianBlur(chroma,(9,9),2.,borderType=cv2.BORDER_REPLICATE)
    mix=shadow*(1-smoothstep(30,100,grad));chroma+=(smooth-chroma)*mix[:,:,None]
    chroma*=1-mix[:,:,None]*.4*(1-smoothstep(4,24,by))[:,:,None]
    base=np.clip(by[:,:,None]+chroma,0,255)
    f=illumination(base);modified=(f*(2-f))**p['tone_power']
    gain=np.divide(modified,f,out=np.ones_like(f),where=f>1e-8)
    cap=1+(p['max_gain']-1)*by/(by+3*noise+1)
    gain=np.minimum(gain,cap)
    alpha=float(np.clip((110-float(y.mean()))/70,0,1))
    gain=1+(gain-1)*alpha*(1-smoothstep(.65,.98,base.max(2)/255))
    z=np.floor(np.clip(base*gain[:,:,None],0,255)+.5).astype(np.uint8)
    oy=(54*z[:,:,0].astype(np.uint32)+183*z[:,:,1].astype(np.uint32)+19*z[:,:,2].astype(np.uint32)+128)>>8
    return z,dict(mean_in=float(y.mean()),mean_out=float(oy.mean()),noise_proxy=noise,max_gain=float(gain.max()),gain_p95=float(np.percentile(gain,95)),alpha=alpha,clip_fraction=float(np.any(z>=254,axis=2).mean()))
