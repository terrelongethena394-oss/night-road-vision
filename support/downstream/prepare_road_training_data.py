"""Real BDD frames and original per-image boxes, conservatively grouped by prefix."""
from pathlib import Path
import collections,concurrent.futures as cf,hashlib,io,json,random,time,urllib.error,urllib.request
from PIL import Image
ROOT=Path('E:/FPGA_Enhance_Work/road_detection_20261026')
REV='69e9f9a60103df97e151e2606a6ad182db824f55'
BASE=f'https://huggingface.co/datasets/dronefreak/BDD100K/resolve/{REV}/'
SEED=2026102621
CLASSES={'person':0,'pedestrian':0,'car':1,'truck':2,'bus':3}
NAMES=['person','car','truck','bus']
QUOTAS={'train':{'night':1200,'dawn/dusk':400,'daytime':800},'val':{'night':160,'dawn/dusk':64,'daytime':96},'test':{'night':240,'dawn/dusk':96,'daytime':144}}
def sha(b):return hashlib.sha256(b).hexdigest()
def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def fetch(url):
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url,timeout=35) as r:return r.read()
        except urllib.error.HTTPError as e:
            if e.code==404:raise
            if attempt==4:raise
            time.sleep((20 if e.code==429 else 2)*(attempt+1))
        except Exception:
            if attempt==4:raise
            time.sleep(2*(attempt+1))
