"""New user-priority contract; old stricter experiment failures stay unchanged."""
from pathlib import Path
import shutil,time
import numpy as np
import road_accuracy_common as ac
from road_numpy_eval import evaluate
from car_box_refine_common import BASE,ROOT as REF,read,write,sha
from evaluate_car_patch_verifier import cohorts
from evaluate_car_boxrefine import eligible,overlaps_strong,fuse_refined
ROOT=BASE/'road_car_balanced_20261030_r1'

def f1(m):return 2*m['tp']/(2*m['tp']+m['fp']+m['fn'])
def gates(a,b):
 return dict(ap=b['ap50']>=a['ap50']+.005,precision=b['precision']>=a['precision']-.002,
  recall=b['recall']>=a['recall']+.01,f1=f1(b)>=f1(a)+.005)

def raw_helpers(key,d):
 if key=='reused320':
  p=BASE/'road_brightness_route_20261030_r1/fresh_evaluation/routed_low/native'
  full={r['name']:r['detections'] for r in read(p/'global_raw.json')}
  tiles=[{r['name']:r['detections'] for r in read(p/f'tile_raw_{i}.json')} for i in range(3)]
 else:
  p=BASE/'road_car_zoom_20261030_r1/confirmation';full={r['name']:r['detections'] for r in read(p/'global_actual_c.json')}
  tiles=[{r['name']:ac.map_tile(r['detections'],*ac.TILES[i]).tolist() for r in read(p/f'raw{i}_actual_c.json')} for i in range(3)]
 return {r['name']:[np.asarray(v,np.float32).reshape(-1,6) for v in [full[r['name']],*[t[r['name']] for t in tiles]]] for r in d['manifest']}

def spatial_fuse(raw,views,helpers,match,blend,minimum):
 a=np.asarray(raw,np.float32).reshape(-1,6);strong=a[a[:,4]>=.25];extra=[]
 for pp in views:
  for p in np.asarray(pp,np.float32).reshape(-1,6):
   if not eligible(p,strong):continue
   total=p[:4].copy();denom=np.float32(1)
   for j,helper in enumerate(helpers):
    q=helper[(helper[:,5]==1)&(helper[:,4]>=minimum)]
    if not len(q):continue
    inter=np.maximum(0,np.minimum(p[2:4],q[:,2:4])-np.maximum(p[:2],q[:,:2])).prod(1)
    area=np.maximum(0,p[2:4]-p[:2]).prod();oa=np.maximum(0,q[:,2:4]-q[:,:2]).prod(1)
    iou=inter/(area+oa-inter+1e-9);k=int(np.argmax(iou))
    if iou[k]<match:continue
    weight=q[k,4]*np.float32(.5 if j==0 else 1.)
    total+=q[k,:4]*weight;denom+=weight
   b=p.copy();b[:4]=p[:4]*(np.float32(1)-np.float32(blend))+(total/denom)*np.float32(blend)
   if overlaps_strong(b,strong):continue
   b[4]*=np.float32(.65);extra.append(b)
 return ac.nms_numpy(np.concatenate([a,np.asarray(extra,np.float32).reshape(-1,6)]),.6,300)

