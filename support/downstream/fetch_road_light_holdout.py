"""Fetch metadata-frozen new groups without any model or quality-based filtering."""
from pathlib import Path
import concurrent.futures as cf,collections,time
from PIL import Image
from road_light_common import ROOT,BASE,NAMES,read,write,sha
from prepare_road_training_data import fetch,CLASSES
URL='https://huggingface.co/datasets/dronefreak/BDD100K/resolve/69e9f9a60103df97e151e2606a6ad182db824f55/'
def main():
    start=time.monotonic()
    while not (ROOT/'fresh_selection.json').exists():
        if time.monotonic()-start>600:raise TimeoutError('Selection not ready')
        time.sleep(1)
    old=read(BASE/'dataset/manifest.json')+read(Path('E:/FPGA_Enhance_Work/road_joint_adapt_20261026/fresh/manifest.json'))
    hashes={r['image_sha256'] for r in old};groups={r['group'] for r in old};selected=read(ROOT/'fresh_selection.json')
    assert len(selected)==480 and len({r['group'] for r in selected})==480 and not ({r['group'] for r in selected}&groups)
    for name in ['images','labels','annotations']:(ROOT/'fresh'/name).mkdir(parents=True,exist_ok=True)
    assert not (ROOT/'fresh/complete.json').exists()
    def one(r):
        stem=Path(r['name']).stem;ap=ROOT/'fresh/annotations'/(stem+'.json');ip=ROOT/'fresh/images'/r['name']
        rel=r['image_path'].replace('images_100k/100k','labels/100k').rsplit('.',1)[0]+'.json'
        if not ap.exists():ap.write_bytes(fetch(URL+rel))
        a=read(ap);assert a['name']==stem and a['attributes']['timeofday']==r['timeofday'] and len(a['frames'])==1 and a['frames'][0]['timestamp']==10000
        if not ip.exists():ip.write_bytes(fetch(URL+r['image_path']))
        image=Image.open(ip);image.load();assert image.size==(1280,720);digest=sha(ip);assert digest not in hashes
        labels=[];counts=[0]*4;invalid=0
        for o in a['frames'][0]['objects']:
            if o.get('category') not in CLASSES or 'box2d' not in o:continue
            box=o['box2d'];x1=max(0.,min(1280.,float(box['x1'])));x2=max(0.,min(1280.,float(box['x2'])));y1=max(0.,min(720.,float(box['y1'])));y2=max(0.,min(720.,float(box['y2'])))
            if x2<=x1 or y2<=y1:invalid+=1;continue
            k=CLASSES[o['category']];counts[k]+=1;labels.append(f'{k} {(x1+x2)/2560:.9f} {(y1+y2)/1440:.9f} {(x2-x1)/1280:.9f} {(y2-y1)/720:.9f}')
        lp=ROOT/'fresh/labels'/(stem+'.txt');lp.write_text('\n'.join(labels)+'\n' if labels else '',encoding='ascii')
        return {**r,'status':'READY','image_sha256':digest,'annotation_sha256':sha(ap),'label_sha256':sha(lp),'class_counts':counts,'invalid_boxes':invalid}
    records=[]
    with cf.ThreadPoolExecutor(12) as pool:
        for r in pool.map(one,selected):
            records.append(r)
            if len(records)%80==0:print('LIGHT_UNSEEN_GROUP_HOLDOUT_FETCHED',len(records),flush=True)
    write(ROOT/'fresh/manifest.json',records);write(ROOT/'fresh/complete.json',dict(status='LIGHT_UNSEEN_HOLDOUT_READY_BEFORE_ANY_MODEL_INFERENCE',images=480,groups=480,
       periods=dict(collections.Counter(r['timeofday'] for r in records)),objects=dict(zip(NAMES,[sum(r['class_counts'][i] for r in records) for i in range(4)])),
       previous_group_overlap=False,previous_exact_image_overlap=False,any_model_inference=False,manifest_sha256=sha(ROOT/'fresh/manifest.json')))
    print('LIGHT_FRESH_HOLDOUT_READY',time.monotonic()-start,flush=True)
if __name__=='__main__':main()
