from pathlib import Path
import hashlib,json
BASE=Path('E:/FPGA_Enhance_Work')
ROOT=BASE/'road_car_pair_20261030_r1'
APP=ROOT/'firmware'
OLD=BASE/'road_camera_snapshot_20261030_r1/firmware'
ADAPT=BASE/'road_viewadapt_20261030_r1'
ROUTE=BASE/'road_brightness_route_20261030_r1'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

