"""Source-scene and font-family separated data. Test data never used by trainer."""
from pathlib import Path
from collections import defaultdict,Counter
import json,hashlib,gzip,re,time
import numpy as np
from PIL import Image,ImageFont,ImageDraw,ImageFilter,ImageOps
from recognition_upgrade_common import ROOT,BASE,SEED,sha,write
PREFIXES=('arial','calibri','cambria','candara','consolas','constantia','corbel','courier','georgia','impact',
 'segoe','tahoma','times','trebuchet','verdana','garamond','bookman','century','palatino','lucida',
 'franklin','baskerville','bahnschrift','rockwell','stencil','perpetua','bodoni','agency','berlin','bauhaus')
def font_groups():
    groups=defaultdict(list)
    for p in sorted(Path('C:/Windows/Fonts').iterdir()):
        if p.suffix.lower() not in ('.ttf','.ttc','.otf'):continue
        try:
            f=ImageFont.truetype(str(p),80);name=f.getname()[0].lower();group=next((g for g in PREFIXES if name.startswith(g)),None)
            if group is None:continue
            masks=[]
            for c in '0123456789':
                a=Image.new('L',(128,128));ImageDraw.Draw(a).text((4,0),c,font=f,fill=255)
                assert a.getbbox();masks.append(hashlib.sha256(a.tobytes()).hexdigest())
            if len(set(masks))!=10:continue
            groups[group].append(dict(path=str(p),sha256=sha(p),family=f.getname()[0]))
        except Exception:continue
    names=sorted(groups,key=lambda s:hashlib.sha256((str(SEED)+'|font|'+s).encode()).hexdigest())
    assert len(names)>=24
    split={g:('test' if i<4 else 'validation' if i<8 else 'train') for i,g in enumerate(names)}
    return dict(groups),split
def real_characters():
    root=ROOT/'chars74k';rows=[];seen={}
    for line in (root/'Maps/English/Img/source_image_map.txt').read_text(errors='replace').splitlines():
        p=line.split(';')
        if len(p)<3 or not p[0].startswith('GoodImg/Bmp/') or len(p[2])!=1:continue
        c=p[2]
        if c not in '0123456789AEFHKMNPRTUVWXYaefhkmnprtuvwxy':continue
        file=root/'English/Img'/(p[0]+'.png')
        if not file.is_file():continue
        if p[0] in seen:
            assert seen[p[0]]==(p[1],c);continue
        seen[p[0]]=(p[1],c)
        bucket=int(hashlib.sha256((str(SEED)+'|'+p[1].lower()).encode()).hexdigest()[:8],16)%100
        rows.append(dict(path=str(file),sha256=sha(file),source_scene=p[1],character=c,
            label=int(c) if c.isdigit() else 10,split='train' if bucket<60 else 'validation' if bucket<80 else 'test'))
    for split in ('train','validation','test'):
        counts=Counter(r['label'] for r in rows if r['split']==split)
        assert all(counts[i]>=3 for i in range(10)),counts
    assert not ({r['source_scene'] for r in rows if r['split']=='train'} & {r['source_scene'] for r in rows if r['split']=='test'})
    return rows
