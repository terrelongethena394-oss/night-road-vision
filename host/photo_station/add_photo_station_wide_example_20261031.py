from pathlib import Path
import shutil
from PIL import Image
from photo_station_core import DELIVERY,BOARD
from car_roi_delivery_common import BASE,read,write,sha
def main():
    record=read(BOARD/'fixtures/manifest.json')['roads'][0];name=record['source']['name']
    candidates=[]
    for pattern in [f'road_*/confirmation/fresh/images/{name}',f'road_*/fresh/images/{name}',f'road_*/dataset/images/{name}']:
        candidates.extend(BASE.glob(pattern))
    matches=[p for p in candidates if sha(p)==record['source_sha256']]
    assert matches,'Original cached wide photo was not found; no download performed.'
    p=matches[0];dest=DELIVERY/'示例照片/夜间道路宽幅原片.jpg';shutil.copy2(p,dest)
    with Image.open(dest) as im:assert im.size==(1280,720)
    write(DELIVERY/'示例照片/宽幅来源.json',dict(source=str(p),source_sha256=sha(p),image_size=[1280,720],scope='Existing demonstration source, not new accuracy data'))
    print('WIDE_ORIGINAL_SAMPLE_READY',dest,flush=True)
if __name__=='__main__':main()
