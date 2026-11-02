import time
from pathlib import Path
from road_enhanced_detection_common import BASE,read
import road_accuracy_common as ac
from study_allview_enhancement_20261031 import finish
from prove_balanced_car_c import RefinerC
from allview_enhance_native import Post
def main():
    import importlib.util
    if importlib.util.find_spec('psutil'):
        import psutil
        for p in psutil.process_iter(['pid','name','cmdline']):
            c=p.info.get('cmdline') or []
            if any('evaluate_allview_gamma_20261031.py' in s for s in c):print('EVAL_PID',p.info['pid'],c)
    root=BASE/'road_allview_enhance_20261031_r1';v=read(root/'view_predictions.json')['raw'][:8];m=read(root/'development_manifest.json')[:8];params=read(BASE/'road_car_balanced_20261030_r1/selected.json')['chosen']['source'];r=RefinerC();post=Post();sensors=[ac.sensor400(Path(a['data_root'])/'images'/a['name'])[0] for a in m]
    start=time.monotonic();a=[finish(z['detections'],s,params,r) for z,s in zip(v,sensors)];t=time.monotonic()-start
    start=time.monotonic();b=[post.run(z['detections'],s)[0] for z,s in zip(v,sensors)];u=time.monotonic()-start
    import numpy as np
    for x,y in zip(a,b):assert x.shape==y.shape and np.max(np.abs(x-y),initial=0)<=.0001
    print('POST_PROFILE',dict(cases=8,numpy_seconds=t,C_seconds=u,ratio=t/u))
if __name__=='__main__':main()
