"""Old-validation-only feasibility of preserving true sensor detail in a center ROI.
This is an explicit extra inference, not super-resolution or a speed optimization.
"""
from pathlib import Path
import time
import cv2,numpy as np
from road_twilight_r2_common import ROOT,BASE,TEACHER,TEACHER_SHA,read,write,sha
from road_arm_common import preprocess400
OUT=ROOT.parent/'road_center_roi_20261027'

def main():
 OUT.mkdir(exist_ok=False)
 write(OUT/'protocol.json',dict(status='CENTER_ROI_RULES_FROZEN_BEFORE_OLD_VALIDATION_INFERENCE',checkpoint_sha256=TEACHER_SHA,roi_sensor_xywh=[200,120,400,240],sensor_wh=[800,480],full_downsample='Exact RGB565 truncation and rounded2x2 average to400x240',roi_downsample='No2x2average: retain original central400x240 RGB565 pixels',roi_map_to_full_xywh=[100,60,200,120],input320_preprocessing='Existing exact integer preprocess400',merge='Map ROI boxes x/2+100,y/2+60. Keep ROI boxes strictly inside1px border. Concatenate full and ROI predictions; class-aware NMS IoU0.6, max300. Confidence0.001 for AP,0.25 operating point. No brightness branch, weights unchanged.',extra_detector_forwards=1,expected_cost='Two full neural-network forwards per image; likely near2x inference latency. Not a default camera upgrade.',gate='Old-validation feasibility: duskAP>=full+.02; dusk-person recall>=full+.03; night/dayAP>=full-.005; dusk FP/personFP<=full*1.10+2. This does not authorize deployment without new heldout images, C/board numerics and explicit latency assessment.',old_validation_images=320,new_test_inference=False,hardware_access=False,sd_written=False))
 from road_adapt_eval_core import torch,evaluate_serial_predictions,non_max_suppression,scale_boxes
 from torchvision.ops import nms
 torch.set_num_threads(3);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
 assert sha(TEACHER)==TEACHER_SHA
 model=torch.load(TEACHER,map_location='cpu',weights_only=False)['model'].float().fuse().cuda().eval()
 rows=[{**r,'label_path':str(BASE/'dataset/labels/val'/(Path(r['name']).stem+'.txt'))} for r in read(ROOT/'dataset/manifest.json') if r['split']=='val'];assert len(rows)==320
 original={};merged={};roi_only={};t=time.monotonic()
 with torch.inference_mode():
  for at in range(0,len(rows),8):
   rs=rows[at:at+8];inputs=[]
   for r in rs:
    image=cv2.imread(str(BASE/'dataset/images/val'/r['name']))[:,:,::-1].copy();sensor=cv2.resize(image,(800,480),interpolation=cv2.INTER_LINEAR);sensor[:,:,0]&=248;sensor[:,:,1]&=252;sensor[:,:,2]&=248;b=sensor.astype(np.uint16);full=((b[0::2,0::2]+b[0::2,1::2]+b[1::2,0::2]+b[1::2,1::2]+2)//4).astype(np.uint8)
    f=preprocess400(full);saved=cv2.imread(str(ROOT/'dataset/raw_control/images/val'/(Path(r['name']).stem+'.png')))[:,:,::-1];assert np.array_equal(f,saved)
    roi=sensor[120:360,200:600].copy();inputs.extend([f.transpose(2,0,1),preprocess400(roi).transpose(2,0,1)])
   x=torch.from_numpy(np.ascontiguousarray(np.stack(inputs))).cuda().float()/255;ps=non_max_suppression(model(x),.001,.6,max_det=300)
   for j,r in enumerate(rs):
    a=ps[2*j];z=ps[2*j+1]
    for p in [a,z]:
     if len(p):scale_boxes((320,320),p[:,:4],(240,400),ratio_pad=((.8,.8),(0.,64.)))
    z=z[(z[:,0]>1)&(z[:,1]>1)&(z[:,2]<399)&(z[:,3]<239)].clone();z[:,[0,2]]=z[:,[0,2]]*.5+100;z[:,[1,3]]=z[:,[1,3]]*.5+60
    both=torch.cat([a,z]);ids=nms(both[:,:4]+both[:,5:6]*7680,both[:,4],.6)[:300] if len(both) else torch.empty(0,dtype=torch.long,device='cuda')
    original[r['name']]=a.cpu().float().tolist();roi_only[r['name']]=z.cpu().float().tolist();merged[r['name']]=both[ids].cpu().float().tolist()
   if (at+len(rs))%80==0:print('CENTER_ROI_OLD_VALIDATION',at+len(rs),round(time.monotonic()-t,1),flush=True)
 a=evaluate_serial_predictions(rows,original,OUT,'full');b=evaluate_serial_predictions(rows,merged,OUT,'full_plus_center');evaluate_serial_predictions(rows,roi_only,OUT,'center_only_diagnostic')
 ap=a['by_time']['dawn/dusk'];bp=b['by_time']['dawn/dusk'];p=ap['classes']['person'];q=bp['classes']['person']
 gates=dict(dusk_ap=bp['mAP50']>=ap['mAP50']+.02,dusk_person_recall=q['recall']>=p['recall']+.03,night=b['by_time']['night']['mAP50']>=a['by_time']['night']['mAP50']-.005,day=b['by_time']['daytime']['mAP50']>=a['by_time']['daytime']['mAP50']-.005,dusk_fp=sum(v['fp'] for v in bp['classes'].values())<=sum(v['fp'] for v in ap['classes'].values())*1.1+2,dusk_person_fp=q['fp']<=p['fp']*1.1+2)
 write(OUT/'complete.json',dict(status='CENTER_ROI_OLD_VALIDATION_FEASIBILITY_COMPLETE',baseline=a,candidate=b,gates=gates,old_validation_qualified=all(gates.values()),new_test_inference=False,hardware_access=False,sd_written=False,extra_neural_forwards=1,checkpoint_unchanged=True,cost_warning='Quality-only GPU feasibility; no camera FPS measurement; requires2 neural forwards, not realtime acceleration.'))
 print('CENTER_ROI_FEASIBILITY_COMPLETE',gates,'dusk',ap['mAP50'],bp['mAP50'],'person_recall',p['recall'],q['recall'],flush=True)

if __name__=='__main__':main()
