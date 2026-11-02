from pathlib import Path
import urllib.request,hashlib,json
ROOT=Path('E:/FPGA_Enhance_Work/retinexformer_reference_20261031_r1')
url='https://drive.usercontent.google.com/download?id=1xDwQtTCj3tlAVCTJgYrzonBGVwqeOhKu&export=download&confirm=t'
req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
with urllib.request.urlopen(req,timeout=40) as r:
    data=r.read(64*1024*1024);ctype=r.headers.get('Content-Type','')
assert len(data)>100000 and ('text/html' not in ctype), (len(data),ctype,data[:120])
assert len(data)<64*1024*1024
dest=ROOT/'LOL_v1.pth';assert not dest.exists();dest.write_bytes(data)
meta=dict(original_author_folder='https://drive.google.com/drive/folders/1ynK5hfQachzc8y96ZumhkPPDXzHJwaQV',
 filename=dest.name,url=url,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),source='Original-author README-linked public Google Drive; no third-party checkpoint.')
(ROOT/'weight_manifest.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
print('RETINEXFORMER_WEIGHT_READY',json.dumps(meta))
