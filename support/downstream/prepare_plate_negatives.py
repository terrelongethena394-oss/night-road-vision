"""Non-plate training/control images, no live camera frames used for fitting."""
from pathlib import Path
import urllib.request,gzip,hashlib,json,io
import numpy as np
import cv2
from skimage import data
from plate_common import ROOT,SEED,write,sha
def main():
    out=ROOT/'negatives';out.mkdir(exist_ok=True);assert not (out/'complete.json').exists()
    files=[('train','train-images-idx3-ubyte.gz','8d4fb7e6c68d591d4c3dfef9ec88bf0d'),('test','t10k-images-idx3-ubyte.gz','bef4ecab320f06d8554ea6380940ec79')]
    images={}
    for split,name,md5 in files:
        p=out/name
        if not p.exists():
            with urllib.request.urlopen('https://raw.githubusercontent.com/zalandoresearch/fashion-mnist/master/data/fashion/'+name,timeout=30) as f:p.write_bytes(f.read())
        assert hashlib.md5(p.read_bytes()).hexdigest()==md5
        images[split]=np.frombuffer(gzip.decompress(p.read_bytes()),np.uint8,offset=16).reshape(-1,28,28)
    rng=np.random.default_rng(SEED);order=rng.permutation(len(images['train']))
    # Real scene sources do not cross splits; many crops are not independent scenes.
    scenes={'train':['camera','coffee','grass','brick'],'validation':['chelsea','gravel'],'test':['astronaut','coins']}
    write(out/'protocol.json',dict(status='FROZEN_BEFORE_NEGATIVE_SCORING_OR_STUDENT_TRAINING',fashion='https://github.com/zalandoresearch/fashion-mnist',fashion_split='Random4500 from originalTRAIN for train and1000 disjoint for validation; originalTEST1000 for test.',natural_scenes=scenes,negative_label='No complete Chinese car plate: empty CTC target. Clothing category IDs are NOT interpreted as digit labels.',augmentation='Multiple scene crops share original source identity; source names stay within one split. Synthetic noise/flat controls are identified separately.',live_camera_fitting=False,board_written=False))
    sources=[]
    for split,ids in [('train',order[:4500]),('validation',order[4500:5500]),('test',np.arange(1000))]:
        imgs=[cv2.resize(a,(96,32)) for a in images['test' if split=='test' else 'train'][ids]]
        for name in scenes[split]:
            a=getattr(data,name)()
            if a.ndim==3:a=((77*a[:,:,0].astype(np.uint32)+150*a[:,:,1].astype(np.uint32)+29*a[:,:,2].astype(np.uint32)+128)>>8).astype(np.uint8)
            sources.append(dict(split=split,name='skimage.data.'+name,sha256=hashlib.sha256(a.tobytes()).hexdigest(),shape=list(a.shape),doc=getattr(data,name).__doc__))
            for j in range(300):
                h,w=a.shape;cw=int(rng.integers(max(32,w//5),w+1));ch=min(h,max(16,int(cw*rng.uniform(.2,.8))));xx=int(rng.integers(0,w-cw+1));yy=int(rng.integers(0,h-ch+1))
                imgs.append(cv2.resize(a[yy:yy+ch,xx:xx+cw],(96,32)))
        np.savez_compressed(out/(split+'.npz'),x=np.stack(imgs));print('NONPLATE_CACHE',split,len(imgs),flush=True)
    write(out/'source_credits.json',sources);write(out/'complete.json',dict(status='NONPLATE_SPLITS_READY',files={s:sha(out/(s+'.npz')) for s in ['train','validation','test']},live_camera_fitting=False))
if __name__=='__main__':main()
