"""Only original training frames are enhanced; preserve validation labels/splits."""
import concurrent.futures as cf,collections,shutil,time
import cv2,numpy as np
from PIL import Image
from road_enhanceadapt_common import *
from road_accuracy_common import sensor400,preprocess400
from audit_bright_detector_20261030 import Enhancer,DLL
from shadowlift_lab import mean_y

def main():
 assert not ROOT.exists();ROOT.mkdir();(ROOT/'source').mkdir()
 assert sha(INITIAL)==read(ADAPT/'export/complete.json')['source_checkpoint_sha256']
 assert read(AUDIT/'result.json')['status']=='REJECT_KEEP_RAW_NN_ENHANCED_DISPLAY'
 training=read(ADAPT/'training_manifest.json');assert len(training)==2400
 dev=read(BASE/'road_brightness_route_20261030_r1/fresh/manifest.json')
 assert not {r['group'] for r in training}&{r['group'] for r in dev}
 assert not {r['image_sha256'] for r in training}&{r['image_sha256'] for r in dev}
 free=shutil.disk_usage(ROOT).free;assert free>1024**3
 protocol=dict(status='FROZEN_BEFORE_PREPARATION_GRADIENTS_AND_CANDIDATE_INFERENCE',seed=SEED,
  purpose='Learn robustness to the deployed display enhancer, not merely increase brightness.',
  initial_checkpoint_sha256=sha(INITIAL),enhancer_sha256=sha(DLL),
  training='Original2400 annotated train images only. Every epoch one full-frame and one rotating raw tile per image. For full frames with raw meanY<=48 choose frozen ABI27 enhancement with deterministic50% probability; otherwise raw. All tiles raw. No pseudolabels.',
  model='Same YOLOv5n4class graph/anchors; actual neural weights change; FP32. Batch16 accumulation2,6epochs AdamW3e-5 cosine5e-6, horizontal flip only, BN buffers and anchors frozen, EMA checkpoints2/4/6.',
  route='Fixed raw meanY<=48: adapted model, enhanced global +3raw tiles. Mean>48: exact current accepted car model with4raw views. One model per shot, not ensemble. Existing board remains unchanged during experiment.',
  development='Previously used audit416 is now explicitly development:320 low +96 brighter. Pick one checkpoint only using development. Low primary compares enhanced-global+raw-tiles against SAME checkpoint raw4views AND prior accepted raw4view model.',
  gates=dict(low_car_ap_gain_vs_initial=.005,low_car_ap_gain_vs_same_model_raw=.005,
             precision_drop_vs_initial_max=.005,recall_drop_vs_initial_max=.005,
             fp_increase_vs_initial_max=0,brighter_route='Byte-identical unchanged initial predictions'),
  selection='Among checkpoints passing every gate, highest low carAP50. If none passes, keep ABI27 and archive failure. Do not search extra gains, epochs or thresholds on these results.',
  fresh_policy='Only after a checkpoint passes: select unused160 low and64 brighter excluding all recorded training/evaluation/brightness screening groups and hashes. Frozen one candidate, same gates, paired99% bootstrap carAP gain lower>0 versus initial raw and same-model raw. No fresh-test reselection.',
  timing='PC training and evaluation; not new board validation or realtime inference.',
  source_training_manifest_sha256=sha(ADAPT/'training_manifest.json'),development_manifest_sha256=sha(BASE/'road_brightness_route_20261030_r1/fresh/manifest.json'),
  hardware_access=False,sd_written=False)
 write(ROOT/'protocol.json',protocol)
 for p in Path(__file__).parent.glob('*enhanceadapt*.py'):shutil.copy2(p,ROOT/'source'/p.name)
 (ROOT/'enhanced_training').mkdir();engine=Enhancer();cv2.setNumThreads(1);begin=time.monotonic()
 original={r['name']:r for r in read(DATA/'dataset/manifest.json') if r.get('status')=='READY' and r['split']=='train'}
 def item(r):
  ip=DATA/'dataset/images/train'/r['name'];lp=DATA/'dataset/labels/train'/(Path(r['name']).stem+'.txt')
  assert sha(ip)==r['image_sha256'] and sha(lp)==original[r['name']]['label_sha256']
  _,full=sensor400(ip);mean=mean_y(full);record=dict(r,mean_raw=mean,enhanced_full=None)
  if mean<=48:
   image=preprocess400(engine.run(full));p=ROOT/'enhanced_training'/(Path(r['name']).stem+'.png')
   Image.fromarray(image).save(p,compress_level=1)
   assert np.array_equal(np.asarray(Image.open(p)),image)
   record['enhanced_full']=dict(image=str(p),sha256=sha(p),labels=r['views'][0]['labels'])
  return record
 rows=[]
 with cf.ThreadPoolExecutor(4) as pool:
  for i,r in enumerate(pool.map(item,training),1):
   rows.append(r)
   if i%120==0:print('ENHANCEADAPT_PREP',i,len(training),'enhanced',sum(z['enhanced_full'] is not None for z in rows),'seconds',round(time.monotonic()-begin),flush=True)
 write(ROOT/'training_manifest.json',rows)
 write(ROOT/'prepared.json',dict(status='TRAIN_ONLY_MIXED_RAW_ENHANCEMENT_READY',images=len(rows),enhanced_sources=sum(r['enhanced_full'] is not None for r in rows),
  periods=dict(collections.Counter(r['timeofday'] for r in rows)),manifest_sha256=sha(ROOT/'training_manifest.json'),seconds=time.monotonic()-begin,free_bytes_at_start=free,
  no_train_development_group_or_hash_overlap=True,hardware_access=False,sd_written=False))
 print('ENHANCEADAPT_PREPARED',read(ROOT/'prepared.json'),flush=True)

if __name__=='__main__':main()
