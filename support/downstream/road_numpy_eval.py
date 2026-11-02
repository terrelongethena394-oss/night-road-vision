"""NumPy-only detector metrics, matching the frozen YOLOv5 evaluator.

Matching/AP definitions adapted from YOLOv5 GPL-3.0 utils/metrics.py and
val.py; preserve its license when distributing this helper.
"""
import numpy as np
NAMES=['person','car','truck','bus']
def correct(pred,gt,thresholds=None):
    if thresholds is None:thresholds=np.linspace(.5,.95,10,dtype=np.float32)
    p=np.asarray(pred,dtype=np.float32).reshape(-1,6);g=np.asarray(gt,dtype=np.float32).reshape(-1,5)
    result=np.zeros((len(p),len(thresholds)),bool);matched=[]
    if not len(p) or not len(g):return result,[set() for _ in thresholds]
    a=g[:,None,1:];b=p[None,:,:4]
    wh=np.maximum(0,np.minimum(a[:,:,2:],b[:,:,2:])-np.maximum(a[:,:,:2],b[:,:,:2]));inter=wh.prod(2)
    iou=inter/((a[:,:,2:]-a[:,:,:2]).prod(2)+(b[:,:,2:]-b[:,:,:2]).prod(2)-inter+1e-7)
    for j,t in enumerate(thresholds):
        gi,pi=np.where((iou>=t)&(g[:,0:1]==p[None,:,5]))
        if not len(gi):matched.append(set());continue
        m=np.stack([gi,pi,iou[gi,pi]],axis=1)
        if len(m)>1:
            m=m[m[:,2].argsort()[::-1]];m=m[np.unique(m[:,1],return_index=True)[1]];m=m[np.unique(m[:,0],return_index=True)[1]]
        result[m[:,1].astype(int),j]=True;matched.append(set(m[:,0].astype(int)))
    return result,matched
def evaluate(rows):
    ps=[np.asarray(r['detections'],np.float32).reshape(-1,6) for r in rows]
    gs=[np.asarray(r['ground_truth'],np.float32).reshape(-1,5) for r in rows]
    tp=np.concatenate([correct(p,g)[0] for p,g in zip(ps,gs)])
    conf=np.concatenate([p[:,4] for p in ps]);cls=np.concatenate([p[:,5] for p in ps]);target=np.concatenate([g[:,0] for g in gs])
    order=np.argsort(-conf);tp=tp[order];cls=cls[order]
    aps={};classes={}
    for c,name in enumerate(NAMES):
        n=int((target==c).sum());which=cls==c;t=tp[which].cumsum(0);f=(1-tp[which]).cumsum(0);ap=[]
        if n and len(t):
            recall=t/(n+1e-16);precision=t/(t+f)
            for j in range(10):
                mr=np.concatenate(([0.],recall[:,j],[1.]));mp=np.concatenate(([1.],precision[:,j],[0.]));mp=np.maximum.accumulate(mp[::-1])[::-1]
                x=np.linspace(0,1,101);ap.append(float(np.trapezoid(np.interp(x,mr,mp),x)))
        else:ap=[0.]*10
        count=0;num=0
        for p,g in zip(ps,gs):
            op=p[p[:,4]>=.25];ok=correct(op,g,np.array([.5],np.float32))[0][:,0]
            count+=int(((op[:,5]==c)&ok).sum());num+=int((op[:,5]==c).sum())
        classes[name]=dict(objects=n,ap50=ap[0] if n else None,ap50_95=float(np.mean(ap)) if n else None,tp=count,fp=num-count,fn=n-count,precision=count/num if num else 0,recall=count/n if n else None)
        if n:aps[name]=ap
    return dict(images=len(rows),mAP50=float(np.mean([v[0] for v in aps.values()])),mAP50_95=float(np.mean(list(aps.values()))),classes=classes)
def by_time(rows):return dict(all=evaluate(rows),by_time={t:evaluate([r for r in rows if r['timeofday']==t]) for t in ['night','dawn/dusk','daytime']})
