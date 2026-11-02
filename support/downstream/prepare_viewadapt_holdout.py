"""Prepare unused-source holdout by raw brightness, without detector inference."""
import concurrent.futures as cf,collections,hashlib,shutil,urllib.error
import cv2,numpy as np
from road_viewadapt_common import *
from prepare_road_training_data import fetch,CLASSES
URL='https://huggingface.co/datasets/dronefreak/BDD100K/resolve/69e9f9a60103df97e151e2606a6ad182db824f55/'
RULES=[dict(cohort='low',timeofday='night',images=160,minimum=0,maximum=48),dict(cohort='brighter',timeofday='daytime',images=64,minimum=70,maximum=255)]

def main():
 assert not (ROOT/'fresh_protocol.json').exists() and (ROOT/'holdout_exclusions.json').exists()
 ledger=read(ROOT/'holdout_exclusions.json');pool=read(ROOT/'holdout_pool.json')
 write(ROOT/'fresh_protocol.json',dict(status='HOLDOUT_SELECTION_FROZEN_BEFORE_ANY_NEW_MODEL_INFERENCE',cohorts=RULES,exclusions_sha256=sha(ROOT/'holdout_exclusions.json'),pool_sha256=sha(ROOT/'holdout_pool.json'),selection='Fixed metadata hash order, first raw-brightness-eligible image per previously unexposed prefix group and exact hash. No predictions or object-count filtering. Skip missing original annotations with receipt, do not replace labels using predictions.',accuracy_gates=read(ROOT/'protocol.json')['fresh_policy'],checkpoint_selection='Only reused development640; no access to these predictions until one candidate selected and actual C development verified.',brightness_definition='Unenhanced sensor-proxy400 meanY=(54R+183G+19B)/256, not measured physical lux. Original metadata period labels may be imperfect.',hardware_access=False,sd_written=False))
 for kind in ['images','labels','annotations']:(ROOT/'fresh'/kind).mkdir(parents=True)
 seen=set(ledger['groups']);hashes=set(ledger['image_hashes']);selected=[];examined=[];missing=[]
 def screen(r):
  data=fetch(URL+r['image_path']);digest=hashlib.sha256(data).hexdigest();im=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR);assert im is not None and im.shape==(720,1280,3)
  sensor=cv2.resize(im[:,:,::-1],(800,480),interpolation=cv2.INTER_LINEAR);a=sensor.astype(np.uint16);raw=((a[::2,::2]+a[::2,1::2]+a[1::2,::2]+a[1::2,1::2]+2)//4).astype(np.uint8);z=raw.astype(np.uint32);mean=float(((54*z[:,:,0]+183*z[:,:,1]+19*z[:,:,2])/256).mean())
  return r,data,digest,mean
 def annotate(item):
  r,data,digest,mean,cohort=item;stem=Path(r['name']).stem;rel=r['image_path'].replace('images_100k/100k','labels/100k').rsplit('.',1)[0]+'.json'
  try:ann=fetch(URL+rel)
  except urllib.error.HTTPError as e:
   if e.code==404:return None,r['name']
   raise
  import json
  a=json.loads(ann);assert a['name']==stem and a['attributes']['timeofday']==r['timeofday'];labels=[];counts=[0]*4
  for o in a['frames'][0]['objects']:
   if o.get('category') not in CLASSES or 'box2d' not in o:continue
   b=o['box2d'];x1=np.clip(float(b['x1']),0,1280);x2=np.clip(float(b['x2']),0,1280);y1=np.clip(float(b['y1']),0,720);y2=np.clip(float(b['y2']),0,720)
   if x2<=x1 or y2<=y1:continue
   k=CLASSES[o['category']];counts[k]+=1;labels.append(f'{k} {(x1+x2)/2560:.9f} {(y1+y2)/1440:.9f} {(x2-x1)/1280:.9f} {(y2-y1)/720:.9f}')
  (ROOT/'fresh/images'/r['name']).write_bytes(data);ap=ROOT/'fresh/annotations'/(stem+'.json');ap.write_bytes(ann);lp=ROOT/'fresh/labels'/(stem+'.txt');lp.write_text('\n'.join(labels)+'\n' if labels else '',encoding='ascii')
  return dict(**r,image_sha256=digest,mean_y=mean,cohort=cohort,class_counts=counts,annotation_sha256=sha(ap),label_sha256=sha(lp)),None
 with cf.ThreadPoolExecutor(8) as workers:
  for rule in RULES:
   count=0;candidates=[r for r in pool if r['timeofday']==rule['timeofday']]
   for start in range(0,len(candidates),24):
    eligible=[]
    for r,data,digest,mean in workers.map(screen,candidates[start:start+24]):
     examined.append(dict(name=r['name'],group=r['group'],image_sha256=digest,mean_y=mean,cohort=rule['cohort']))
     if r['group'] in seen or digest in hashes or not rule['minimum']<=mean<=rule['maximum']:continue
     seen.add(r['group']);hashes.add(digest);eligible.append((r,data,digest,mean,rule['cohort']))
    for rec,absent in workers.map(annotate,eligible[:rule['images']-count]):
     if absent:missing.append(absent);continue
     selected.append(rec);count+=1
    write(ROOT/'screened_candidates.json',examined);write(ROOT/'fresh_download_progress.json',dict(cohort=rule['cohort'],done=count,target=rule['images'],missing_annotations=missing))
    print('VIEWADAPT_HOLDOUT_PREPARED',rule['cohort'],count,rule['images'],flush=True)
    if count==rule['images']:break
   assert count==rule['images'],rule
 total=sum(r['images'] for r in RULES)
 assert len(selected)==total and len({r['group'] for r in selected})==total and len({r['image_sha256'] for r in selected})==total
 assert not {r['group'] for r in selected}&set(ledger['groups']) and not {r['image_sha256'] for r in selected}&set(ledger['image_hashes'])
 write(ROOT/'fresh/manifest.json',selected);write(ROOT/'fresh/complete.json',dict(status=f'UNUSED{total}_HOLDOUT_RAW_BRIGHTNESS_SELECTED_NO_PREDICTIONS',manifest_sha256=sha(ROOT/'fresh/manifest.json'),cohorts=dict(collections.Counter(r['cohort'] for r in selected)),missing_annotations=missing,hardware_access=False))
 shutil.copy2(Path(__file__),ROOT/'source'/Path(__file__).name);print('VIEWADAPT_UNUSED_HOLDOUT_READY',total,flush=True)

if __name__=='__main__':main()
