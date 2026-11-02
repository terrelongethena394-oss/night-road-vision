"""Freeze a fresh brightness-defined confirmation without prediction filtering."""
import collections,concurrent.futures as cf,hashlib,json,shutil,sys
from road_classwise_common import *
from road_accuracy_common import sensor400
from audit_road_accuracy_light import mean_y
from prepare_road_training_data import fetch,CLASSES
import cv2
ROOT=BASE/'road_classwise_20261030_r2'
URL='https://huggingface.co/datasets/dronefreak/BDD100K/resolve/69e9f9a60103df97e151e2606a6ad182db824f55/'
COHORTS=[dict(cohort='low',timeofday='night',images=240,minimum=0,maximum=48),dict(cohort='brighter',timeofday='daytime',images=96,minimum=70,maximum=255)]

def main():
 if (ROOT/'fresh/complete.json').exists():print('CLASSWISE_CONFIRMATION_DATA_ALREADY_FROZEN',flush=True);return
 chosen=read(ROOT/'selected.json');assert chosen['qualified'] and (ROOT/'c_complete.json').exists()
 resume='--resume-available205' in sys.argv
 if (ROOT/'fresh_protocol.json').exists():
  assert resume and not (ROOT/'native').exists() and not (ROOT/'fresh/manifest.json').exists()
  assert read(ROOT/'fresh_protocol.json')['selected_sha256']==sha(ROOT/'selected.json')
  shutil.copy2(ROOT/'fresh_protocol.json',ROOT/'fresh_protocol_initial240.json')
  COHORTS[0]['images']=205
  write(ROOT/'sample_size_addendum.json',dict(initial_low=240,available_low=205,selected_low=205,brighter=96,reason='All remaining eligible unused groups exhausted under unchanged raw mean<=48; no model predictions or annotation outcomes consumed. Use all205 rather than relaxing brightness/deduplication.',changed_before_any_predictions=True,quality_gates_unchanged=True,selected_sha256=sha(ROOT/'selected.json')))
 sources=[DATA/'dataset/manifest.json',BASE/'road_twilight_consistency_20261027/dataset/manifest.json',BASE/'road_light_20261027/dataset/manifest.json']+list(BASE.glob('road_*/fresh/manifest.json'))+list(BASE.glob('road_*/fresh_selection.json'))+list(BASE.glob('road_*/quality/fresh_selection.json'))+list(BASE.glob('road_*/screened_candidates.json'))
 sources=[p for p in sources if p.exists() and not p.resolve().is_relative_to(ROOT.resolve())]
 used=[]
 for p in sources:
  d=read(p)
  if isinstance(d,list):used.extend(r for r in d if isinstance(r,dict) and 'name' in r)
 groups={r.get('group',r['name'].split('-')[0]) for r in used};hashes={r['image_sha256'] for r in used if 'image_sha256' in r}
 image_paths={Path(r['rfilename']).name:r['rfilename'] for r in read(DATA/'BDD100K_repo.json')['siblings'] if r['rfilename'].endswith('.jpg') and '/100k/' in r['rfilename']}
 pools=collections.defaultdict(list)
 for p in sorted((DATA/'source_metadata').glob('val_*.jsonl')):
  for line in p.read_text().splitlines():
   r=json.loads(line);name=r['file_name'];group=name.split('-')[0]
   if group in groups or name not in image_paths:continue
   pools[r['label']].append(dict(name=name,group=group,timeofday=r['label'],image_path=image_paths[name],rank=hashlib.sha256((str(SEED+31)+'|'+name).encode()).hexdigest()))
 protocol=dict(status='FROZEN_BEFORE_SCREENING_OR_NEW_PREDICTIONS',cohorts=COHORTS,selected_sha256=sha(ROOT/'selected.json'),weights=chosen['chosen']['weights'],source_period_labels_known_imperfect=True,brightness='Unenhanced400x240 meanY=(54R+183G+19B)/256; not measured lux or independently confirmed physical time.',selection='Fixed metadata hash order. Previously unused prefix group and exact image hash; one per group, first eligible by raw brightness. No object-count or prediction filters.',excluded={str(p):sha(p) for p in sources},acceptance='All existing development gates separately on low and brighter cohorts: car AP/precision/recall drop<=0.1pp, fourclass AP drop<=0.5pp, rare-class AP/TP no worse than raw single under declared gates, truck+bus TP>=80%current and FP<=75%current. Paired-image99% CI for FP-per-image reduction above0 separately in both cohorts. No fresh-driven reselection.',hardware_access=False,sd_written=False)
 write(ROOT/'fresh_protocol.json',protocol)
 for kind in ['images','labels','annotations']:(ROOT/'fresh'/kind).mkdir(parents=True,exist_ok=resume)
 seen=set(groups);examined=[];selected=[]
 def screen(r):
  cached=ROOT/'fresh/images'/r['name'];data=cached.read_bytes() if cached.exists() else fetch(URL+r['image_path']);digest=hashlib.sha256(data).hexdigest();bgr=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR);assert bgr is not None and bgr.shape==(720,1280,3)
  sensor=cv2.resize(bgr[:,:,::-1],(800,480),interpolation=cv2.INTER_LINEAR);a=sensor.astype(np.uint16);raw=((a[0::2,0::2]+a[0::2,1::2]+a[1::2,0::2]+a[1::2,1::2]+2)//4).astype(np.uint8)
  return r,data,digest,mean_y(raw)
 with cf.ThreadPoolExecutor(8) as pool:
  for rule in COHORTS:
   count=0;candidates=sorted(pools[rule['timeofday']],key=lambda r:r['rank']);assert len(candidates)>=rule['images']
   for start in range(0,len(candidates),32):
    for r,data,digest,brightness in pool.map(screen,candidates[start:start+32]):
     examined.append(dict(name=r['name'],group=r['group'],image_sha256=digest,mean_y=brightness,screened_cohort=rule['cohort']))
     if count>=rule['images'] or r['group'] in seen or digest in hashes or not rule['minimum']<=brightness<=rule['maximum']:continue
     seen.add(r['group']);hashes.add(digest);(ROOT/'fresh/images'/r['name']).write_bytes(data);selected.append(dict(**r,image_sha256=digest,mean_y=brightness,cohort=rule['cohort']));count+=1
    write(ROOT/'screened_candidates.json',examined);print('CLASSWISE_FRESH_SCREEN',rule['cohort'],count,rule['images'],flush=True)
    if count==rule['images']:break
   assert count==rule['images'],rule
 def annotate(r):
  stem=Path(r['name']).stem;rel=r['image_path'].replace('images_100k/100k','labels/100k').rsplit('.',1)[0]+'.json';ap=ROOT/'fresh/annotations'/(stem+'.json');ap.write_bytes(fetch(URL+rel));a=read(ap);assert a['name']==stem and a['attributes']['timeofday']==r['timeofday']
  labels=[];counts=[0]*4
  for o in a['frames'][0]['objects']:
   if o.get('category') not in CLASSES or 'box2d' not in o:continue
   b=o['box2d'];x1=max(0.,min(1280.,float(b['x1'])));x2=max(0.,min(1280.,float(b['x2'])));y1=max(0.,min(720.,float(b['y1'])));y2=max(0.,min(720.,float(b['y2'])))
   if x2<=x1 or y2<=y1:continue
   k=CLASSES[o['category']];counts[k]+=1;labels.append(f'{k} {(x1+x2)/2560:.9f} {(y1+y2)/1440:.9f} {(x2-x1)/1280:.9f} {(y2-y1)/720:.9f}')
  lp=ROOT/'fresh/labels'/(stem+'.txt');lp.write_text('\n'.join(labels)+'\n' if labels else '',encoding='ascii')
  return dict(**r,class_counts=counts,annotation_sha256=sha(ap),label_sha256=sha(lp))
 with cf.ThreadPoolExecutor(8) as pool:records=list(pool.map(annotate,selected))
 total=sum(c['images'] for c in COHORTS)
 assert len(records)==total and len({r['group'] for r in records})==total and len({r['image_sha256'] for r in records})==total
 write(ROOT/'fresh/manifest.json',records);write(ROOT/'fresh/complete.json',dict(status=f'FRESH{total}_FROZEN_BEFORE_ANY_PREDICTIONS',cohorts=dict(collections.Counter(r['cohort'] for r in records)),manifest_sha256=sha(ROOT/'fresh/manifest.json'),hardware_access=False))
 shutil.copy2(Path(__file__),ROOT/'source'/Path(__file__).name);print('CLASSWISE_FRESH_READY',total,flush=True)
if __name__=='__main__':main()
