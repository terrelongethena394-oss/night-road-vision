"""Freeze evaluation and reserve metadata-only unseen examples before inference."""
from pathlib import Path
import collections,concurrent.futures as cf,json,shutil
from PIL import Image
from road_accuracy_common import *
from prepare_road_training_data import fetch,CLASSES

HERE=Path(__file__).resolve().parent
URL='https://huggingface.co/datasets/dronefreak/BDD100K/resolve/69e9f9a60103df97e151e2606a6ad182db824f55/'
def main():
    assert not ROOT.exists();ROOT.mkdir();(ROOT/'source').mkdir()
    sources=[DATA/'dataset/manifest.json',BASE/'road_twilight_consistency_20261027/dataset/manifest.json',BASE/'road_light_20261027/dataset/manifest.json']
    sources+=list(BASE.glob('road_*/fresh/manifest.json'))+list(BASE.glob('road_*/fresh_selection.json'))+list(BASE.glob('road_*/quality/fresh_selection.json'))
    used=[]
    for p in sources:
        if not p.exists():continue
        d=read(p)
        if isinstance(d,list):used.extend(r for r in d if isinstance(r,dict) and 'name' in r)
    groups={r.get('group',r['name'].split('-')[0]) for r in used}
    hashes={r['image_sha256'] for r in used if 'image_sha256' in r}
    image_paths={Path(r['rfilename']).name:r['rfilename'] for r in read(DATA/'BDD100K_repo.json')['siblings'] if r['rfilename'].endswith('.jpg') and '/100k/' in r['rfilename']}
    pools=collections.defaultdict(list)
    for p in sorted((DATA/'source_metadata').glob('val_*.jsonl')):
        for line in p.read_text().splitlines():
            r=json.loads(line);name=r['file_name'];group=name.split('-')[0]
            if group in groups or name not in image_paths or r['label'] not in QUOTA:continue
            pools[r['label']].append(dict(name=name,group=group,timeofday=r['label'],image_path=image_paths[name],rank=__import__('hashlib').sha256((str(SEED)+'|'+name).encode()).hexdigest()))
    selected=[];reserved=set()
    for period,n in QUOTA.items():
        for r in sorted(pools[period],key=lambda r:r['rank']):
            if r['group'] in reserved:continue
            selected.append(r);reserved.add(r['group'])
            if sum(x['timeofday']==period for x in selected)==n:break
        assert sum(x['timeofday']==period for x in selected)==n,(period,len(pools[period]))
    protocol=dict(status='FROZEN_BEFORE_DEVELOPMENT_INFERENCE',date='2026-10-30',seed=SEED,primary='night car AP50 on full labelled images, not number of boxes',secondary=['night vehicle macroAP50','night four-class mAP50','car precision/recall at confidence .25 and IoU .5','person preservation','daytime regression'],known_development='Previously used original320 validation, never called blind testing',new_holdout_quotas=QUOTA,holdout_selection='Officialval unseen first8 groups, deterministic metadata hash order, no prediction filtering. Only32 unused dawn/dusk groups remain; dusk analysis descriptive.',excluded_manifests={str(p):sha(p) for p in sources if p.exists()},weights_sha256=sha(WEIGHTS),weights_f32_sha256=sha(APP/'runtime/weights.f32'),input='Original JPEG -> RGB800x480 bilinear -> RGB400x240 rounded 2x2 mean, no RGB565; exact board integer320 preprocessing.',views=dict(global_modes=['raw','gamma080','gamma065','guard22'],detail_modes=['raw','gamma080','gamma065'],tiles=TILES),fusion=dict(vehicle_only=True,weights=[.3,.45,.6,.75],dedup_iou=.3,dedup_containment=.8,roi_min_conf=.05,nms_iou=.6),selection='Choose on320 only: night car AP50 +>=1pp; overall4class mAP50 no drop>0.5pp; night car precision no drop>1pp and recall nondecreasing; daytime car AP no drop>1pp. Among eligible maximize night car AP50, prefer fewer passes within0.5pp. Freeze before fresh inference.',fresh_acceptance='Paired image-group bootstrap1000,97.5% interval for primary difference candidate-raw must be above0; point carAP gain>=1pp; car precision no drop>1pp; all/night4class no drop>0.5pp; person outputs unchanged for vehicle-only supplement. Two predeclared comparisons: selected-raw and any enhanced-input selected vs same raw-view geometry. No fresh-driven reselection.',enhancement_attribution='Only same-network/same-view raw-vs-enhanced input comparison supports enhancement-caused gain. More detail/extra passes do not count as enhancement benefit.',hardware_access=False,sd_written=False)
    write(ROOT/'protocol.json',protocol);write(ROOT/'fresh_selection.json',selected)
    for p in HERE.glob('*road_accuracy*.py'):shutil.copy2(p,ROOT/'source'/p.name)
    write(ROOT/'used_group_audit.json',dict(names=len({r['name'] for r in used}),groups=len(groups),available={k:len(v) for k,v in pools.items()},holdout_overlap=False))
    for kind in ['images','labels','annotations']:(ROOT/'fresh'/kind).mkdir(parents=True)
    def one(r):
        stem=Path(r['name']).stem;ap=ROOT/'fresh/annotations'/(stem+'.json');ip=ROOT/'fresh/images'/r['name']
        rel=r['image_path'].replace('images_100k/100k','labels/100k').rsplit('.',1)[0]+'.json'
        ap.write_bytes(fetch(URL+rel));a=read(ap)
        assert a['name']==stem and a['attributes']['timeofday']==r['timeofday']
        ip.write_bytes(fetch(URL+r['image_path']));im=Image.open(ip);im.load();assert im.size==(1280,720) and sha(ip) not in hashes
        labels=[];counts=[0]*4
        for o in a['frames'][0]['objects']:
            if o.get('category') not in CLASSES or 'box2d' not in o:continue
            b=o['box2d'];x1=max(0.,min(1280.,float(b['x1'])));x2=max(0.,min(1280.,float(b['x2'])));y1=max(0.,min(720.,float(b['y1'])));y2=max(0.,min(720.,float(b['y2'])))
            if x2<=x1 or y2<=y1:continue
            k=CLASSES[o['category']];counts[k]+=1;labels.append(f'{k} {(x1+x2)/2560:.9f} {(y1+y2)/1440:.9f} {(x2-x1)/1280:.9f} {(y2-y1)/720:.9f}')
        lp=ROOT/'fresh/labels'/(stem+'.txt');lp.write_text('\n'.join(labels)+'\n' if labels else '',encoding='ascii')
        return dict(**r,image_sha256=sha(ip),annotation_sha256=sha(ap),label_sha256=sha(lp),class_counts=counts)
    records=[]
    with cf.ThreadPoolExecutor(8) as pool:
        for r in pool.map(one,selected):
            records.append(r)
            if len(records)%48==0:print('ACCURACY_HOLDOUT_FETCHED',len(records),len(selected),flush=True);write(ROOT/'fetch_progress.json',dict(done=len(records),total=len(selected)))
    assert len({r['image_sha256'] for r in records})==len(records)
    write(ROOT/'fresh/manifest.json',records);write(ROOT/'fresh/complete.json',dict(status='672_NEW_GROUPS_RESERVED_NO_MODEL_INFERENCE',images=len(records),periods=dict(collections.Counter(r['timeofday'] for r in records)),sha256=sha(ROOT/'fresh/manifest.json')))
    print('ACCURACY_FRESH_READY',len(records),flush=True)

if __name__=='__main__':main()
