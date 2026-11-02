"""Freeze prior-exposure ledger and unused-source pool before fresh inference."""
import collections,json,hashlib
from road_viewadapt_common import *

def main():
 assert (ROOT/'protocol.json').exists() and not (ROOT/'holdout_exclusions.json').exists()
 patterns=['road_*/dataset/manifest.json','road_*/dataset/selection.json','road_*/fresh/manifest.json','road_*/fresh_selection.json','road_*/quality/fresh_selection.json','road_*/screened_candidates.json','road_*/extra_training_selection.json','road_*/training_manifest.json',
           'road_*/confirmation/fresh/manifest.json','road_*/confirmation/screened_candidates.json','road_*/training_selection.json']
 files=sorted({p for pat in patterns for p in BASE.glob(pat)})
 names=set();groups=set();hashes=set();sources={}
 def collect(v):
  if isinstance(v,list):
   for x in v:collect(x)
  elif isinstance(v,dict):
   name=v.get('name',v.get('file_name',''))
   if isinstance(name,str) and name.endswith('.jpg'):
    name=Path(name).name;names.add(name);groups.add(v.get('group',name.split('-')[0]))
    if v.get('image_sha256'):hashes.add(v['image_sha256'])
   for x in v.values():
    if isinstance(x,(dict,list)):collect(x)
 for p in files:
  collect(read(p));sources[str(p)]=sha(p)
 image_paths={Path(r['rfilename']).name:r['rfilename'] for r in read(DATA/'BDD100K_repo.json')['siblings'] if r['rfilename'].endswith('.jpg') and '/100k/train/' in r['rfilename']}
 candidates=[]
 for p in sorted((DATA/'source_metadata').glob('train_*.jsonl')):
  for line in p.read_text().splitlines():
   r=json.loads(line);name=r['file_name'];group=name.split('-')[0]
   if group in groups or name not in image_paths or r['label'] not in ['night','daytime']:continue
   candidates.append(dict(name=name,group=group,timeofday=r['label'],official_split='train',image_path=image_paths[name],rank=hashlib.sha256((str(SEED+1)+'|'+name).encode()).hexdigest()))
 write(ROOT/'holdout_exclusions.json',dict(status='EXPOSURE_LEDGER_FROZEN_BEFORE_ANY_FRESH_PREDICTIONS',sources=sources,names=sorted(names),groups=sorted(groups),image_hashes=sorted(hashes),unused_source='Official train pool, excluding all recorded prior training/evaluation/brightness-screening prefix groups and exact image hashes. No candidate predictions used.',candidate_period_counts=dict(collections.Counter(r['timeofday'] for r in candidates)),protocol_sha256=sha(ROOT/'protocol.json')))
 write(ROOT/'holdout_pool.json',sorted(candidates,key=lambda r:r['rank']))
 print('VIEWADAPT_UNUSED_SOURCE_POOL',len(candidates),dict(collections.Counter(r['timeofday'] for r in candidates)),len(groups),'excluded groups',flush=True)

if __name__=='__main__':main()