def main():
    data=ROOT/'dataset';data.mkdir(exist_ok=True)
    assert not (data/'complete.json').exists()
    repo=json.loads((ROOT/'BDD100K_repo.json').read_text())
    assert repo['sha']==REV
    image_paths={Path(a['rfilename']).name:a['rfilename'] for a in repo['siblings'] if a['rfilename'].endswith('.jpg') and '/100k/' in a['rfilename']}
    meta=[]
    for p in sorted((ROOT/'source_metadata').glob('*.jsonl')):
        split=p.name.split('_')[0]
        for line in p.read_text().splitlines():
            d=json.loads(line);name=d['file_name'];meta.append(dict(name=name,timeofday=d['label'],official_split=split,group=name.split('-')[0]))
    held_groups={d['group'] for d in meta if d['official_split']=='val'}
    pools=collections.defaultdict(list)
    for d in meta:
        if d['timeofday'] not in QUOTAS['train'] or d['name'] not in image_paths:continue
        if d['official_split']=='val':split='test'
        else:
            if d['group'] in held_groups:continue
            bucket=int(sha((str(SEED)+'|'+d['group']).encode())[:8],16)%100
            split='train' if bucket<85 else 'val'
        d={**d,'split':split,'rank':sha((str(SEED)+'|'+d['name']).encode()),'image_path':image_paths[d['name']]}
        pools[(split,d['timeofday'])].append(d)
    chosen=[]
    for split,periods in QUOTAS.items():
        for period,n in periods.items():
            candidates=sorted(pools[(split,period)],key=lambda d:d['rank'])
            assert len(candidates)>=n,(split,period,len(candidates),n)
            chosen.extend(candidates[:n])
    group_sets={s:{r['group'] for r in chosen if r['split']==s} for s in QUOTAS}
    for a,b in [('train','val'),('train','test'),('val','test')]:assert not group_sets[a]&group_sets[b]
    protocol=dict(status='FROZEN_SELECTION_BEFORE_DOWNLOAD_OR_TRAINING',seed=SEED,classes=NAMES,quotas=QUOTAS,selected=len(chosen),
                  source_revision=REV,source='Unofficial BDD100K mirror dronefreak/BDD100K, actual original-style per-image JSON; README layout does not match current files.',
                  grouping='All same first8 filename prefix stay in one split; original official-val prefix groups completely excluded from train/val. Test from original val; train/val from original train with deterministic prefix hash.',
                  grouping_limit='Prefix grouping is conservative, not proof that geographically related but differently named drives are independent. No GPS/session metadata available.',
                  no_pseudolabels=True,selection='Fixed metadata hash order within time-of-day strata, no detector-outcome filtering; missing annotations quarantined and reported, never filled using model outcomes.',
                  source_annotation_version='Original-style BDD2018 JSON with frames/objects and attributes, not claiming the revised Detection2020 release.',
                  scope='PC training/evaluation of a small real-road subset. No board deployment or SD modification. Dusk field also includes dawn.')
    if (data/'selection.json').exists():assert json.loads((data/'selection.json').read_text())==chosen
    else:write(data/'selection.json',chosen)
    write(data/'protocol.json',protocol)
    for split in QUOTAS:
        for kind in ['images','labels','annotations']:(data/kind/split).mkdir(parents=True,exist_ok=True)
    def item(r):
        split,name=r['split'],r['name'];annpath=data/'annotations'/split/(Path(name).stem+'.json')
        rel=r['image_path'].replace('images_100k/100k','labels/100k').rsplit('.',1)[0]+'.json'
        try:
            if not annpath.exists():annpath.write_bytes(fetch(BASE+rel))
        except urllib.error.HTTPError as e:
            if e.code==404:return dict(**r,status='QUARANTINED_MISSING_ORIGINAL_ANNOTATION',annotation_path=rel)
            raise
        try:annotation=json.loads(annpath.read_text())
        except json.JSONDecodeError:
            annpath.write_bytes(fetch(BASE+rel));annotation=json.loads(annpath.read_text())
        assert annotation['name']==Path(name).stem and annotation['attributes']['timeofday']==r['timeofday']
        ip=data/'images'/split/name
        if not ip.exists():ip.write_bytes(fetch(BASE+r['image_path']))
        try:image=Image.open(ip);image.load()
        except (OSError,ValueError):
            ip.write_bytes(fetch(BASE+r['image_path']));image=Image.open(ip);image.load()
        width,height=image.size
        assert (width,height)==(1280,720)
        labels=[];counts=[0]*4;invalid=0
        for o in annotation['frames'][0]['objects']:
            if o.get('category') not in CLASSES or 'box2d' not in o:continue
            b=o['box2d'];x1=max(0.,min(width,float(b['x1'])));x2=max(0.,min(width,float(b['x2'])));y1=max(0.,min(height,float(b['y1'])));y2=max(0.,min(height,float(b['y2'])))
            if x2<=x1 or y2<=y1:invalid+=1;continue
            k=CLASSES[o['category']];counts[k]+=1
            labels.append(f'{k} {(x1+x2)/(2*width):.9f} {(y1+y2)/(2*height):.9f} {(x2-x1)/width:.9f} {(y2-y1)/height:.9f}')
        lp=data/'labels'/split/(Path(name).stem+'.txt');lp.write_text('\n'.join(labels)+'\n' if labels else '',encoding='ascii')
        return dict(**r,status='READY',width=width,height=height,image_sha256=sha(ip.read_bytes()),annotation_path=rel,annotation_sha256=sha(annpath.read_bytes()),label_sha256=sha(lp.read_bytes()),class_counts=counts,invalid_boxes=invalid)
    results=[];start=time.monotonic()
    with cf.ThreadPoolExecutor(12) as pool:
        futures=[pool.submit(item,r) for r in chosen]
        for future in cf.as_completed(futures):
            results.append(future.result())
            if len(results)%100==0:
                print('BDD_REAL_DATA_FETCHED',len(results),'/',len(chosen),'seconds',round(time.monotonic()-start),flush=True)
                write(data/'download_progress.json',dict(done=len(results),total=len(chosen),seconds=time.monotonic()-start))
    results.sort(key=lambda d:(d['split'],d['name']));write(data/'manifest.json',results)
    ready=[r for r in results if r['status']=='READY'];summaries={}
    hashes={s:{r['image_sha256'] for r in ready if r['split']==s} for s in QUOTAS}
    for a,b in [('train','val'),('train','test'),('val','test')]:assert not hashes[a]&hashes[b],'Exact-image duplicate across splits'
    for split in QUOTAS:
        rs=[r for r in ready if r['split']==split];counts=[sum(r['class_counts'][i] for r in rs) for i in range(4)]
        assert len(rs)>=sum(QUOTAS[split].values())*.97 and min(counts)>=10,(split,len(rs),counts)
        summaries[split]=dict(images=len(rs),groups=len({r['group'] for r in rs}),time_of_day=dict(collections.Counter(r['timeofday'] for r in rs)),boxes=dict(zip(NAMES,counts)),empty_images=sum(not sum(r['class_counts']) for r in rs))
    yaml='path: '+data.as_posix()+'\ntrain: images/train\nval: images/val\ntest: images/test\nnc: 4\nnames: [person, car, truck, bus]\n'
    (data/'road4.yaml').write_text(yaml,encoding='ascii')
    complete=dict(status='REAL_BDD_FOUR_CLASS_DATASET_READY',splits=summaries,quarantined=len(results)-len(ready),source_revision=REV,fit_on_test=False,group_overlap=False,exact_image_overlap=False,download_seconds=time.monotonic()-start)
    write(data/'complete.json',complete);print('REAL_BDD_DATA_READY',json.dumps(complete),flush=True)
if __name__=='__main__':main()
