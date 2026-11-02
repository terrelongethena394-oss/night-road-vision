"""Supervised box offsets use original training annotations, never evaluation GT."""
import shutil,time
import numpy as np
import road_accuracy_common as ac
from car_box_refine_common import *

def main():
 assert not ROOT.exists() and not read(PREV/'veto_selected.json')['qualified'];ROOT.mkdir();(ROOT/'source').mkdir()
 selections=read(PREV/'training_selection.json');proposals=read(PREV/'training_proposals.json');assert len(selections)==len(proposals)==600
 protocol=dict(status='BOX_REFINEMENT_FROZEN_BEFORE_NEW_TRAINING_AND_EVALUATION',
  reason='Previous verifier failed all gates;23/45 addedFP in reused160 hadGTIoU.3..5,so presence confidence alone cannot fix localization.',
  train='Same600 original-training groups:480fit,120internal-validation. IoU>=.3 car-positive,<=.1 background,others ignored. Box regression target best originalGT delta-center/size and log-size ratio for positives;clipped+-1.5. No development/test labels in training.',
  architecture='Reuse trained verifier30 conv/fc1,copy old class head;add4 zero-initialized offset outputs. 17549FP32 parameters. Patchcontext1.5,same32RGB localgain80 mean,metadata detectorconfidence fixedzero to avoid confidence-label shortcut.',
  optimizer='80epochs,batch128,balanced6000/epoch,AdamWlr.0005cosine.00005wd.0001,clip5. BCE class +5*SmoothL1beta.1 positives. 50%negative draws score>=.25. No flips to preserve target offsets.',
  checkpoints=CHECKPOINTS,grid=dict(strength=[.5,1.],cap=[.1,.25],class_gate=[0.,.3]),weight=.65,
  development='Reused320+reused160,not independent. Same AP+1pp,precision>=baseline-.5pp,recall+1pp,newFP<=75%unverified additions,extraTP>=90%unverified additions on both separately.',
  fresh_policy=read(PREV/'protocol.json')['fresh_policy'],
  prior_failures=dict(continuous=sha(PREV/'selected.json'),veto=sha(PREV/'veto_selected.json')),
  seed=SEED,hardware_access=False,sd_written=False)
 write(ROOT/'protocol.json',protocol);write(ROOT/'training_manifest.json',selections)
 for n in ['car_box_refine_common.py',Path(__file__).name]:shutil.copy2(Path(__file__).with_name(n),ROOT/'source'/n)
 pixels=[];meta=[];targets=[];deltas=[];records=[];begin=time.monotonic();choices={r['name']:r for r in selections}
 for i,row in enumerate(proposals):
  r=choices[row['name']];ip=BASE/'road_detection_20261026/dataset/images/train'/r['name'];assert sha(ip)==r['image_sha256'];sensor,_=ac.sensor400(ip)
  gt=ac.truth(BASE/'road_detection_20261026/dataset/labels/train'/(Path(r['name']).stem+'.txt'));gt=gt[gt[:,0]==1,1:]
  for b in np.asarray(row['boxes'],np.float32).reshape(-1,6):
   inter=np.maximum(0,np.minimum(b[2:4],gt[:,2:4])-np.maximum(b[:2],gt[:,:2])).prod(1)
   iou=inter/(np.maximum(0,b[2:4]-b[:2]).prod()+np.maximum(0,gt[:,2:4]-gt[:,:2]).prod(1)-inter+1e-9)
   best=int(np.argmax(iou)) if len(iou) else -1;overlap=float(iou[best]) if best>=0 else 0.
   if .1<overlap<.3:continue
   positive=overlap>=.3;a,m=patch(sensor,b);delta=np.zeros(4,np.float32);target=np.zeros(4,np.float32)
   if positive:
    target=gt[best];wh=np.maximum(b[2:4]-b[:2],1e-6);tw=target[2:4]-target[:2]
    delta[:2]=((target[:2]+target[2:4])*.5-(b[:2]+b[2:4])*.5)/wh;delta[2:]=np.log(tw/wh);delta=np.clip(delta,-1.5,1.5)
   pixels.append(a);meta.append(m);targets.append(int(positive));deltas.append(delta)
   records.append(dict(name=r['name'],split=r['verifier_split'],target=int(positive),box=b.tolist(),gt=target.tolist(),iou=overlap))
  if (i+1)%120==0:print('BOX_REFINE_DATA',i+1,len(proposals),len(pixels),round(time.monotonic()-begin),flush=True)
 np.asarray(pixels,np.uint8).tofile(ROOT/'patches.u8');np.asarray(meta,'<f4').tofile(ROOT/'metadata.f32');np.asarray(targets,np.uint8).tofile(ROOT/'targets.u8');np.asarray(deltas,'<f4').tofile(ROOT/'deltas.f32');write(ROOT/'patches.json',records)
 counts={s:{str(t):sum(r['split']==s and r['target']==t for r in records) for t in [0,1]} for s in ['train','internal_val']}
 assert min(counts['train'].values())>500
 write(ROOT/'prepared.json',dict(status='TRUE_TRAIN_GT_BOX_REFINEMENT_DATA_READY',shape=[len(pixels),32,32,3],counts=counts,
  sha256={n:sha(ROOT/n) for n in ['patches.u8','metadata.f32','targets.u8','deltas.f32','patches.json']},hardware_access=False,sd_written=False))
 print('BOX_REFINE_PREPARED',counts,flush=True)

if __name__=='__main__':main()
