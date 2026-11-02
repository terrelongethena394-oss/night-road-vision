"""Check current source bytes against upstream manifests frozen before this study."""
from pathlib import Path
import concurrent.futures as cf
from train_allview_gamma_20261031 import ROOT
from road_enhanced_detection_common import BASE,read,write,sha
def main():
    data=BASE/'road_detection_20261026/dataset';original=read(data/'manifest.json');lookup={r['name']:r for r in original if r['split']=='train' and r['status']=='READY'}
    rows=read(ROOT/'training_manifest.json');dev=read(ROOT/'development_manifest.json');assert len(rows)==2400
    assert not {r['group'] for r in rows}&{r['group'] for r in dev}
    def one(r):
        old=lookup[r['name']];assert old['group']==r['group'] and old['image_sha256']==r['image_sha256']
        p=data/'images/train'/r['name'];q=data/'labels/train'/(Path(r['name']).stem+'.txt');assert sha(p)==old['image_sha256'] and sha(q)==old['label_sha256']
        return dict(name=r['name'],image_sha256=old['image_sha256'],label_sha256=old['label_sha256'])
    with cf.ThreadPoolExecutor(4) as pool:receipts=list(pool.map(one,rows))
    write(ROOT/'source_byte_receipts.json',receipts);proof=dict(status='ALL2400_SOURCE_IMAGE_AND_LABEL_BYTES_MATCH_UPSTREAM_FROZEN_MANIFEST',training_images=len(rows),train_dev_prefix_groups_disjoint=True,upstream_manifest_sha256=sha(data/'manifest.json'),training_manifest_sha256=sha(ROOT/'training_manifest.json'),receipt_sha256=sha(ROOT/'source_byte_receipts.json'),scope='Audit during fixed training; upstream label hashes predate this study. No source edits.',hardware_access=False,sd_written=False)
    write(ROOT/'source_audit.json',proof);print(proof)
if __name__=='__main__':main()