def main():
 assert not ROOT.exists() and not read(REF/'selected.json')['qualified'];ROOT.mkdir();(ROOT/'source').mkdir()
 protocol=dict(status='NEW_USER_BALANCE_PROTOCOL_FROZEN_BEFORE_SPATIAL_STUDY_AND_UNUSED_CONFIRMATION',
  user_priority='两者平衡：尽量多检出，同时控制误检',
  relation='Previous1ppAP and25%extraFP experiments remain failed. This is a new balanced delivery hypothesis,not a reinterpretation of old confirmation.',
  candidates='Already evaluated24 box-refiner variants plus8 new coordinate-consensus variants. All selection uses explicitly reused480 development images.',
  spatial='Keep old4view boxes. For each added zoom proposal, one best-overlap support per raw view:IoU.3/.5,minscore.03/.1;coordinate weight=confidence,globalweight.5,tileweight1,candidateweight1. Blend.5/1;score stays original*.65.',
  balanced_gates='Separately on reused320/reused160:AP>=baseline+.5pp,precision>=baseline-.2pp,recall>=baseline+1pp,F1>=baseline+.5pp.',
  selection='Max mean F1 among all passing candidates;tie byAP then lower extra compute. Freeze one before new holdout.',
  fresh_policy='New240low+64brighter,exclude all recorded sources including nested confirmation manifests/screened images. Same balanced gates on low240,paired99%AP-gain CI lower>0. Brighter outputs unchanged. No test-driven replacement.',
  source_old_rejected_selection_sha256=sha(REF/'selected.json'),hardware_access=False,sd_written=False)
 write(ROOT/'protocol.json',protocol);datasets=cohorts();baseline={};records=[];stored={};begin=time.monotonic()
 for key,d in datasets.items():baseline[key]=evaluate([d['base'][r['name']] for r in d['manifest']])['classes']['car']
 for previous in read(REF/'selected.json')['records']:
  scores=previous['scores'];gg={key:gates(baseline[key],m) for key,m in scores.items()}
  records.append(dict(family='box_refiner',tag=previous['tag'],source=previous,scores=scores,gates=gg,qualified=all(all(g.values()) for g in gg.values())))
 helpers={key:raw_helpers(key,d) for key,d in datasets.items()}
 for match in [.3,.5]:
  for blend in [.5,1.]:
   for minimum in [.03,.1]:
    scores={};gg={};outputs={};tag=f'm{match}_b{blend}_t{minimum}'
    for key,d in datasets.items():
     rows=[]
     for r in d['manifest']:
      name=r['name'];pred=spatial_fuse(d['base'][name]['detections'],d['views'][name],helpers[key][name],match,blend,minimum)
      rows.append(dict(name=name,ground_truth=d['base'][name]['ground_truth'],detections=pred.tolist()))
     scores[key]=evaluate(rows)['classes']['car'];gg[key]=gates(baseline[key],scores[key]);outputs[key]=rows
    good=all(all(g.values()) for g in gg.values());record=dict(family='spatial_consensus',tag=tag,params=dict(match=match,blend=blend,minimum=minimum),scores=scores,gates=gg,qualified=good)
    records.append(record);stored[tag]=outputs
    print('BALANCED_CAR_SPATIAL',tag,good,{key:(round(m['ap50'],5),round(f1(m),5),m['tp'],m['fp']) for key,m in scores.items()},'seconds',round(time.monotonic()-begin),flush=True)
 good=[r for r in records if r['qualified']]
 chosen=max(good,key=lambda r:(np.mean([f1(m) for m in r['scores'].values()]),np.mean([m['ap50'] for m in r['scores'].values()]),r['family']=='spatial_consensus')) if good else None
 write(ROOT/'selected.json',dict(status='ONE_BALANCED_CANDIDATE_REQUIRES_C_AND_UNUSED_CONFIRMATION' if chosen else 'NO_BALANCED_CANDIDATE_KEEP_ABI27',qualified=chosen is not None,
  chosen=chosen,records=records,baselines=baseline,protocol_sha256=sha(ROOT/'protocol.json'),previous_failed_experiments_preserved=True,fresh_inference=False,hardware_access=False,sd_written=False))
 if chosen:
  if chosen['family']=='spatial_consensus':outputs=stored[chosen['tag']]
  else:
   s=chosen['source'];outputs={}
   for key,d in datasets.items():
    pred=read(REF/'development'/f"epoch{s['epoch']}_{key}_outputs.json")
    outputs[key]=[dict(name=r['name'],ground_truth=d['base'][r['name']]['ground_truth'],detections=fuse_refined(d['base'][r['name']]['detections'],d['views'][r['name']],pred[r['name']],s['strength'],s['cap'],s['class_gate']).tolist()) for r in d['manifest']]
  for key,rows in outputs.items():write(ROOT/f'chosen_{key}_predictions.json',rows)
 shutil.copy2(Path(__file__),ROOT/'source'/Path(__file__).name)
 print('BALANCED_CAR_SELECTION',None if chosen is None else (chosen['family'],chosen['tag']),flush=True)

if __name__=='__main__':main()
