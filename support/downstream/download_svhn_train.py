"""Download the real training split, verify upstream checksum, keep test separate."""
from pathlib import Path
import hashlib, json, time, urllib.request

ROOT=Path('E:/FPGA_Enhance_Work/real_digit_training_20261025/data')
URL='https://huggingface.co/datasets/darcook/DCPV-Artifacts/resolve/main/data/svhn/train_32x32.mat'
EXPECTED='e26dedcc434d2e4c54c9b2d4a06d8373'

def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    final=ROOT/'train_32x32.mat'
    if not final.exists():
        part=ROOT/'train_32x32.mat.part'
        for attempt in range(3):
            try:
                request=urllib.request.Request(URL,headers={'User-Agent':'FPGA-research/1.0'})
                with urllib.request.urlopen(request,timeout=60) as response,part.open('wb') as out:
                    size=0;last=time.monotonic()
                    while True:
                        chunk=response.read(1024*1024)
                        if not chunk:break
                        out.write(chunk);size+=len(chunk)
                        if time.monotonic()-last>10:
                            print('SVHN_DOWNLOAD_BYTES',size,flush=True);last=time.monotonic()
                assert hashlib.md5(part.read_bytes()).hexdigest()==EXPECTED,'SVHN checksum mismatch'
                part.rename(final)
                break
            except Exception as exc:
                print('DOWNLOAD_ATTEMPT_FAILED',attempt+1,type(exc).__name__,str(exc),flush=True)
                if attempt==2:raise
    data=final.read_bytes()
    assert hashlib.md5(data).hexdigest()==EXPECTED
    record=dict(url=URL,upstream_url='http://ufldl.stanford.edu/housenumbers/train_32x32.mat',
        checksum_source='https://raw.githubusercontent.com/pytorch/vision/main/torchvision/datasets/svhn.py',
        bytes=len(data),md5=EXPECTED,sha256=hashlib.sha256(data).hexdigest(),
        purpose='Training split only. Official test photographs are not training data.')
    (ROOT/'source_manifest.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print('SVHN_TRAIN_CHECKSUM_VERIFIED',len(data),flush=True)

if __name__=='__main__':main()
