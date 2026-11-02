"""Download preselected new holdout without any model inference or filtering."""
from pathlib import Path
import collections,concurrent.futures as cf,json,time
from PIL import Image
from road_adapt_common import BASE,ROOT,NAMES,read,write,sha
from prepare_road_training_data import fetch,CLASSES
URL='https://huggingface.co/datasets/dronefreak/BDD100K/resolve/69e9f9a60103df97e151e2606a6ad182db824f55/'
def main():
    t=time.monotonic()
    while not (ROOT/'fresh_selection.json').exists():
        if time.monotonic()-t>300:raise TimeoutError('Fresh selection unavailable')
        time.sleep(.5)
    selected=read(ROOT/'fresh_selection.json');old=read(BASE/'dataset/manifest.json');hashes={r['image_sha256'] for r in old if r['status']=='READY'}
    for name in ['images','annotations','labels']:(ROOT/'fresh'/name).mkdir(parents=True,exist_ok=True)
    assert not (ROOT/'fresh/complete.json').exists()
    def one(r):
        name=r['name'];stem=Path(name).stem;ap=ROOT/'fresh/annotations'/(stem+'.json')
        rel=r['image_path'].replace('images_100k/100k','labels/100k').rsplit('.',1)[0]+'.json'
        if not ap.exists():ap.write_bytes(fetch(URL+rel))
        annotation=read(ap);assert annotation['name']==stem and annotation['attributes']['timeofday']==r['timeofday']
        assert len(annotation['frames'])==1 and annotation['frames'][0]['timestamp']==10000
        ip=ROOT/'fresh/images'/name
        if not ip.exists():ip.write_bytes(fetch(URL+r['image_path']))
        image=Image.open(ip);image.load();w,h=image.size;assert (w,h)==(1280,720)
        digest=sha(ip);assert digest not in hashes,'Fresh image duplicates previous data'
        labels=[];counts=[0]*4;invalid=0
        for o in annotation['frames'][0]['objects']:
            if o.get('category') not in CLASSES or 'box2d' not in o:continue
            b=o['box2d'];x1=max(0.,min(w,float(b['x1'])));x2=max(0.,min(w,float(b['x2'])));y1=max(0.,min(h,float(b['y1'])));y2=max(0.,min(h,float(b['y2'])))
            if x2<=x1 or y2<=y1:invalid+=1;continue
            k=CLASSES[o['category']];counts[k]+=1;labels.append(f'{k} {(x1+x2)/(2*w):.9f} {(y1+y2)/(2*h):.9f} {(x2-x1)/w:.9f} {(y2-y1)/h:.9f}')
        lp=ROOT/'fresh/labels'/(stem+'.txt');lp.write_text('\n'.join(labels)+'\n' if labels else '',encoding='ascii')
        return {**r,'status':'READY','image_sha256':digest,'annotation_sha256':sha(ap),'label_sha256':sha(lp),'class_counts':counts,'invalid_boxes':invalid}
    out=[]
    with cf.ThreadPoolExecutor(12) as pool:
        for r in pool.map(one,selected):
            out.append(r)
            if len(out)%80==0:print('UNSEEN_GROUP_HOLDOUT_FETCHED',len(out),len(selected),flush=True)
    assert len({r['group'] for r in out})==len(out)==480
    write(ROOT/'fresh/manifest.json',out)
    summary=dict(status='FRESH_HELDOUT_READY',images=len(out),groups=len(out),by_time=dict(collections.Counter(r['timeofday'] for r in out)),
                 objects=dict(zip(NAMES,[sum(r['class_counts'][k] for r in out) for k in range(4)])),previous_prefix_overlap=False,previous_exact_image_overlap=False,any_model_inference=False,manifest_sha256=sha(ROOT/'fresh/manifest.json'))
    write(ROOT/'fresh/complete.json',summary);print('UNSEEN_HOLDOUT_READY',json.dumps(summary),flush=True)
if __name__=='__main__':main()
