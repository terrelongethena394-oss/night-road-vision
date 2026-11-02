"""Range-download the official pinned wheel, then require its official SHA256."""
from pathlib import Path
import json,urllib.request,concurrent.futures,hashlib,time,os,subprocess
ROOT=Path('E:/FPGA_Enhance_Work/license_plate_20261026')
def main():
    meta=json.loads((ROOT/'gpu_wheel.json').read_text());url=meta['url'];expected=meta['hash_fragment'].split('=')[1]
    path=ROOT/'torch-2.7.1+cu126-cp312-cp312-win_amd64.whl';total=2716918001;chunk=8*1024*1024
    assert not path.exists()
    with path.open('wb') as f:f.truncate(total)
    def part(i):
        start=i*chunk;end=min(total,start+chunk)-1
        for attempt in range(4):
            try:
                request=urllib.request.Request(url,headers={'Range':f'bytes={start}-{end}'})
                with urllib.request.urlopen(request,timeout=30) as response:
                    assert response.status==206 and response.headers.get('Content-Range')==f'bytes {start}-{end}/{total}'
                    data=response.read();assert len(data)==end-start+1
                with path.open('r+b') as f:f.seek(start);f.write(data)
                return i
            except Exception:
                if attempt==3:raise
                time.sleep(2+attempt)
    start=time.monotonic();count=(total+chunk-1)//chunk;done=0
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for future in concurrent.futures.as_completed([pool.submit(part,i) for i in range(count)]):
            future.result();done+=1
            if done%8==0:print('OFFICIAL_GPU_WHEEL_PARTS',done,count,round(time.monotonic()-start,1),flush=True)
    h=hashlib.sha256()
    with path.open('rb') as f:
        for data in iter(lambda:f.read(8*1024*1024),b''):h.update(data)
    assert h.hexdigest()==expected,(h.hexdigest(),expected)
    (ROOT/'gpu_download_verified.json').write_text(json.dumps(dict(path=str(path),bytes=total,sha256=h.hexdigest(),official_hash_verified=True,seconds=time.monotonic()-start),indent=2))
    print('GPU_WHEEL_SHA256_VERIFIED',h.hexdigest(),flush=True)
    subprocess.run(['E:/FPGA_Enhance_Work/nn_env312/Scripts/python.exe','-m','pip','install','--no-deps','--no-cache-dir','--target','E:/FPGA_Enhance_Work/plate_gpu_lib',str(path)],check=True)
    print('ISOLATED_GPU_TORCH_INSTALLED',flush=True)
if __name__=='__main__':main()
