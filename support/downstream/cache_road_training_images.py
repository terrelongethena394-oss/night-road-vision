"""Exact decoded-pixel disk cache recognized by upstream loader; no resizing."""
from pathlib import Path
import concurrent.futures as cf,hashlib,json,os,time
import cv2,numpy as np
ROOT=Path('E:/FPGA_Enhance_Work/road_detection_20261026')
def main():
    folder=(ROOT/'dataset/images/train').resolve();assert folder.is_dir()
    out=ROOT/'training_disk_cache.json';assert not out.exists()
    rows=json.loads((ROOT/'dataset/manifest.json').read_text());rows=[r for r in rows if r['split']=='train' and r['status']=='READY']
    start=time.monotonic()
    def one(r):
        jpg=folder/r['name'];p=jpg.with_suffix('.npy');tmp=p.with_suffix('.npy.tmp')
        assert p.resolve().is_relative_to(folder) and tmp.resolve().is_relative_to(folder)
        assert not p.exists() and not tmp.exists(), 'Do not overwrite existing cache'
        image=cv2.imread(str(jpg));assert image.shape==(720,1280,3)
        with tmp.open('wb') as f:np.save(f,image,allow_pickle=False)
        check=np.load(tmp,allow_pickle=False);assert np.array_equal(check,image)
        digest=hashlib.sha256(tmp.read_bytes()).hexdigest();os.replace(tmp,p)
        return dict(path=str(p),source_sha256=r['image_sha256'],bytes=p.stat().st_size,sha256=digest,pixels_exact=True)
    done=[]
    with cf.ThreadPoolExecutor(2) as pool:
        for item in pool.map(one,rows):
            done.append(item)
            if len(done)%400==0:print('EXACT_TRAIN_PIXEL_CACHE',len(done),len(rows),flush=True)
    manifest=dict(status='ALL_DECODED_TRAINING_PIXEL_CACHES_EXACT',folder=str(folder),created=done,bytes=sum(r['bytes'] for r in done),seconds=time.monotonic()-start,
                  note='Identical original cv2 BGR pixels, dimensions preserved. Upstream load_image chooses .npy when present, with unchanged resize and augmentation. Training only, no val/test caches.')
    out.write_text(json.dumps(manifest,indent=2),encoding='utf-8');print('EXACT_PIXEL_CACHE_COMPLETE',manifest['bytes'],manifest['seconds'],flush=True)
if __name__=='__main__':main()
