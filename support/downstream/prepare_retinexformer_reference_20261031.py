"""Fetch original-author source metadata; do not execute downloaded code here."""
from pathlib import Path
import urllib.request,json,re,hashlib
ROOT=Path('E:/FPGA_Enhance_Work/retinexformer_reference_20261031_r1')
def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'FPGA-project-reference-review'})
    with urllib.request.urlopen(req,timeout=45) as r:return r.read()
def main():
    ROOT.mkdir(exist_ok=True);(ROOT/'source').mkdir(exist_ok=True)
    api='https://api.github.com/repos/caiyuanhao1998/Retinexformer'
    info=json.loads(get(api+'/commits/master'));commit=info['sha']
    base=f'https://raw.githubusercontent.com/caiyuanhao1998/Retinexformer/{commit}/'
    paths=['README.md','LICENSE.txt','basicsr/models/archs/RetinexFormer_arch.py','Options/RetinexFormer_LOL_v1.yml','Enhancement/test_from_folder.py']
    files={}
    for path in paths:
        try:
            data=get(base+path);dest=ROOT/'source'/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
            files[path]={'sha256':hashlib.sha256(data).hexdigest(),'url':base+path}
            if path=='README.md':
                lines=data.decode().splitlines()
                for i,line in enumerate(lines):
                    if any(s in line.lower() for s in ['pre-trained','pretrained','weights','gdown','testing','test_from_folder']):
                        print('README',i+1,('\n'.join(lines[max(0,i-1):i+4])).encode('ascii','backslashreplace').decode())
            elif path.endswith('.py'):
                lines=data.decode().splitlines()
                print('SOURCE_HEADER',path,'\n'.join(lines[:35]))
        except Exception as e:print('FETCH_FAILED',path,repr(e))
    (ROOT/'source_manifest.json').write_text(json.dumps({'repository':api,'commit':commit,'files':files},indent=2),encoding='utf-8')
    tree=json.loads(get(api+f'/git/trees/{commit}?recursive=1'))
    (ROOT/'tree.json').write_text(json.dumps(tree,indent=2),encoding='utf-8')
    print('TREE_RELEVANT',[x['path'] for x in tree['tree'] if any(s in x['path'].lower() for s in ['.pth','.yml','folder','retinexformer_arch'])])
if __name__=='__main__':main()
