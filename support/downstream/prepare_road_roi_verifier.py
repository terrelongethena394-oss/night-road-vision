"""True train-image hard negatives; all previous test images remain excluded."""
from pathlib import Path
import collections,shutil,time
import cv2,numpy as np
from road_roi_verifier_common import *
from road_arm_common import preprocess400
HERE=Path(__file__).resolve().parent

def main():
 ROOT.mkdir(exist_ok=False);policy=read(GUARD/'selected.json')['chosen']['policy'];rows=read(R2/'dataset/manifest.json');train=[r for r in rows if r['split']=='train'];val=[r for r in rows if r['split']=='val'];assert len(train)==3000 and len(val)==320 and not {r['group'] for r in train}&{r['group'] for r in val}
 frozen_test=read(GUARD/'fresh/manifest.json');assert not {r['group'] for r in rows}&{r['group'] for r in frozen_test}
 source={r['name']:{**r,'image':str(BASE/'dataset/images'/r['split']/r['name']),'label':str(BASE/'dataset/labels'/r['split']/(Path(r['name']).stem+'.txt'))} for r in read(BASE/'dataset/manifest.json')}
 for r in read(R2/'extra/manifest.json'):source[r['name']]={**r,'image':str(R2/'extra/images'/r['name']),'label':str(R2/'extra/labels'/(Path(r['name']).stem+'.txt'))}
 write(ROOT/'protocol.json',dict(status='VERIFIER_DESIGN_FROZEN_BEFORE_TRAINING_PROPOSALS',seed=SEED,epochs=EPOCHS,checkpoints=CHECKPOINTS,floors=FLOORS,train_images=3000,old_val_images=320,train_validation_group_overlap=False,previous_guard_test_group_overlap=False,train_source_manifest_sha256=sha(R2/'dataset/manifest.json'),roi_policy=policy,teacher_sha256=TEACHER_SHA,proposal='Unchanged full and center YOLOv5n; only extra person ROI boxes raw score>=.05 passing frozen geometry are verified.',labels='TRAIN GT only: positive IoU>=.5 with person, negative max-person-IoU<.2; ignore ambiguous. No pseudo-labels, no previous-test labels or crops.',crop='800x480 original RGB565 proxy,1.25x box context, floor/ceil bounds, integer nearest-center24x48 RGB, /255.',model='Conv3x3 stride2 pad1:3->8->16->16 withReLU, global average, linear16->1;3729 FP32 parameters, noBN/dropout.',training='Balanced train sampling4000patches/epoch, batch128, BCEWithLogits, AdamWlr.001 cosine to.0001,wd.0001; noAMP/TF32.',validation='Freeze selected epoch+floor using only old320. Same dusk+2pp/all+1pp/person recall+3pp guards; all times totalFP/personFP<=1.10baseline+2, night/dayAP>=baseline-.005. Prefer highest duskAP among passing, then overall.',new_test='Only after old-validation passes, use new groups excluding all previous sets; single chosen epoch/floor;97.5% pairedCI lower>0 for duskAP; do not reuse previous guard480 to choose.',hardware_access=False,sd_written=False))
 (ROOT/'source').mkdir()
 for n in ['road_roi_verifier_common.py','prepare_road_roi_verifier.py','road_roi_guard_common.py']:shutil.copy2(HERE/n,ROOT/'source'/n)
 from road_adapt_eval_core import torch,non_max_suppression,scale_boxes,truth
 torch.set_num_threads(3);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;assert sha(TEACHER)==TEACHER_SHA;model=torch.load(TEACHER,map_location='cpu',weights_only=False)['model'].float().fuse().cuda().eval()
 patches=[];targets=[];metadata=[];start=time.monotonic()
 def sensor(r):
  s=source[r['name']];assert sha(s['image'])==s['image_sha256'];image=cv2.imread(s['image'])[:,:,::-1].copy();a=cv2.resize(image,(800,480),interpolation=cv2.INTER_LINEAR);a[:,:,0]&=248;a[:,:,1]&=252;a[:,:,2]&=248;return a
 def add(r,a,full,roi,is_train):
  s=source[r['name']];gt=truth(dict(label_path=s['label']),400,240);gt=gt[gt[:,0]==0,1:];area=np.maximum(0,gt[:,2:]-gt[:,:2]).prod(1)
  for j,p in enumerate(roi):
   if not person_eligible(full,p,policy):continue
   v=np.maximum(0,np.minimum(p[2:4],gt[:,2:])-np.maximum(p[:2],gt[:,:2])).prod(1);iou=v/(area+(p[2]-p[0])*(p[3]-p[1])-v+1e-9);best=float(iou.max(initial=0));label=1 if best>=.5 else (0 if best<.2 else -1)
   if is_train and label<0:continue
   patches.append(crop_patch(a,p));targets.append(label);metadata.append(dict(name=r['name'],group=r['group'],timeofday=r['timeofday'],split=r['split'],roi_index=j,score=float(p[4]),max_person_iou=best,target=label))
 with torch.inference_mode():
  for at in range(0,len(train),8):
   rs=train[at:at+8];sensors=[sensor(r) for r in rs];images=[]
   for a in sensors:
    b=a.astype(np.uint16);raw=((b[0::2,0::2]+b[0::2,1::2]+b[1::2,0::2]+b[1::2,1::2]+2)//4).astype(np.uint8);images.extend([preprocess400(raw).transpose(2,0,1),preprocess400(a[120:360,200:600].copy()).transpose(2,0,1)])
   x=torch.from_numpy(np.ascontiguousarray(np.stack(images))).cuda().float()/255;ps=non_max_suppression(model(x),.001,.6,max_det=300)
   for j,r in enumerate(rs):
    f,z=ps[2*j],ps[2*j+1]
    for p in [f,z]:
     if len(p):scale_boxes((320,320),p[:,:4],(240,400),ratio_pad=((.8,.8),(0.,64.)))
    z=z[(z[:,0]>1)&(z[:,1]>1)&(z[:,2]<399)&(z[:,3]<239)].clone();z[:,[0,2]]=z[:,[0,2]]*.5+100;z[:,[1,3]]=z[:,[1,3]]*.5+60;add(r,sensors[j],f.cpu().numpy(),z.cpu().numpy(),True)
   if (at+len(rs))%400==0:print('VERIFIER_TRAIN_PROPOSALS',at+len(rs),len(patches),round(time.monotonic()-start,1),flush=True)
 ntrain=len(patches);full={r['name']:r for r in read(OLD/'full_predictions.json')};roi={r['name']:r for r in read(OLD/'center_only_diagnostic_predictions.json')}
 for r in val:add(r,sensor(r),np.asarray(full[r['name']]['detections'],np.float32).reshape(-1,6),np.asarray(roi[r['name']]['detections'],np.float32).reshape(-1,6),False)
 np.stack(patches).tofile(ROOT/'patches.u8');np.asarray(targets,np.int8).tofile(ROOT/'targets.i8');write(ROOT/'patches.json',metadata);counts=dict(collections.Counter(targets[:ntrain]));assert counts.get(1,0)>=100 and counts.get(0,0)>=100,counts
 write(ROOT/'prepared.json',dict(status='TRAIN_ONLY_LABELED_PATCHES_AND_OLD_VAL_READY',train_patches=ntrain,val_patches=len(patches)-ntrain,shape=[len(patches),48,24,3],train_target_counts={str(k):v for k,v in counts.items()},patches_sha256=sha(ROOT/'patches.u8'),targets_sha256=sha(ROOT/'targets.i8'),metadata_sha256=sha(ROOT/'patches.json'),hardware_access=False));print('VERIFIER_PATCH_DATA_READY',ntrain,len(patches)-ntrain,counts,flush=True)
if __name__=='__main__':main()
