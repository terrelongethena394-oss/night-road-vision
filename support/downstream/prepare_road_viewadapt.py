"""Project only original training images into the actual deployment views."""
import concurrent.futures as cf,collections,hashlib,shutil,time
import cv2,numpy as np
from road_viewadapt_common import *

def labels_for_view(gt,x,y,w,h):
 g=np.asarray(gt,np.float32).reshape(-1,5).copy()
 g[:,[1,3]]-=x;g[:,[2,4]]-=y
 g[:,[1,3]]=np.clip(g[:,[1,3]],0,w);g[:,[2,4]]=np.clip(g[:,[2,4]],0,h)
 g=g[(g[:,3]-g[:,1]>=2)&(g[:,4]-g[:,2]>=2)]
 # Same integer 400x240 -> 320x192 resize plus top64 gray padding.
 out=np.empty((len(g),5),np.float32);out[:,0]=g[:,0]
 out[:,1]=(g[:,1]+g[:,3])*.4/320;out[:,2]=((g[:,2]+g[:,4])*.4+64)/320
 out[:,3]=(g[:,3]-g[:,1])*.8/320;out[:,4]=(g[:,4]-g[:,2])*.8/320
 return out

def main():
 assert not ROOT.exists();ROOT.mkdir();(ROOT/'source').mkdir()
 source=Path(__file__).resolve().parent
 for n in ['road_viewadapt_common.py','prepare_road_viewadapt.py','train_road_viewadapt.py','evaluate_road_viewadapt.py']:
  if (source/n).exists():shutil.copy2(source/n,ROOT/'source'/n)
 assert sha(WEIGHTS)=='98f46429cd431d735e276d7735f50f61811a70cbb5feb2a0475fba562449a46f'
 assert read(BASE/'road_overlap_20261030_r1/development_result.json')['qualified'] is False
 manifest=read(DATA/'dataset/manifest.json');train=[r for r in manifest if r['split']=='train' and r['status']=='READY'];assert len(train)==2400
 held=[r for r in manifest if r['split']!='train'];assert not {r['group'] for r in train}&{r['group'] for r in held}
 protocol=dict(status='FROZEN_BEFORE_PREPARATION_AND_GRADIENTS',seed=SEED,architecture='Unchanged YOLOv5n four classes, original anchors and all graph dimensions; actual neural weights will change.',initial_weights_sha256=sha(WEIGHTS),training='Original2400 train images only. Exact RGB800x480 sensor proxy, rounded2x2 mean400x240 and three raw400x240 crops. All views use exact integer320x192 resize and gray114 top/bottom64. Each epoch visits every source image once for full and once for a rotating crop. Batch16, FP32, AdamW lr3e-5 cosine to5e-6, accumulation2, freeze BN buffers and anchors, EMA checkpoints2/4/6 of6. Horizontal flip only, no enhancement or synthetic darkening.',labels='Original annotated labels mapped to proxy; ROI boxes clipped to viewport, keep visible width/height>=2 sensor pixels. No pseudolabels. Raw scene content only.',checkpoints=CHECKPOINTS,development='Reused original320 and reused low320. Select checkpoint maximizing mean fourclass mAP50 among candidates passing gates. No fresh301 or unseen holdout used for checkpoint selection.',development_gates=dict(car_ap_each_cohort_gain_at_least=.005,car_ap_each_present_period_drop_max=.005,car_precision_drop_max=.005,car_recall_drop_max=.005,fourclass_map_drop_max=.002,truck_bus_tp_retained=.9,truck_bus_fp_retained=.9),fresh_policy='Only after development qualification, freeze checkpoint and evaluate unused prefix groups/images excluded from all prior training, evaluation and brightness screening. At least160 raw meanY<=48 night-labelled and64 meanY>=70 day-labelled. Same accuracy gates per cohort, 99% paired-image CI on car AP gain lower>0. No test-driven reselection. If unavailable or rejected retain ABI24.',source_manifest_sha256=sha(DATA/'dataset/manifest.json'),hardware_access=False,sd_written=False)
 write(ROOT/'protocol.json',protocol)
 for view in range(4):(ROOT/'prepared'/f'view{view}').mkdir(parents=True)
 begin=time.monotonic()
 def item(r):
  ip=DATA/'dataset/images/train'/r['name'];lp=DATA/'dataset/labels/train'/(Path(r['name']).stem+'.txt')
  assert sha(ip)==r['image_sha256'] and sha(lp)==r['label_sha256']
  sensor,full=sensor400(ip);gt=truth(lp);g800=gt.copy();g800[:,1:]*=2
  views=[full]+[sensor[y:y+240,x:x+400] for x,y in TILES]
  labels=[labels_for_view(gt,0,0,400,240)]+[labels_for_view(g800,x,y,400,240) for x,y in TILES]
  records=[]
  for i,(im,g) in enumerate(zip(views,labels)):
   a=preprocess400(im);p=ROOT/'prepared'/f'view{i}'/(Path(r['name']).stem+'.png');assert cv2.imwrite(str(p),a[:,:,::-1],[cv2.IMWRITE_PNG_COMPRESSION,1])
   assert np.array_equal(cv2.imread(str(p))[:,:,::-1],a)
   records.append(dict(view=i,image=str(p),image_sha256=sha(p),labels=g.tolist()))
  return dict(name=r['name'],group=r['group'],timeofday=r['timeofday'],split='train',image_sha256=r['image_sha256'],views=records)
 rows=[]
 with cf.ThreadPoolExecutor(4) as pool:
  for i,r in enumerate(pool.map(item,train),1):
   rows.append(r)
   if i%300==0:print('VIEWADAPT_PREPARED',i,len(train),round(time.monotonic()-begin),flush=True)
 write(ROOT/'training_manifest.json',rows);write(ROOT/'prepared.json',dict(status='ORIGINAL2400_TRAIN_ONLY_EXACT_BOARD_FOUR_VIEWS_READY',images=len(rows),views=4*len(rows),manifest_sha256=sha(ROOT/'training_manifest.json'),seconds=time.monotonic()-begin,periods=dict(collections.Counter(r['timeofday'] for r in rows)),hardware_access=False))
 print('VIEWADAPT_DATA_READY',flush=True)

if __name__=='__main__':main()

