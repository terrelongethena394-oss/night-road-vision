"""Independent low-brightness confirmation, before any new predictions.

The nominal night labels contain visual mistakes. Keep the selected detector
unchanged, require an operational raw-brightness criterion before inference.
"""
import concurrent.futures as cf,hashlib,json,shutil
from PIL import Image
from road_accuracy_common import *
from prepare_road_training_data import fetch,CLASSES
from audit_road_accuracy_light import mean_y

ORIGINAL=ROOT
LOW=BASE/'road_accuracy_lowlight_20261030_r1'
URL='https://huggingface.co/datasets/dronefreak/BDD100K/resolve/69e9f9a60103df97e151e2606a6ad182db824f55/'

def prepare():
    assert not LOW.exists();LOW.mkdir()
    sources=[DATA/'dataset/manifest.json',BASE/'road_twilight_consistency_20261027/dataset/manifest.json',BASE/'road_light_20261027/dataset/manifest.json']+list(BASE.glob('road_*/fresh/manifest.json'))+list(BASE.glob('road_*/fresh_selection.json'))+list(BASE.glob('road_*/quality/fresh_selection.json'))
    used=[]
    for p in sources:
        if p.exists():
            d=read(p)
            if isinstance(d,list):used.extend(r for r in d if isinstance(r,dict) and 'name' in r)
    groups={r.get('group',r['name'].split('-')[0]) for r in used};hashes={r['image_sha256'] for r in used if 'image_sha256' in r}
    image_paths={Path(r['rfilename']).name:r['rfilename'] for r in read(DATA/'BDD100K_repo.json')['siblings'] if r['rfilename'].endswith('.jpg') and '/100k/' in r['rfilename']}
    pool=[]
    for p in sorted((DATA/'source_metadata').glob('val_*.jsonl')):
        for line in p.read_text().splitlines():
            r=json.loads(line);name=r['file_name'];group=name.split('-')[0]
            if group not in groups and r['label']=='night' and name in image_paths:pool.append(dict(name=name,group=group,timeofday='night',image_path=image_paths[name],rank=hashlib.sha256((str(SEED+101)+'|'+name).encode()).hexdigest()))
    pool.sort(key=lambda r:r['rank']);assert len(pool)>=320
    write(LOW/'protocol.json',dict(status='FROZEN_BEFORE_DOWNLOAD_SCREENING_OR_NEW_INFERENCE',reason='A visually daytime image was labelled night in the source. Existing672 remains mixed-road evidence; reserve a new confirmation based on raw brightness, without changing selected network/geometry/thresholds.',selection='First320 distinct previously unused first8 groups by fixed metadata hash rank satisfying original night label AND mean unenhanced400x240 Y<=48. Brightness screening only, before any predictions. No claim of physical lux or perfect time-of-day labels.',brightness_threshold=48,images=320,selected_sha256=sha(ORIGINAL/'selected.json'),model_unchanged=True,primary='Car AP50 in operationally defined low-brightness road images',acceptance='Same +1pp point AP and <=1pp precision loss;99% paired image bootstrap lower bound>0;4class AP loss<=0.5pp. No reselection on confirmation.',previous_label_audit_sha256=sha(ORIGINAL/'brightness_audit.json'),excluded={str(p):sha(p) for p in sources if p.exists()},hardware_access=False,sd_written=False))
    shutil.copy2(ORIGINAL/'selected.json',LOW/'selected.json')
    for kind in ['images','annotations','labels']:(LOW/'fresh'/kind).mkdir(parents=True)
    examined=[];chosen=[];seen=set()
    def screen(r):
        data=fetch(URL+r['image_path']);digest=hashlib.sha256(data).hexdigest();assert digest not in hashes
        # Decode with the same OpenCV path used by the detector, then apply the
        # fixed sensor/averaging path. No detector or target boxes consulted.
        bgr=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR);assert bgr is not None and bgr.shape==(720,1280,3)
        sensor=cv2.resize(bgr[:,:,::-1],(800,480),interpolation=cv2.INTER_LINEAR);a=sensor.astype(np.uint16);raw=((a[0::2,0::2]+a[0::2,1::2]+a[1::2,0::2]+a[1::2,1::2]+2)//4).astype(np.uint8)
        return r,data,digest,mean_y(raw)
    with cf.ThreadPoolExecutor(8) as executor:
        for start in range(0,len(pool),32):
            for r,data,digest,brightness in executor.map(screen,pool[start:start+32]):
                examined.append(dict(name=r['name'],group=r['group'],mean_y=brightness,image_sha256=digest))
                if len(chosen)>=320 or brightness>48 or r['group'] in seen:continue
                seen.add(r['group']);(LOW/'fresh/images'/r['name']).write_bytes(data);chosen.append(dict(**r,image_sha256=digest,mean_y=brightness))
            write(LOW/'screened_candidates.json',examined);print('LOWLIGHT_SCREENED',len(examined),'accepted',len(chosen),flush=True)
            if len(chosen)==320:break
    assert len(chosen)==320
    def annotate(r):
        stem=Path(r['name']).stem;rel=r['image_path'].replace('images_100k/100k','labels/100k').rsplit('.',1)[0]+'.json';ap=LOW/'fresh/annotations'/(stem+'.json');ap.write_bytes(fetch(URL+rel));a=read(ap);assert a['name']==stem and a['attributes']['timeofday']=='night'
        labels=[];counts=[0]*4
        for o in a['frames'][0]['objects']:
            if o.get('category') not in CLASSES or 'box2d' not in o:continue
            b=o['box2d'];x1=max(0.,min(1280.,float(b['x1'])));x2=max(0.,min(1280.,float(b['x2'])));y1=max(0.,min(720.,float(b['y1'])));y2=max(0.,min(720.,float(b['y2'])))
            if x2<=x1 or y2<=y1:continue
            k=CLASSES[o['category']];counts[k]+=1;labels.append(f'{k} {(x1+x2)/2560:.9f} {(y1+y2)/1440:.9f} {(x2-x1)/1280:.9f} {(y2-y1)/720:.9f}')
        lp=LOW/'fresh/labels'/(stem+'.txt');lp.write_text('\n'.join(labels)+'\n' if labels else '',encoding='ascii')
        return dict(**r,annotation_sha256=sha(ap),label_sha256=sha(lp),class_counts=counts)
    with cf.ThreadPoolExecutor(8) as executor:records=list(executor.map(annotate,chosen))
    assert len({r['image_sha256'] for r in records})==320
    write(LOW/'fresh/manifest.json',records);write(LOW/'fresh/complete.json',dict(status='NEW320_LOW_BRIGHTNESS_RESERVED_BEFORE_ANY_INFERENCE',images=320,mean_range=[min(r['mean_y'] for r in records),max(r['mean_y'] for r in records)],manifest_sha256=sha(LOW/'fresh/manifest.json')))
    print('LOWLIGHT_CONFIRMATION_DATA_READY',flush=True)

def evaluate_and_confirm():
    assert (LOW/'fresh/complete.json').exists() and not (LOW/'result.json').exists()
    import native_road_accuracy as native
    native.ROOT=LOW;native.main()
    from finish_road_accuracy_metrics import bootstrap
    done=read(LOW/'native/complete.json');a=read(LOW/'native/baseline_predictions.json');b=read(LOW/'native/candidate_predictions.json');ci=bootstrap(a,b,'new320_low_brightness_fixed_candidate',320,.01)
    s=done['scores'];bc=s['baseline']['all']['classes']['car'];cc=s['candidate']['all']['classes']['car']
    gates=dict(car_ap=cc['ap50']>=bc['ap50']+.01,interval99_positive=ci['interval99'][0]>0,precision=cc['precision']>=bc['precision']-.01,fourclass=s['candidate']['all']['mAP50']>=s['baseline']['all']['mAP50']-.005)
    result=dict(status='INDEPENDENT_LOW_BRIGHTNESS_CONFIRMATION_ACCEPTED' if all(gates.values()) else 'LOW_BRIGHTNESS_NOT_ACCEPTED',accepted=all(gates.values()),gates=gates,scores=s,uncertainty=ci,images=320,scope='Previously unseen original night-labelled AND raw meanY<=48 road photos; operational brightness, not measured lux or verified physical night.',source_period_labels_have_visual_errors=True,no_candidate_reselection=True,sd_written=False)
    write(LOW/'result.json',result);print('LOWLIGHT_CONFIRMATION_COMPLETE',result,flush=True)

if __name__=='__main__':
    import sys
    {'prepare':prepare,'evaluate':evaluate_and_confirm}[sys.argv[1]]()
