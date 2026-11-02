import numpy as np
from evaluate_car_patch_verifier import cohorts
from study_balanced_car_20261030 import raw_helpers
import road_accuracy_common as ac
d=cohorts()['reused320'];h=raw_helpers('reused320',d);r=d['manifest'][0];a=h[r['name']];g=np.asarray(d['base'][r['name']]['detections'],np.float32).reshape(-1,6);g=g[g[:,5]==1]
for mapped in [False,True]:
    p=ac.fuse(a[0],[ac.map_tile(v,*ac.TILES[i]) for i,v in enumerate(a[1:])] if mapped else a[1:],.75);p=p[p[:,5]==1]
    print('MAPPED',mapped,'SHAPES',p.shape,g.shape)
    if p.shape==g.shape:print('MAX',np.max(np.abs(p-g)),'MEAN',np.mean(np.abs(p-g)),'PER_COLUMN',np.max(np.abs(p-g),axis=0))
    print('P',p[:4].tolist(),'G',g[:4].tolist(),'TILE',a[1][:3].tolist())