def char_image(path):
    a=Image.open(path).convert('RGB');v=np.array(a,dtype=np.uint32)
    g=((77*v[:,:,0]+150*v[:,:,1]+29*v[:,:,2]+128)>>8).astype(np.uint8)
    border=np.concatenate([g[0],g[-1],g[:,0],g[:,-1]]);bg=int(np.median(border))
    small=ImageOps.contain(Image.fromarray(g),(20,24),Image.Resampling.LANCZOS)
    out=Image.new('L',(28,28),bg);out.paste(small,((28-small.width)//2,(28-small.height)//2))
    return np.array(out)
def font_sample(families,groups,rng,cache):
    family=families[int(rng.integers(len(families)))];files=groups[family];r=files[int(rng.integers(len(files)))];key=r['path']
    if key not in cache:cache[key]=ImageFont.truetype(key,90)
    digit=int(rng.integers(10));font=cache[key];bbox=font.getbbox(str(digit))
    mask=Image.new('L',(max(1,bbox[2]-bbox[0])+8,max(1,bbox[3]-bbox[1])+8));ImageDraw.Draw(mask).text((4-bbox[0],4-bbox[1]),str(digit),font=font,fill=255)
    target=int(rng.integers(58,97));nw=max(14,int(mask.width*target/mask.height*rng.uniform(.75,1.15)))
    mask=mask.resize((min(102,nw),target),Image.Resampling.LANCZOS).rotate(float(rng.uniform(-12,12)),Image.Resampling.BICUBIC,expand=True)
    canvas=Image.new('L',(112,112));canvas.paste(mask,((112-mask.width)//2+int(rng.integers(-8,9)),(112-mask.height)//2+int(rng.integers(-8,9))))
    m=np.array(canvas,dtype=np.float32)/255
    yy,xx=np.mgrid[-1:1:112j,-1:1:112j];bg=float(rng.uniform(25,230))
    texture=np.array(Image.fromarray(rng.integers(0,256,(14,14),dtype=np.uint8)).resize((112,112),Image.Resampling.BICUBIC),np.float32)-128
    background=bg+rng.uniform(-30,30)*xx+rng.uniform(-30,30)*yy+texture*rng.uniform(0,.16)
    direction=-1 if bg>128 else 1
    foreground=bg+direction*rng.uniform(55,210)+rng.uniform(-45,45)*yy
    image=background*(1-m)+foreground*m
    # Mild metallic edge/shadow appearance; random orientation, not a target photograph.
    if rng.random()<.4:
        shifted=np.roll(m,(int(rng.integers(-3,4)),int(rng.integers(-3,4))),(0,1))
        image+=(shifted-m)*rng.uniform(-45,45)
    image=np.clip(image+rng.normal(0,rng.uniform(0,2.5),(112,112)),0,255).astype(np.uint8)
    return np.array(Image.fromarray(image).resize((28,28),Image.Resampling.LANCZOS)),digit,family
def mnist(split):
    root=BASE/'digit_recognition_20261023/mnist';prefix='train' if split=='train' else 't10k'
    x=np.frombuffer(gzip.decompress((root/(prefix+'-images-idx3-ubyte.gz')).read_bytes()),np.uint8,offset=16).reshape(-1,28,28).copy()
    y=np.frombuffer(gzip.decompress((root/(prefix+'-labels-idx1-ubyte.gz')).read_bytes()),np.uint8,offset=8).copy()
    return x,y
def main():
    ROOT.mkdir(exist_ok=True);data=ROOT/'data';data.mkdir(exist_ok=True)
    assert not (ROOT/'data_complete.json').exists()
    groups,fsplit=font_groups();characters=real_characters()
    protocol=dict(status='FROZEN_BEFORE_TRAINING_OR_NEW_TEST_INFERENCE',seed=SEED,
        architecture='Conv3x3(1->8),pool2,Conv3x3(8->16),pool2,784->64ReLU->11; original first32 hidden initialized, new32 head outputs initiallyzero.',
        input='ROI28x28 uint8; P5 rank40/P95 rank745, center=(lo+hi+1)//2,span=max(hi-lo,32),round-away((p-center)*192/span)+128 clipped tobyte. Same RAW/NET/AUTO preprocessing.',
        font_groups=groups,font_split=fsplit,real_characters=characters,
        split='Chars74K grouped by original source image. Font family groups separated. Existing SVHN train65257/val8000 kept. MNIST TRAIN54000/val6000 seeded split; official test read only after checkpoint frozen.',
        validation_selection='NormalSVHN accuracy must not fall below old float baseline; real chars>=max(oldraw+0.10,.70); fontnorm>=.90; MNIST>=.95; background>=.95; score .50SVHN+.20chars+.15fonts+.05MNIST+.10enhancedviews.',
        planned_training=dict(steps=2000,batch_parts=dict(svhn=128,views=64,fonts=96,mnist=48,chars=48,background=32),lr=.0005,
            distill='Temperature2 KL on original teacher-correct SVHN and existing train views only; CE on all true labels. No Wikimedia photos or official test fitting.'),
        test_acceptance='Selected frozen candidate only: officialSVHN integer not below original22170/26032; heldout-scene chars>=.80 and at least5points above oldraw; heldout fontfamilies>=.90; MNISTofficialTEST>=.95; background>=.95. Existing3Wikimedia only declared regression, not checkpointselection.',
        enhancement_benefit='Separate from recognizer acceptance: same weights/preprocessing compare RAW/NET/AUTO, retain all wins/losses. Better raw recognition alone is not enhancement benefit.',
        privacy='Local rendering only; Windows font binaries not redistributed. No private camera photos used for fitting.',board_changed=False,sd_written=False)
    if (ROOT/'training_protocol.json').exists():assert json.loads((ROOT/'training_protocol.json').read_text(encoding='utf-8'))==protocol
    else:write(ROOT/'training_protocol.json',protocol)
    cache={};start=time.monotonic()
    for split,n in [('train',16000),('validation',2000),('test',2000)]:
        families=[g for g,s in fsplit.items() if s==split];rng=np.random.default_rng(SEED+{'train':1,'validation':2,'test':3}[split])
        x=np.empty((n,28,28),np.uint8);y=np.empty(n,np.uint8);fg=[]
        for i in range(n):
            x[i],y[i],family=font_sample(families,groups,rng,cache);fg.append(family)
            if (i+1)%2000==0:print('FONT_CACHE',split,i+1,n,round(time.monotonic()-start,1),flush=True)
        np.savez_compressed(data/('fonts_'+split+'.npz'),x=x,y=y,family=np.array(fg))
    for split in ('train','validation','test'):
        rows=[r for r in characters if r['split']==split]
        x=np.stack([char_image(r['path']) for r in rows]);y=np.array([r['label'] for r in rows],np.uint8)
        np.savez_compressed(data/('chars_'+split+'.npz'),x=x,y=y,source=np.array([r['source_scene'] for r in rows]))
        print('REAL_CHARACTER_CACHE',split,len(rows),Counter(y.tolist()),flush=True)
    mx,my=mnist('train');order=np.random.default_rng(SEED).permutation(len(mx))
    for name,ids in [('train',order[:54000]),('validation',order[54000:])]:np.savez_compressed(data/('mnist_'+name+'.npz'),x=mx[ids],y=my[ids])
    np.savez(data/'mnist_split.npz',train=order[:54000],validation=order[54000:])
    files=[dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(data.glob('*.npz'))]
    write(ROOT/'data_complete.json',dict(status='GROUP_SEPARATED_DATA_READY',files=files,seconds=time.monotonic()-start,test_read_by_trainer=False))
    print('RECOGNITION_UPGRADE_DATA_READY',round(time.monotonic()-start,1),flush=True)
if __name__=='__main__':main()
