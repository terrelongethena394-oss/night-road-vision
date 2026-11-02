"""Small CCPD-derived public crop subset; no large full-dataset download."""
from pathlib import Path
import json,urllib.request,urllib.parse,time,concurrent.futures,re,hashlib,io
import numpy as np
from PIL import Image
from plate_common import ROOT,SOURCE,SEED,write,sha,decode_key,split_plate
DATASET='zenitsu09/ccpd-ocr-recognition'
REVISION='a859a9f1180675b69ee7fcbc884758406900b5b7'
def get(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'FPGA-educational-image-research/1.0'}),timeout=25) as r:return r.read()
        except Exception:
            if attempt==2:raise
            time.sleep(2*(attempt+1))
def main():
    out=ROOT/'ccpd_subset';out.mkdir(exist_ok=True);images=out/'images';images.mkdir(exist_ok=True)
    assert not (out/'complete.json').exists()
    excluded={p.stem.split('-')[0].split('_')[0] for p in (SOURCE/'data/test').glob('*.jpg')}
    size=json.loads(get('https://datasets-server.huggingface.co/size?'+urllib.parse.urlencode(dict(dataset=DATASET))))
    write(out/'remote_size.json',size);total=size['size']['splits'][0]['num_rows']
    # Distributed blocks, fixed before seeing any model prediction.
    rng=np.random.default_rng(SEED);blocks=sorted(rng.choice((total+99)//100,size=min(32,(total+99)//100),replace=False).tolist())
    write(out/'sampling_protocol.json',dict(status='FROZEN_BEFORE_IMAGE_FETCH_OR_MODEL_SCORING',source='CCPD-derived community crop mirror',dataset=DATASET,revision=REVISION,original_dataset='https://github.com/detectRecog/CCPD',source_rows=total,blocks=blocks,block_size=100,split='SHA256(seed|full_plate_string):70%train15%validation15%test; all appearances of same plate stay together; non-base source subsets stress-test-only.',excluded_legacy_plate_strings=len(excluded),pretrained_data_overlap='Unknown; upstream pretrained model may have seen CCPD. This is an engineering benchmark, not proof of blind generalization.',label='Decode original CCPD numeric annotation in key; validate against key ASCII suffix. Blue seven-character plates only, no pseudo-labeling.',board_written=False,sd_written=False))
    entries=[];rejected=[]
    for block in blocks:
        u='https://datasets-server.huggingface.co/rows?'+urllib.parse.urlencode(dict(dataset=DATASET,config='default',split='train',offset=block*100,length=min(100,total-block*100)))
        page=json.loads(get(u));write(out/f'block_{block}.json',page)
        for item in page['rows']:
            row=item['row'];key=row['__key__'];idx=item['row_idx']
            try:
                text=decode_key(key)
                prefix=key.rsplit('/',1)[-1].split('_')[0]
                assert prefix==text[1:],'Label does not match ASCII key prefix'
                if text in excluded:raise ValueError('Same plate as upstream regression examples')
                split=split_plate(text)
                if '_ccpd_base_' not in key:split='stress_test'
                entries.append(dict(row=idx,key=key,text=text,split=split,url=row['jpg']['src']))
            except (AssertionError,ValueError,IndexError) as e:rejected.append(dict(row=idx,key=key,reason=str(e)))
        print('PLATE_METADATA_BLOCK',block,'accepted',len(entries),flush=True)
    def download(e):
        p=images/f'{e["row"]:07d}.jpg'
        try:
            if not p.exists():p.write_bytes(get(e['url']))
            im=Image.open(p);im.load();assert im.width>=30 and im.height>=8
            return {k:v for k,v in e.items() if k!='url'}|dict(path=str(p),sha256=sha(p),width=im.width,height=im.height)
        except Exception as exc:return dict(row=e['row'],key=e['key'],failure=repr(exc))
    completed=[];start=time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for i,e in enumerate(pool.map(download,entries),1):
            if 'failure' in e:rejected.append(e)
            else:completed.append(e)
            if i%100==0:print('PLATE_IMAGES',i,len(entries),round(time.monotonic()-start,1),flush=True)
    # Reject exact cross-split duplicate bytes instead of leaking them.
    used={};unique=[]
    for e in completed:
        if e['sha256'] in used:
            rejected.append(dict(row=e['row'],reason='Duplicate image bytes',duplicate_of=used[e['sha256']]));continue
        used[e['sha256']]=e['row'];unique.append(e)
    write(out/'manifest.json',unique);write(out/'rejected.json',rejected)
    counts={s:sum(e['split']==s for e in unique) for s in ['train','validation','test','stress_test']}
    for s in ['train','validation','test']:assert counts[s]>=80,(s,counts)
    write(out/'complete.json',dict(status='SMALL_PLATE_GROUPED_SUBSET_READY',counts=counts,images=len(unique),manifest_sha256=sha(out/'manifest.json'),source_revision=REVISION,download_failures_and_exclusions=len(rejected),bytes=sum(Path(e['path']).stat().st_size for e in unique),seconds=time.monotonic()-start))
    print('PLATE_SUBSET_READY',counts,flush=True)
if __name__=='__main__':main()
