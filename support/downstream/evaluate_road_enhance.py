"""Select only on old validation; retain all curves and all failures."""
from pathlib import Path
import json
import cv2,numpy as np
from road_enhance_common import ROOT,NN,CAPS,enhance,write,sha
from road_arm_common import preprocess400
def main():
 assert (ROOT/'numeric_complete.json').exists();out=ROOT/'validation320';out.mkdir(exist_ok=False)
 from road_light_evaluate import validation_rows
 from road_adapt_eval_core import torch,evaluate_serial_predictions,non_max_suppression,scale_boxes
 rows=validation_rows();assert len(rows)==320
 torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
 model=torch.load('E:/FPGA_Enhance_Work/road_detection_20261026/frozen/road4_best.pt',map_location='cpu',weights_only=False)['model'].float().fuse().cuda().eval()
 frames=Path('E:/FPGA_Enhance_Work/road_pipeline_diagnostic_20261026/camera_order/frames')
 raw={r['name']:cv2.imread(str(frames/(Path(r['name']).stem+'.sim565.png')))[:,:,::-1].copy() for r in rows};assert all(a.shape==(240,400,3) for a in raw.values())
 records={}
 for cap in [0,*CAPS]:
  tag='raw' if cap==0 else f'cap{cap}';folder=out/tag;folder.mkdir();predictions={};stats=[]
  with torch.inference_mode():
   for at in range(0,len(rows),8):
    rs=rows[at:at+8];images=[]
    for r in rs:
     a=raw[r['name']]
     if cap:a,s=enhance(a,1,cap);stats.append(dict(name=r['name'],**s))
     images.append(preprocess400(a).transpose(2,0,1))
    x=torch.from_numpy(np.ascontiguousarray(np.stack(images))).cuda().float()/255
    pred=non_max_suppression(model(x),.001,.6,max_det=300)
    for r,p in zip(rs,pred):
     if len(p):scale_boxes((320,320),p[:,:4],(240,400),ratio_pad=((.8,.8),(0.,64.)))
     predictions[r['name']]=p.cpu().float().tolist()
  m=evaluate_serial_predictions(rows,predictions,folder,tag);records[tag]=dict(cap=cap,metrics=m);write(folder/'enhancement_stats.json',stats)
  print('ROAD_ENHANCE_VALIDATION',tag,m['all']['mAP50'],m['by_time']['night']['mAP50'],flush=True)
 base=records['raw']['metrics'];passing=[]
 for cap in CAPS:
  r=records[f'cap{cap}'];m=r['metrics'];night=m['by_time']['night'];bn=base['by_time']['night']
  tests=dict(night_ap=night['mAP50']>=.95*bn['mAP50'],all_ap=m['all']['mAP50']>=.97*base['all']['mAP50'],person_recall=night['classes']['person']['recall']>=.9*bn['classes']['person']['recall'])
  r.update(gates=tests,passed=all(tests.values()))
  if r['passed']:passing.append(r)
 selected=max(passing,key=lambda r:(r['metrics']['by_time']['night']['mAP50'],-r['cap'])) if passing else records['cap16']
 write(ROOT/'selected.json',dict(status='OLD_VALIDATION_ONLY_ENHANCEMENT_POLICY_FROZEN',cap=selected['cap'],mode=1,validation_gates_passed=bool(passing),records=records,detector_weights_sha256=sha(NN/'weights.f32'),hardware_access=False,sd_written=False,no_recognition_improvement_claim=selected['metrics']['by_time']['night']['mAP50']<=base['by_time']['night']['mAP50']))
 print('ROAD_ENHANCE_POLICY_SELECTED',selected['cap'],'validation_gates',bool(passing),flush=True)
if __name__=='__main__':main()
