"""Freeze a new matched training experiment; fixed gamma, no test-based tuning."""
from pathlib import Path
import collections,concurrent.futures as cf,hashlib,os,shutil
import cv2,numpy as np
from road_twilight_common import *
from road_enhance_common import enhance
from road_arm_common import preprocess400
HERE=Path(__file__).resolve().parent
def main():
 ROOT.mkdir(exist_ok=False);assert sha(TEACHER)==TEACHER_SHA
 manifests=[BASE/'dataset/manifest.json',Path('E:/FPGA_Enhance_Work/road_joint_adapt_20261026/fresh/manifest.json'),LIGHT/'fresh/manifest.json',Path('E:/FPGA_Enhance_Work/road_realtime_20261027/fresh/manifest.json')]
 old=[r for p in manifests for r in read(p)];groups={r['group'] for r in old};names={r['name'] for r in old}
 paths={Path(x['rfilename']).name:x['rfilename'] for x in read(BASE/'BDD100K_repo.json')['siblings'] if x['rfilename'].endswith('.jpg') and '/val/' in x['rfilename']}
 meta=[__import__('json').loads(s) for p in sorted((BASE/'source_metadata').glob('val_*.jsonl')) for s in p.read_text(encoding='utf-8').splitlines()];selected=[];used=set()
 for period,n in QUOTA.items():
  pool=sorted([r for r in meta if r['label']==period and r['file_name'] in paths and r['file_name'].split('-')[0] not in groups],key=lambda r:hashlib.sha256((str(SEED)+'|'+r['file_name']).encode()).hexdigest());count=0
  for r in pool:
   name=r['file_name'];group=name.split('-')[0]
   if group in used:continue
   assert name not in names;used.add(group);selected.append(dict(name=name,group=group,timeofday=period,image_path=paths[name],split='fresh_test',official_split='val'));count+=1
   if count==n:break
  assert count==n,(period,count,n)
 write(ROOT/'fresh_selection.json',selected)
 write(ROOT/'protocol.json',dict(status='FROZEN_BEFORE_ANY_TRAINING_GRADIENTS_AND_NEW_TEST_INFERENCE',seed=SEED,epochs=EPOCHS,checkpoint_epochs=CHECKPOINTS,variants=['raw_control','enhance_adapt'],initialization_sha256=TEACHER_SHA,imgsz=320,batch=16,optimizer='AdamW lr1e-4 cosine to2e-5, weight_decay1e-5, gradient norm clip10',amp=False,tf32=False,training=2400,validation=320,sampling_probabilities={'night':.25,'dawn/dusk':.5,'daytime':.25},sampling='Same fixed epoch index lists for both modes; replacement sampling within training only. Counts are exposure counts, not independent images.',enhancement='Fixed already deployed ARM-compatible bounded gamma0.65 cap32; whole-frame auto gate40..80. Before exact integer resize and padding. No gamma parameter search this round.',training_control='Same original checkpoint, supervised loss, optimizer steps, epoch indices, architecture, anchors and augmentation settings. Only paired input pixels differ.',loss='YOLO standard320/4class scales; class BCE positive weights [1.5,1,1,1] in both modes.',checkpoint_selection='Old validation only. Choose best raw-control by duskAP among overall>=original-.005, night>=original-.005, daytime>=original-.005. Enhanced candidate must beat original duskAP by.01 AND matched-control duskAP by.005 AND same-enhance-model raw duskAP by.005; overall>=original+.005; night>=max(original,control-.005); day>=original-.005; dusk person recall>=control; duskFP<=1.10*control+2; duskPersonFP<=1.10*control+2. Prefer highest duskAP, then overall.',if_no_enhancement_candidate='Record failure and preserve current board; evaluate frozen best enhanced candidate diagnostically without relaxing gates. A better raw detector is a separate result, not evidence for enhancement.',new_test_quota=QUOTA,new_test_selection='Metadata hash order, one previously unseen filename-prefix group; excludes all prior dataset/group and exact hashes. No result-based selection. No changes after fresh results.',excluded_manifests={str(p):sha(p) for p in manifests},fresh_selection_sha256=sha(ROOT/'fresh_selection.json'),time_label_limit='BDD labels combine dawn and dusk; no dusk-only or cross-camera claim.',hardware_access=False,sd_written=False))
 source=ROOT/'source';source.mkdir()
 for n in ['road_twilight_common.py','prepare_road_twilight.py','road_enhance_common.py']:
  shutil.copy2(HERE/n,source/n)
 shutil.copytree(BASE/'yolov5',ROOT/'yolov5',ignore=shutil.ignore_patterns('__pycache__','runs','*.pyc','*.pt','.git'))
 manifest=read(LIGHT/'dataset/manifest.json');assert len(manifest)==2720;sg={s:{r['group'] for r in manifest if r['split']==s} for s in ['train','val']};assert not sg['train']&sg['val']
 for mode in ['raw_control','enhance_adapt']:
  for split in ['train','val']:
   for sub in ['images','labels']:(ROOT/'dataset'/mode/sub/split).mkdir(parents=True)
  (ROOT/'dataset'/mode/'road4.yaml').write_text('path: '+(ROOT/'dataset'/mode).as_posix()+'\ntrain: images/train\nval: images/val\nnc: 4\nnames: [person, car, truck, bus]\n',encoding='ascii')
 def one(r):
  split=r['split'];stem=Path(r['name']).stem;rawpath=LIGHT/'raw400'/split/(stem+'.png');assert sha(rawpath)==r['raw400_sha256']
  original=LIGHT/'dataset/images'/split/(stem+'.png');assert sha(original)==r['input320_sha256'];raw=cv2.imread(str(rawpath))[:,:,::-1].copy();enh,stats=enhance(raw,1,32);prepared=preprocess400(enh)
  a=ROOT/'dataset/raw_control/images'/split/(stem+'.png');b=ROOT/'dataset/enhance_adapt/images'/split/(stem+'.png');os.link(original,a);assert cv2.imwrite(str(b),prepared[:,:,::-1])
  label=LIGHT/'dataset/labels'/split/(stem+'.txt');assert sha(label)==r['mapped_label_sha256']
  for mode in ['raw_control','enhance_adapt']:shutil.copy2(label,ROOT/'dataset'/mode/'labels'/split/label.name)
  return dict(name=r['name'],group=r['group'],split=split,timeofday=r['timeofday'],raw320_sha256=sha(a),enh320_sha256=sha(b),label_sha256=sha(label),enhancement_stats=stats)
 records=[]
 with cf.ThreadPoolExecutor(4) as pool:
  for r in pool.map(one,manifest):
   records.append(r)
   if len(records)%400==0:print('TWILIGHT_PAIRED_INPUTS_READY',len(records),flush=True)
 write(ROOT/'dataset/manifest.json',records);write(ROOT/'prepare_complete.json',dict(status='MATCHED_EXACT320_TRAIN_AND_VALIDATION_READY',images=len(records),periods=dict(collections.Counter((r['split']+'/'+r['timeofday']) for r in records)),manifest_sha256=sha(ROOT/'dataset/manifest.json'),protocol_sha256=sha(ROOT/'protocol.json'),hardware_access=False))
 print('ROAD_TWILIGHT_PREPARED',flush=True)
if __name__=='__main__':main()
