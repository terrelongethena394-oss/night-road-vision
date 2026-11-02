"""Independent NumPy fixed-point complete-plate reference and BN folding."""
import numpy as np
import torch
from plate_common import CHARS
ACT_BITS=10
ACT_MAX=6*(1<<ACT_BITS)
def round_away(x):return (np.sign(x)*np.floor(np.abs(x)+.5)).astype(np.int64)
def rshift(x,n):return np.sign(x)*((np.abs(x)+(1<<(n-1)))>>n)
def normalized_np(gray):
    a=np.asarray(gray,np.uint8).reshape(-1,3072);p=np.partition(a,(153,2918),axis=1)
    lo=p[:,153].astype(np.int32);hi=p[:,2918].astype(np.int32);span=np.maximum(hi-lo,16)[:,None];center=((lo+hi+1)//2)[:,None]
    d=a.astype(np.int32)-center;q=(np.abs(d)*192+span//2)//span
    b=np.clip(128+np.where(d<0,-q,q),0,255)
    return ((2*b-255)*4).astype(np.int16).reshape(-1,1,32,96)
def layer_definitions():
    return [('stem','stem_bn',1,16,3,3,2,2,1,1,1),('b1.dw','b1.dw_bn',16,16,3,3,2,2,1,1,16),('b1.pw','b1.pw_bn',16,32,1,1,1,1,0,0,1),('b2.dw','b2.dw_bn',32,32,3,3,2,1,1,1,32),('b2.pw','b2.pw_bn',32,64,1,1,1,1,0,0,1),('b3.dw','b3.dw_bn',64,64,3,3,2,1,1,1,64),('b3.pw','b3.pw_bn',64,96,1,1,1,1,0,0,1),('temporal','temporal_bn',192,128,1,3,1,1,0,1,1),('head',None,128,len(CHARS),1,1,1,1,0,0,1)]
def fold_state(state):
    layers=[];hin,win=32,96
    for name,bn,ci,co,kh,kw,sh,sw,ph,pw,groups in layer_definitions():
        w=state[name+'.weight'].detach().cpu().double().numpy()
        if w.ndim==3:w=w[:,:,None,:]
        b=state[name+'.bias'].detach().cpu().double().numpy() if name+'.bias' in state else np.zeros(co)
        if bn:
            gamma=state[bn+'.weight'].detach().cpu().double().numpy();beta=state[bn+'.bias'].detach().cpu().double().numpy();mean=state[bn+'.running_mean'].detach().cpu().double().numpy();var=state[bn+'.running_var'].detach().cpu().double().numpy()
            scale=gamma/np.sqrt(var+1e-5);w=w*scale[:,None,None,None];b=beta+(b-mean)*scale
        if name=='temporal':hin,win=1,24
        ho=(hin+2*ph-kh)//sh+1;wo=(win+2*pw-kw)//sw+1
        frac=12;maxinput=1020 if name=='stem' else ACT_MAX
        while True:
            qw=round_away(w*(1<<frac));qb=round_away(b*(1<<(ACT_BITS+frac)))
            bound=np.abs(qb)+np.abs(qw).sum((1,2,3))*maxinput
            if np.abs(qw).max()<=32767 and np.abs(qb).max()<2**31 and bound.max()<2**31:break
            frac-=1;assert frac>=4,(name,'insufficient precision')
        layers.append(dict(name=name,cin=ci,cout=co,hi=hin,wi=win,ho=ho,wo=wo,kh=kh,kw=kw,sh=sh,sw=sw,ph=ph,pw=pw,groups=groups,frac=frac,activation=bn is not None,w=qw,b=qb,absolute_partial_sum_bound=int(bound.max())))
        hin,win=ho,wo
    return layers
class IntegerPlate:
    def __init__(self,state):self.layers=fold_state(state)
    def infer(self,gray):
        x=normalized_np(gray).astype(np.int64)
        for d in self.layers:
            x=x.reshape(len(x),d['cin'],d['hi'],d['wi'])
            p=np.pad(x,((0,0),(0,0),(d['ph'],d['ph']),(d['pw'],d['pw'])))
            windows=np.lib.stride_tricks.sliding_window_view(p,(d['kh'],d['kw']),axis=(2,3))[:,:,::d['sh'],::d['sw']]
            if d['groups']==1:z=np.einsum('nchwkl,ockl->nohw',windows,d['w'],optimize=True)
            else:z=np.einsum('nchwkl,ckl->nchw',windows,d['w'][:,0],optimize=True)
            z+=d['b'][None,:,None,None]
            assert np.abs(z).max()<2**31
            x=np.clip(rshift(z,d['frac']),0,ACT_MAX) if d['activation'] else z
        return x.reshape(len(x),len(CHARS),24)
