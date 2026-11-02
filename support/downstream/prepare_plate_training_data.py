"""Frozen plate-identity grouped crop dataset, no pseudo labels or test fitting."""
from pathlib import Path
import json,hashlib,io,ast,re,time
import numpy as np
import pyarrow.parquet as pq
from PIL import Image
import cv2
from plate_common import ROOT,SOURCE,SEED,CHARS,write,sha,decode_key,split_plate
def main():
    out=ROOT/'data';out.mkdir(exist_ok=True);assert not (out/'complete.json').exists()
    source=ROOT/'ccpd_crops_shard_0002.parquet';assert sha(source)=='e316d6e28e0a796b27a2dc2a7b18ae8743d806aeb6033eba321d1464c5b7240c'
    # Parse the actual upstream mapping, so province order cannot silently drift.
    doc=(ROOT/'ccpd_readme.md').read_text(encoding='utf-8')
    for key,want in [('provinces',list('皖沪津渝冀晋蒙辽吉黑苏浙京闽赣鲁豫鄂湘粤桂琼川贵云藏陕甘青宁新')),('alphabets',list('ABCDEFGHJKLMNPQRSTUVWXYZ')),('ads',list('ABCDEFGHJKLMNPQRSTUVWXYZ0123456789'))]:
        got=ast.literal_eval(re.search(key+r'\s*=\s*(\[[^\]]+\])',doc,re.S)[1]);assert got[:len(want)]==want
    excluded={p.stem.split('-')[0].split('_')[0] for p in (SOURCE/'data/test').glob('*.jpg')}
    write(out/'protocol.json',dict(status='FROZEN_BEFORE_EXTRACTION_OR_STUDENT_FITTING',dataset='CCPD-derived cropped plates, community mirror zenitsu09/ccpd-ocr-recognition',revision='a859a9f1180675b69ee7fcbc884758406900b5b7',artifact='default/train/0002.parquet',artifact_sha256=sha(source),original='https://github.com/detectRecog/CCPD',limits=dict(train=8000,validation=1200,test=1200,stress_test=600),sampling='Fixed SHA256(seed|key) order within plate-hash split; plate string never crosses train/val/test. Only base subset for fitting; other subsets stress-test-only. Upstream1000 example plate identities entirely excluded.',scope='Given ground-truth plate crop, seven-character blue mainland plates. Not automatic detection, green eight-character plates or real night proof.',pretraining_overlap='Teacher data unknown, so teacher distillation may carry external pretraining overlap; no blind generalization claim. Evaluation images are never gradient inputs or checkpoint selection.',darkening='Training random gains/shot-noise/contrast are augmentation, not lux or actual night capture.',board_written=False,sd_written=False))
    rows=[];reject=[];used={};table=pq.read_table(source,columns=['jpg','__key__'])
    for i in range(len(table)):
        key=table['__key__'][i].as_py()
        try:
            label=decode_key(key);prefix=key.rsplit('/',1)[-1].split('_')[0];assert prefix==label[1:]
            if label in excluded:raise ValueError('Same plate as upstream example')
            b=table['jpg'][i].as_py()['bytes'];digest=hashlib.sha256(b).hexdigest()
            if digest in used:raise ValueError('Exact duplicate bytes')
            used[digest]=i;split=split_plate(label) if '_ccpd_base_' in key else 'stress_test'
            rows.append(dict(row=i,key=key,text=label,split=split,sha256=digest,rank=hashlib.sha256((str(SEED)+'|'+key).encode()).hexdigest()))
        except (AssertionError,ValueError,IndexError) as e:reject.append(dict(row=i,key=key,reason=str(e)))
    chosen=[];counts={}
    for split,limit in [('train',8000),('validation',1200),('test',1200),('stress_test',600)]:
        records=sorted([a for a in rows if a['split']==split],key=lambda v:v['rank'])[:limit]
        if split!='stress_test':assert len(records)>=300,(split,len(records))
        xs=[];teachers=[];texts=[]
        for a in records:
            b=table['jpg'][a['row']].as_py()['bytes'];rgb=np.array(Image.open(io.BytesIO(b)).convert('RGB'));bgr=rgb[:,:,::-1].copy()
            xs.append(cv2.resize(bgr,(96,32),interpolation=cv2.INTER_LINEAR));teachers.append(cv2.resize(bgr,(94,24),interpolation=cv2.INTER_LINEAR));texts.append(a['text'])
        if records:np.savez_compressed(out/f'{split}.npz',x=np.stack(xs),teacher=np.stack(teachers),texts=np.array(texts))
        counts[split]=len(records);chosen.extend(records);print('PLATE_CACHE',split,len(records),flush=True)
    sets={s:{a['text'] for a in chosen if a['split']==s} for s in counts}
    for a,b in [('train','validation'),('train','test'),('validation','test')]:assert not sets[a]&sets[b]
    write(out/'manifest.json',chosen);write(out/'excluded.json',reject)
    write(out/'complete.json',dict(status='PLATE_CACHES_READY',counts=counts,excluded=len(reject),manifest_sha256=sha(out/'manifest.json'),source_sha256=sha(source),unique_plates={s:len(v) for s,v in sets.items()},provinces={p:sum(a['text'][0]==p for a in chosen) for p in sorted({a['text'][0] for a in chosen})},fit_on_test=False))
    print('PLATE_TRAINING_DATA_READY',counts,flush=True)
if __name__=='__main__':main()
