"""A new preregistered paired/teacher experiment; retain R1 failures and untouched holdout."""
from pathlib import Path
import collections,concurrent.futures as cf,hashlib,os,shutil
import cv2,numpy as np
from road_twilight_r2_common import *
from road_enhance_common import enhance
from road_arm_common import preprocess400
from prepare_road_light import sensor_proxy
from prepare_road_training_data import fetch,CLASSES
HERE=Path(__file__).resolve().parent
URL='https://huggingface.co/datasets/dronefreak/BDD100K/resolve/69e9f9a60103df97e151e2606a6ad182db824f55/'
def main():
 assert (PREV/'holdout_not_consumed.json').exists() and not (PREV/'fresh_evaluation').exists();ROOT.mkdir(exist_ok=False);assert sha(TEACHER)==TEACHER_SHA
 oldpaths=[BASE/'dataset/manifest.json',Path('E:/FPGA_Enhance_Work/road_joint_adapt_20261026/fresh/manifest.json'),LIGHT/'fresh/manifest.json',Path('E:/FPGA_Enhance_Work/road_realtime_20261027/fresh/manifest.json'),PREV/'fresh/manifest.json']
 old=[r for p in oldpaths for r in read(p)];excluded={r['group'] for r in old};hashes={r.get('image_sha256') for r in old};selected=[];used=set()
 paths={Path(r['rfilename']).name:r['rfilename'] for r in read(BASE/'BDD100K_repo.json')['siblings'] if r['rfilename'].endswith('.jpg') and '/train/' in r['rfilename']}
 meta=[__import__('json').loads(s) for p in sorted((BASE/'source_metadata').glob('train_*.jsonl')) for s in p.read_text(encoding='utf-8').splitlines()]
 for period,n in [('dawn/dusk',400),('night',200)]:
  pool=[r for r in meta if r['label']==period and r['file_name'] in paths and r['file_name'].split('-')[0] not in excluded and int(hashlib.sha256(('2026102621|'+r['file_name'].split('-')[0]).encode()).hexdigest()[:8],16)%100<85]
  pool.sort(key=lambda r:hashlib.sha256((str(SEED)+'|'+r['file_name']).encode()).hexdigest());count=0
  for r in pool:
   name=r['file_name'];group=name.split('-')[0]
   if group in used:continue
   selected.append(dict(name=name,group=group,timeofday=period,image_path=paths[name],split='train',official_split='train'));used.add(group);count+=1
   if count==n:break
  assert count==n,(period,count,n)
 write(ROOT/'extra_training_selection.json',selected)
 write(ROOT/'protocol.json',dict(status='R2_FROZEN_BEFORE_EXTRA_DOWNLOAD_AND_GRADIENTS',seed=SEED,epochs=EPOCHS,checkpoint_epochs=CHECKPOINTS,initialization_sha256=TEACHER_SHA,train_unique_images=3000,extra_train={'dawn/dusk':400,'night':200},old_validation=320,heldout480_unconsumed=True,heldout_manifest_sha256=sha(PREV/'fresh/manifest.json'),extra_selection_sha256=sha(ROOT/'extra_training_selection.json'),reason='R1 adapted checkpoints forgot night performance and did not establish runtime enhancement benefit. No new-test predictions were consumed.',same_architecture=True,fp32=True,amp=False,tf32=False,matched_controls='raw_control gets paired raw/raw, enhance_adapt gets raw/enhanced, same GT, same index and flip plans, same losses/teacher/optimizer steps. Both see two views per sampled image.',sampling={'night':.4,'dawn/dusk':.4,'daytime':.2},sampled_examples_per_epoch=3072,batch_unique=8,student_batch_views=16,gradient_accumulation=4,optimizer='AdamW lr5e-5 cosine to1e-5, wd1e-5; divide microbatch loss by4; clip10 at optimizer step',batchnorm='Freeze running mean/variance in both models, retain affine gradients. Assert buffers unchanged.',augmentations='Matched horizontal flips only; paired images preserve exact gamma/resize relationship.',teacher_consistency='Frozen original raw teacher. Positive anchors assigned by training GT and teacher obj>.2, GT-class prob>.4: average two-view .5objBCE+.5classBCE+.25sigmoid-box SmoothL1 over heads. Lambda.02 times16. No pseudo-labels.',feature_consistency='Stride8 model.4 C3 feature SmoothL1 normalized by detached teacher perchannel mean absolute clamped.05; lambda.005 times16, both views to teacher raw. Teacher sees training data only.',loss='Standard4class/320 YOLO scaled supervision, no extra person positive-class boost',gamma='Unchanged deployed cap32 gamma0.65/gate40..80. No curve retuning.',selection_and_release='Same checkpoint selection/retention gates and paired bootstrap release rules as R1; all checkpoint choice uses old320 only. If no candidate passes, holdout remains unread.',hardware_access=False,sd_written=False))
 (ROOT/'source').mkdir()
 for n in ['road_twilight_r2_common.py','prepare_road_twilight_r2.py','road_enhance_common.py']:shutil.copy2(HERE/n,ROOT/'source'/n)
 shutil.copytree(PREV/'yolov5',ROOT/'yolov5',ignore=shutil.ignore_patterns('__pycache__','*.pyc','runs','.git'))
 for mode in ['raw_control','enhance_adapt']:
  for split in ['train','val']:
   for kind in ['images','labels']:(ROOT/'dataset'/mode/kind/split).mkdir(parents=True)
  for p in (PREV/'dataset'/mode).rglob('*'):
   if p.is_file() and p.suffix in ['.png','.txt']:
    dest=ROOT/'dataset'/mode/p.relative_to(PREV/'dataset'/mode);os.link(p,dest)
 records=read(PREV/'dataset/manifest.json')
 for kind in ['images','labels','annotations']:(ROOT/'extra'/kind).mkdir(parents=True)
 def one(r):
  stem=Path(r['name']).stem;ap=ROOT/'extra/annotations'/(stem+'.json');ip=ROOT/'extra/images'/r['name'];ann=r['image_path'].replace('images_100k/100k','labels/100k').rsplit('.',1)[0]+'.json'
  ap.write_bytes(fetch(URL+ann));a=read(ap);assert a['name']==stem and a['attributes']['timeofday']==r['timeofday'] and len(a['frames'])==1 and a['frames'][0]['timestamp']==10000
  ip.write_bytes(fetch(URL+r['image_path']));assert sha(ip) not in hashes;image=cv2.imread(str(ip));assert image.shape==(720,1280,3);labels=[];mapped=[];counts=[0]*4;invalid=0
  for o in a['frames'][0]['objects']:
   if o.get('category') not in CLASSES or 'box2d' not in o:continue
   b=o['box2d'];x1=max(0.,min(1280.,float(b['x1'])));x2=max(0.,min(1280.,float(b['x2'])));y1=max(0.,min(720.,float(b['y1'])));y2=max(0.,min(720.,float(b['y2'])))
   if x2<=x1 or y2<=y1:invalid+=1;continue
   k=CLASSES[o['category']];counts[k]+=1;x=(x1+x2)/2560;y=(y1+y2)/1440;w=(x2-x1)/1280;h=(y2-y1)/720
   labels.append(f'{k} {x:.9f} {y:.9f} {w:.9f} {h:.9f}');mapped.append(f'{k} {x:.9f} {(.6*y+.2):.9f} {w:.9f} {(.6*h):.9f}')
  lp=ROOT/'extra/labels'/(stem+'.txt');lp.write_text('\n'.join(labels)+'\n' if labels else '',encoding='ascii');raw=sensor_proxy(image[:,:,::-1].copy());enh,stats=enhance(raw,1,32);outputs={}
  for mode,rgb in [('raw_control',raw),('enhance_adapt',enh)]:
   path=ROOT/'dataset'/mode/'images/train'/(stem+'.png');assert cv2.imwrite(str(path),preprocess400(rgb)[:,:,::-1]);mp=ROOT/'dataset'/mode/'labels/train'/(stem+'.txt');mp.write_text('\n'.join(mapped)+'\n' if mapped else '',encoding='ascii');outputs[mode]=sha(path)
  return dict(**r,image_sha256=sha(ip),annotation_sha256=sha(ap),label_sha256=sha(lp),mapped_label_sha256=sha(mp),raw320_sha256=outputs['raw_control'],enh320_sha256=outputs['enhance_adapt'],class_counts=counts,invalid_boxes=invalid,enhancement_stats=stats)
 extra=[]
 with cf.ThreadPoolExecutor(8) as pool:
  for r in pool.map(one,selected):
   extra.append(r)
   if len(extra)%100==0:print('TWILIGHT_R2_EXTRA_LABELED_TRAIN_IMAGES',len(extra),flush=True)
 records+=extra;write(ROOT/'extra/manifest.json',extra);write(ROOT/'dataset/manifest.json',records)
 for kind in ['images','labels','annotations']:
  (ROOT/'fresh'/kind).mkdir(parents=True)
  for p in (PREV/'fresh'/kind).iterdir():os.link(p,ROOT/'fresh'/kind/p.name)
 for n in ['manifest.json','complete.json']:shutil.copy2(PREV/'fresh'/n,ROOT/'fresh'/n)
 shutil.copy2(PREV/'fresh_selection.json',ROOT/'fresh_selection.json')
 assert len([r for r in records if r['split']=='train'])==3000 and len([r for r in records if r['split']=='val'])==320
 gs={s:{r['group'] for r in records if r['split']==s} for s in ['train','val']};assert not gs['train']&gs['val'];assert not gs['train']&{r['group'] for r in read(ROOT/'fresh/manifest.json')}
 write(ROOT/'prepare_complete.json',dict(status='R2_PAIRED3000_TRAIN_OLD320_VAL_AND_UNREAD480_TEST_READY',dataset_manifest_sha256=sha(ROOT/'dataset/manifest.json'),extra_manifest_sha256=sha(ROOT/'extra/manifest.json'),periods=dict(collections.Counter(r['split']+'/'+r['timeofday'] for r in records)),new_test_not_used=True,hardware_access=False));print('TWILIGHT_R2_PREPARATION_COMPLETE',flush=True)
if __name__=='__main__':main()
