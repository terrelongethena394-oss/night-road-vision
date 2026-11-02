"""Diagnose fixed-confidence false positives, without modifying predictions."""
from collections import Counter
from pathlib import Path
import numpy as np
from road_enhanced_detection_common import BASE,read,write
from road_numpy_eval import correct
import road_accuracy_common as ac
ROOT=BASE/'road_allview_enhance_20261031_r1'
def iou(a,b):
    if not len(b):return np.zeros(0,np.float32)
    it=np.maximum(0,np.minimum(a[2:],b[:,2:])-np.maximum(a[:2],b[:,:2])).prod(1)
    return it/(np.maximum(0,a[2:]-a[:2]).prod()+np.maximum(0,b[:,2:]-b[:,:2]).prod(1)-it+1e-7)
def main():
    rows=read(ROOT/'development_manifest.json');pred=read(ROOT/'predictions.json');truth={r['name']:ac.truth(Path(r['data_root'])/'labels'/(Path(r['name']).stem+'.txt')) for r in rows}
    results={}
    for mode in ['raw','gamma080','abi29mix10']:
        counts=Counter();tp_size=Counter();conf=Counter()
        for r in pred[mode]:
            g=truth[r['name']];p=np.array(r['detections'],np.float32).reshape(-1,6);p=p[(p[:,4]>=.25)&(p[:,5]==1)];car=g[g[:,0]==1]
            ok=correct(p,car,np.array([.5],np.float32))[0][:,0]
            for b,yes in zip(p,ok):
                size='tiny_h_lt8' if b[3]-b[1]<8 else 'small_h_lt20' if b[3]-b[1]<20 else 'larger'
                if yes:tp_size[size]+=1;continue
                ci=iou(b[:4],car[:,1:]);ni=iou(b[:4],g[g[:,0]!=1,1:]);cm=float(ci.max(initial=0));nm=float(ni.max(initial=0))
                kind='duplicate_iou_ge50' if cm>=.5 else 'car_localization_iou10_to50' if cm>=.1 else 'other_class_iou_ge30' if nm>=.3 else 'background_iou_lt10'
                counts[kind]+=1;conf[size]+=1
        results[mode]=dict(false_positive_categories=dict(counts),false_positive_total=sum(counts.values()),false_positive_sizes=dict(conf),true_positive_sizes=dict(tp_size))
    out=dict(status='DIAGNOSTIC_ONLY_NOT_GATES_OR_LABEL_CORRECTION',definition='Fixed confidence.25 and original IoU.5 matching. FP category uses maximum annotation IoU, car first then other class. No predictions or labels changed.',results=results)
    write(ROOT/'error_analysis.json',out);print(out)
if __name__=='__main__':main()
