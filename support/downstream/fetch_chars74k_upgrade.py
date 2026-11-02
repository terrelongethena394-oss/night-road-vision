"""Download public author-linked archives; extract only ordinary safe files."""
from pathlib import Path
import urllib.request,hashlib,json,tarfile,concurrent.futures
ROOT=Path('E:/FPGA_Enhance_Work/recognition_upgrade_20261026')
IDS={'EnglishImg.tgz':'1VNMJEvx9UJwzVi7IaNF2QfbMbAD90krX','Maps.tgz':'1Gy8R50W1XtmSYc4GsESNkEttmHlxnORR','Lists.tgz':'1Gzioygh0hy2JWQASjucQ0slx_0IyieaP'}
def fetch(item):
    name,id=item;p=ROOT/'downloads'/name
    url='https://drive.usercontent.google.com/download?id='+id+'&export=download&confirm=t'
    if not p.exists():
        tmp=p.with_suffix('.partial')
        with urllib.request.urlopen(url,timeout=40) as r,tmp.open('wb') as f:
            first=r.read(1024)
            assert first.startswith(b'\x1f\x8b'),(name,r.headers.get('Content-Type'),first[:80])
            f.write(first)
            while True:
                block=r.read(1024*1024)
                if not block:break
                f.write(block)
        tmp.replace(p)
    sha=hashlib.sha256(p.read_bytes()).hexdigest();dest=ROOT/'chars74k';dest.mkdir(exist_ok=True)
    extracted=[]
    with tarfile.open(p,'r:gz') as t:
        for m in t:
            if not m.isfile():continue
            target=(dest/m.name).resolve()
            assert target.is_relative_to(dest.resolve()),m.name
            if name=='EnglishImg.tgz' and not m.name.lower().endswith('.png'):continue
            target.parent.mkdir(parents=True,exist_ok=True)
            with t.extractfile(m) as src,target.open('wb') as out:
                while True:
                    b=src.read(1024*1024)
                    if not b:break
                    out.write(b)
            extracted.append(target.relative_to(dest).as_posix())
    print('AUTHOR_DATASET_READY',name,len(extracted),p.stat().st_size,flush=True)
    return dict(name=name,url=url,bytes=p.stat().st_size,sha256=sha,files=extracted)
def main():
    ROOT.mkdir(exist_ok=True);(ROOT/'downloads').mkdir(exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(fetch,IDS.items()))
    (ROOT/'chars74k_sources.json').write_text(json.dumps(dict(author_page='https://teodecampos.github.io/chars74k/',
        citation='T. E. de Campos, B. R. Babu, M. Varma. Character recognition in natural images. VISAPP2009.',
        conditions='Author asks source acknowledgement and paper citation. Public research dataset. No private Drive account used.',archives=rows),indent=2),encoding='utf-8')
    print('CHARS74K_DOWNLOAD_AND_SAFE_EXTRACTION_COMPLETE',flush=True)
if __name__=='__main__':main()
