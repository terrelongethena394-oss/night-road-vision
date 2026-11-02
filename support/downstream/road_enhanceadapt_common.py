from pathlib import Path
import hashlib,json
BASE=Path('E:/FPGA_Enhance_Work')
ROOT=BASE/'road_enhanceadapt_20261030_r1'
ADAPT=BASE/'road_viewadapt_20261030_r1'
DATA=BASE/'road_detection_20261026'
INITIAL=ADAPT/'export/model.pt'
AUDIT=BASE/'road_bright_detector_audit_20261030_r1'
SEED=2026103041
EPOCHS=6
CHECKPOINTS=[2,4,6]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
