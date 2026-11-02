"""Generate hard proposal labels from original train GT only, not detector labels."""
import shutil,time
import numpy as np
import road_accuracy_common as ac
from car_patch_verifier_common import *
from study_car_zoom_20261030 import XS,zoom,map_zoom

def main():
 assert not ROOT.exists();ROOT.mkdir();(ROOT/'source').mkdir()
 old=read(ZOOM/'confirmation/fresh_result.json');assert not old['accepted']
 train=read(BASE/'road_enhanceadapt_20261030_r1/training_manifest.json')
 candidates=sorted([r for r in train if r['mean_raw']<=48],key=lambda r:hashlib.sha256((str(SEED)+'|'+r['name']).encode()).hexdigest())
 selected=[];seen=set()
 for r in candidates:
  if r['group'] not in seen:selected.append(r);seen.add(r['group'])
  if len(selected)==600:break
 assert len(selected)==600
 for i,r in enumerate(selected):r['verifier_split']='train' if i<480 else 'internal_val'
 for path in [BASE/'road_brightness_route_20261030_r1/fresh/manifest.json',ZOOM/'confirmation/fresh/manifest.json']:
  assert not seen&{r['group'] for r in read(path)}
 protocol=dict(status='VERIFIER_DATA_MODEL_AND_GATES_FROZEN_BEFORE_NEW_PREDICTIONS_AND_GRADIENTS',
  purpose='Review only added zoom proposals, leave all prior4view detections untouched.',
  train='600 unique original-training prefix groups selected by fixed hash from rawmean<=48;480 fit,120 internal validation. All proposal labels from original car GT:IoU>=.5 positive,<=.2 negative, middle ignored. No pseudolabels.',
  cnn='RGB32x32 context1.25 nearest-centre source800 crop; fixed local gain clip80/(meanY+4)1..3. Conv3->8->16->24 stride2 ReLU;flatten384+6metadata->32ReLU->1. Actual FP32 learned weights, no BN.',
  metadata='Raw proposal confidence,cx/400,cy/240,w/400,h/240,raw patch meanY/255.',
  training=dict(epochs=EPOCHS,checkpoints=CHECKPOINTS,batch=128,balanced_per_epoch=6000,optimizer='AdamWlr.001 cosine.0001 wd.0001',augmentation='horizontal patch flip only, scene coordinates unchanged',seed=SEED),
  development='Reused low320 plus previous zoom low160,now explicitly development. No new blind accuracy claim here.',
  fusion='Accepted4view boxes unchanged. Added zoom scores multiplied by learned probability^power and fixed weight. Existing dedup/NMS geometry unchanged.',
  grid=dict(weights=[.65,.85,1.],powers=[.5,1.]),
  gates='Each reused cohort:AP gain>=1pp,precision drop<=.5pp,recall gain>=1pp versus4view;new false positives <=75%unverified zoom.65 additions;retain>=90%unverified zoom.65 added TP. Best mean AP qualified checkpoint/params.',
  fresh_policy='One frozen candidate on new240 low+64 brighter,exclude all recorded training/evaluation/screening groups/hashes. Same AP/P/R gates and99%paired AP-gain CI lower>0 versus4view. NewFP reduction>=25% vs unverified7view.65,retain>=90%its extraTP. No test-driven replacement.',
  geometry_sha256=sha(ZOOM/'protocol.json'),detector_sha256=sha(INITIAL),hardware_access=False,sd_written=False)
 write(ROOT/'protocol.json',protocol)
 write(ROOT/'training_selection.json',[{k:r[k] for k in ['name','group','image_sha256','mean_raw','verifier_split']} for r in selected])
 write(ROOT/'training_manifest.json',[{k:r[k] for k in ['name','group','image_sha256','verifier_split']} for r in selected])
 for n in ['car_patch_verifier_common.py',Path(__file__).name]:shutil.copy2(Path(__file__).with_name(n),ROOT/'source'/n)
 ac.WEIGHTS=INITIAL;det=ac.Detector();y=read(ZOOM/'protocol.json')['geometry']['y'];begin=time.monotonic()
 patches=[];metadata=[];targets=[];records=[];proposals=[]
 for at in range(0,len(selected),8):
  rr=selected[at:at+8];ims=[];sensors=[]
  for r in rr:
   ip=BASE/'road_detection_20261026/dataset/images/train'/r['name'];assert sha(ip)==r['image_sha256']
   sensor,_=ac.sensor400(ip);sensors.append(sensor);ims.extend(zoom(sensor,x,y) for x in XS)
  pp=det.run(ims)
  for i,r in enumerate(rr):
   gt=ac.truth(BASE/'road_detection_20261026/dataset/labels/train'/(Path(r['name']).stem+'.txt'));gt=gt[gt[:,0]==1,1:]
   boxes=np.concatenate([map_zoom(pp[3*i+j],x,y) for j,x in enumerate(XS)])
   boxes=boxes[boxes[:,4]>=.05];proposals.append(dict(name=r['name'],split=r['verifier_split'],boxes=boxes.tolist()))
   for b in boxes:
    overlap=iou_max(b,gt)
    if .2<overlap<.5:continue
    image,meta=patch(sensors[i],b);index=len(patches);patches.append(image);metadata.append(meta);targets.append(int(overlap>=.5))
    records.append(dict(index=index,name=r['name'],split=r['verifier_split'],target=targets[-1],iou=overlap,box=b.tolist()))
  if (at+len(rr))%80==0:print('CAR_VERIFIER_PROPOSALS',at+len(rr),len(selected),'patches',len(patches),'seconds',round(time.monotonic()-begin),flush=True)
 np.asarray(patches,np.uint8).tofile(ROOT/'patches.u8');np.asarray(metadata,'<f4').tofile(ROOT/'metadata.f32');np.asarray(targets,np.uint8).tofile(ROOT/'targets.u8')
 write(ROOT/'patches.json',records);write(ROOT/'training_proposals.json',proposals)
 counts={}
 for split in ['train','internal_val']:
  tt=[r['target'] for r in records if r['split']==split];counts[split]=dict(patches=len(tt),positive=sum(tt),negative=len(tt)-sum(tt))
 assert counts['train']['positive']>=100 and counts['train']['negative']>=500 and counts['internal_val']['positive']>=30
 write(ROOT/'prepared.json',dict(status='TRUE_TRAIN_GT_VERIFIER_PATCHES_READY',shape=[len(patches),32,32,3],counts=counts,
  source_images=600,patches_sha256=sha(ROOT/'patches.u8'),metadata_sha256=sha(ROOT/'metadata.f32'),targets_sha256=sha(ROOT/'targets.u8'),records_sha256=sha(ROOT/'patches.json'),seconds=time.monotonic()-begin,
  no_development_overlap=True,hardware_access=False,sd_written=False))
 print('CAR_VERIFIER_PATCHES_READY',counts,flush=True)

if __name__=='__main__':main()
