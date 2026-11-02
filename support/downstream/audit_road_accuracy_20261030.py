from pathlib import Path
import collections,json
BASE=Path('E:/FPGA_Enhance_Work')

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
    used=[];sources=[]
    paths=[BASE/'road_detection_20261026/dataset/manifest.json']
    paths += sorted(BASE.glob('road_*/fresh/manifest.json'))
    paths += [BASE/'road_twilight_consistency_20261027/dataset/manifest.json',BASE/'road_light_20261027/dataset/manifest.json']
    for p in paths:
        if not p.exists():continue
        rows=read(p)
        if not isinstance(rows,list):continue
        rows=[r for r in rows if isinstance(r,dict) and 'name' in r]
        used+=rows;sources.append(dict(path=str(p),rows=len(rows)))
    groups={r.get('group',r['name'].split('-')[0]) for r in used}
    pool=[]
    for p in (BASE/'road_detection_20261026/source_metadata').glob('val_*.jsonl'):
        for line in p.read_text().splitlines():
            r=json.loads(line)
            if r['file_name'].split('-')[0] not in groups:pool.append(r)
    print('USED_GROUP_AUDIT',json.dumps(dict(sources=sources,unique_names=len({r['name'] for r in used}),unique_groups=len(groups),unused_val_periods=dict(collections.Counter(r['label'] for r in pool))),ensure_ascii=False),flush=True)
    for root in ['road_roi_guard_20261028','road_roi_spatial_verifier_20261028','road_twilight_consistency_20261027']:
        for n in ['selected.json','complete.json','fresh_complete.json']:
            p=BASE/root/n
            if not p.exists():continue
            d=read(p);print('PRIOR_KEYS',str(p),list(d.keys()),flush=True)
            for k in ['policy','gates','deployment_decision','validation_accepted','accepted','baseline','candidate']:
                if k in d:
                    v=d[k]
                    if isinstance(v,dict) and 'by_time' in v:v={t:dict(map50=z['mAP50'],car=z['classes']['car'],person=z['classes']['person']) for t,z in v['by_time'].items()}
                    print('PRIOR',root,n,k,json.dumps(v)[:5000],flush=True)

if __name__=='__main__':main()
