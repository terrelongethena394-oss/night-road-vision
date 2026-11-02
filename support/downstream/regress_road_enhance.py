"""Frozen selected curve on the existing 480-image regression set, not a new blind test."""
from pathlib import Path
import json
import cv2,numpy as np
from road_enhance_common import ROOT,enhance,write,sha
from road_arm_common import preprocess400
def main():
 selected=json.loads((ROOT/'selected.json').read_text());assert selected['validation_gates_passed'];data=Path('E:/FPGA_Enhance_Work/road_realtime_20261027/fresh');out=ROOT/'regression480';out.mkdir(exist_ok=False)
 write(out/'protocol.json',dict(status='SELECTED_CURVE_FROZEN_BEFORE_REGRESSION',selected_sha256=sha(ROOT/'selected.json'),data_manifest_sha256=sha(data/'manifest.json'),cap=selected['cap'],caveat='Existing heldout480 previously used for quantization evaluation; regression comparison, not a new independent blind test. No tuning or reselection on these results.',hardware_access=False,sd_written=False))
 from prepare_road_light import sensor_proxy
 from road_adapt_eval_core import torch,evaluate_serial_predictions,non_max_suppression,scale_boxes
 torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
 rows=[{**r,'label_path':str(data/'labels'/(Path(r['name']).stem+'.txt'))} for r in json.loads((data/'manifest.json').read_text())];assert len(rows)==480
 model=torch.load('E:/FPGA_Enhance_Work/road_detection_20261026/frozen/road4_best.pt',map_location='cpu',weights_only=False)['model'].float().fuse().cuda().eval()
 results={};cached={r['name']:sensor_proxy(cv2.imread(str(data/'images'/r['name']))[:,:,::-1].copy()) for r in rows}
 for active in [0,1]:
  tag='auto' if active else 'raw';folder=out/tag;folder.mkdir();predictions={};stats=[]
  with torch.inference_mode():
   for at in range(0,len(rows),8):
    rs=rows[at:at+8];images=[]
    for r in rs:
     rgb=cached[r['name']]
     if active:rgb,s=enhance(rgb,1,selected['cap']);stats.append(dict(name=r['name'],**s))
     images.append(preprocess400(rgb).transpose(2,0,1))
    x=torch.from_numpy(np.ascontiguousarray(np.stack(images))).cuda().float()/255;ps=non_max_suppression(model(x),.001,.6,max_det=300)
    for r,p in zip(rs,ps):
     if len(p):scale_boxes((320,320),p[:,:4],(240,400),ratio_pad=((.8,.8),(0.,64.)))
     predictions[r['name']]=p.cpu().float().tolist()
  results[tag]=evaluate_serial_predictions(rows,predictions,folder,tag);write(folder/'enhancement_stats.json',stats)
  print('ROAD_ENHANCE_REGRESSION',tag,results[tag]['all']['mAP50'],results[tag]['by_time']['night']['mAP50'],flush=True)
 a=results['auto'];b=results['raw'];tests=dict(night_ap=a['by_time']['night']['mAP50']>=.95*b['by_time']['night']['mAP50'],all_ap=a['all']['mAP50']>=.97*b['all']['mAP50'],person_recall=a['by_time']['night']['classes']['person']['recall']>=.9*b['by_time']['night']['classes']['person']['recall'])
 write(out/'complete.json',dict(status='FIXED_CURVE_EXISTING480_REGRESSION_COMPLETE',raw=b,auto=a,gates=tests,passed=all(tests.values()),new_independent_test=False,selected_unchanged=sha(ROOT/'selected.json')==json.loads((out/'protocol.json').read_text())['selected_sha256'],hardware_access=False,sd_written=False));print('ROAD_ENHANCE_REGRESSION_COMPLETE',tests,flush=True)
if __name__=='__main__':main()
