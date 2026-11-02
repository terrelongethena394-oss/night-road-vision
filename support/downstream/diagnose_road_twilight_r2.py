"""Post-test descriptive error analysis; never chooses checkpoints or release thresholds."""
from pathlib import Path
from collections import defaultdict,Counter
import cv2,numpy as np
from road_twilight_r2_common import ROOT,read,write,sha
from road_enhance_common import enhance
from prepare_road_light import sensor_proxy
from prepare_road_training_data import CLASSES

def main():
 assert read(ROOT/'fresh_complete.json')['deployment_decision']=='retain_current'
 methods=['original','control','candidate_raw','candidate_enh']
 predictions={k:{r['name']:r for r in read(ROOT/'fresh_evaluation'/k/(k+'_predictions.json'))} for k in methods}
 totals=defaultdict(Counter);light=defaultdict(Counter);examples=[];names=['person','car','truck','bus']
 for row in read(ROOT/'fresh/manifest.json'):
  name=row['name'];base=predictions['original'][name];gt=np.asarray(base['ground_truth']).reshape(-1,5);period=row['timeofday']
  rgb=sensor_proxy(cv2.imread(str(ROOT/'fresh/images'/name))[:,:,::-1].copy());_,stats=enhance(rgb,1,32)
  bucket='mean<=40' if stats['mean_in']<=40 else ('40<mean<80' if stats['mean_in']<80 else 'mean>=80')
  light[period][bucket]+=1;light[period]['images']+=1;light[period]['bypassed' if stats['changed']==0 else 'changed']+=1
  ann=read(ROOT/'fresh/annotations'/(Path(name).stem+'.json'));objects=[]
  for o in ann['frames'][0]['objects']:
   if o.get('category') not in CLASSES or 'box2d' not in o:continue
   b=o['box2d'];x1=np.clip(float(b['x1']),0,1280);x2=np.clip(float(b['x2']),0,1280);y1=np.clip(float(b['y1']),0,720);y2=np.clip(float(b['y2']),0,720)
   if x2<=x1 or y2<=y1:continue
   objects.append((o,np.array([x1/3.2,y1/3.,x2/3.2,y2/3.])))
  assert len(objects)==len(gt)
  matched={k:set(predictions[k][name]['matched_gt']) for k in methods}
  for k in methods:assert np.allclose(np.asarray(predictions[k][name]['ground_truth']).reshape(-1,5),gt,atol=1e-9,rtol=0)
  for i,(target,(obj,bounds)) in enumerate(zip(gt,objects)):
   assert CLASSES[obj['category']]==int(target[0]) and np.allclose(target[1:],bounds,atol=1e-3,rtol=0)
   cls=names[int(target[0])];h=float(target[4]-target[2]);w=float(target[3]-target[1]);nh=h*.8;nw=w*.8
   hb='<16px' if nh<16 else ('16..32px' if nh<32 else ('32..64px' if nh<64 else '>=64px'))
   short=min(nw,nh);sb='<8px' if short<8 else ('8..16px' if short<16 else '>=16px')
   attrs=obj['attributes'];occluded=bool(attrs.get('occluded'));truncated=bool(attrs.get('truncated'))
   for dimension,value in [('all','all'),('input_height',hb),('input_short_side',sb),('occluded',str(occluded)),('truncated',str(truncated))]:
    c=totals[(period,cls,dimension,value)];c['objects']+=1
    for method in methods:c[method+'_tp']+=int(i in matched[method]);c[method+'_fn']+=int(i not in matched[method])
   if cls=='person' and i not in matched['original'] and len(examples)<20:
    examples.append(dict(name=name,timeofday=period,gt_index=i,height_input_px=nh,width_input_px=nw,occluded=occluded,truncated=truncated,mean_luma=stats['mean_in'],gamma_alpha=stats['alpha'],source_image=str(ROOT/'fresh/images'/name)))
 result=[]
 for (period,cls,dimension,value),c in sorted(totals.items()):
  result.append(dict(timeofday=period,cls=cls,dimension=dimension,bucket=value,**dict(c),recall={k:c[k+'_tp']/c['objects'] for k in methods}))
 write(ROOT/'error_diagnosis.json',dict(status='POST_TEST_DESCRIPTIVE_DIAGNOSIS_ONLY_NOT_RELEASE_EVIDENCE',confidence=.25,iou=.5,network_input=320,foreground_content=320*192,input_dimension_mapping='400x240 target boxes multiplied by0.8. Letterbox adds64 pixels vertically but does not enlarge objects.',brightness={k:dict(v) for k,v in light.items()},objects=result,first20_missed_person_metadata_order=examples,source_result_sha256=sha(ROOT/'fresh_complete.json'),no_checkpoint_or_threshold_reselection=True,hardware_access=False))
 print('TWILIGHT_POST_TEST_ERROR_DIAGNOSIS_DONE',dict(light),flush=True)

if __name__=='__main__':main()
