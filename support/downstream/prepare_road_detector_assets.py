"""Pin trusted upstream source/weights and public BDD metadata; no training yet."""
from pathlib import Path
import concurrent.futures as cf,hashlib,io,json,time,urllib.request,zipfile
ROOT=Path('E:/FPGA_Enhance_Work/road_detection_20261026')
OBJ_REV='69e9f9a60103df97e151e2606a6ad182db824f55'
PER_REV='47b8bde4a2d808df9208a89cdd10f68b251bcdb4'
def sha(b):return hashlib.sha256(b).hexdigest()
def get(url):
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url,timeout=40) as r:return r.read()
        except Exception:
            if attempt==4:raise
            time.sleep(2+attempt*3)
def main():
    assets=ROOT/'assets';assets.mkdir(exist_ok=True)
    urls={'yolov5_v7.zip':'https://codeload.github.com/ultralytics/yolov5/zip/refs/tags/v7.0',
          'yolov5n.pt':'https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5n.pt',
          'BDD_DATA_LICENSE.txt':'https://raw.githubusercontent.com/bdd100k/bdd100k/master/doc/source/license.rst'}
    def fetch(kv):
        name,url=kv;p=assets/name
        if not p.exists():p.write_bytes(get(url))
        return dict(file=name,url=url,bytes=p.stat().st_size,sha256=sha(p.read_bytes()))
    results=list(cf.ThreadPoolExecutor(3).map(fetch,urls.items()))
    source=ROOT/'yolov5'
    if not source.exists():
        source.mkdir()
        with zipfile.ZipFile(assets/'yolov5_v7.zip') as z:
            for member in z.infolist():
                if member.is_dir():continue
                relative=Path(*Path(member.filename).parts[1:]);dest=source/relative
                assert dest.resolve().is_relative_to(source.resolve())
                dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(member))
    meta=ROOT/'source_metadata';meta.mkdir(exist_ok=True)
    tasks=[(split,i) for split,n in [('train',9),('val',2)] for i in range(n)]
    def metadata(task):
        split,i=task;path=f'data/images/{split}/shard_{i:03d}/metadata.jsonl'
        url=f'https://huggingface.co/datasets/dronefreak/BDD100K-Period-Classification/resolve/{PER_REV}/{path}'
        p=meta/f'{split}_{i:03d}.jsonl'
        if not p.exists():p.write_bytes(get(url))
        rows=[json.loads(line) for line in p.read_text().splitlines()]
        return dict(split=split,shard=i,path=path,url=url,rows=len(rows),sha256=sha(p.read_bytes()))
    rows=list(cf.ThreadPoolExecutor(4).map(metadata,tasks))
    manifest=dict(status='SOURCE_AND_METADATA_DOWNLOADED',object_revision=OBJ_REV,period_revision=PER_REV,assets=results,metadata=rows)
    (ROOT/'assets.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('ROAD_ASSETS_READY',len(results),sum(r['rows'] for r in rows),flush=True)
if __name__=='__main__':main()
