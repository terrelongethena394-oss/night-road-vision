from pathlib import Path
import hashlib,json
BASE=Path('E:/FPGA_Enhance_Work')
ROOT=BASE/'road_enhanced_detection_20261031_r1'
INITIAL=BASE/'road_viewadapt_20261030_r1/export/model.pt'
ENHANCER=BASE/'road_student_fusion_20261031_r1/host/fusion.dll'
SEED=2026103127
EPOCHS=12
CHECKPOINTS=[4,8,12]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def f1(m):return 2*m['tp']/(2*m['tp']+m['fp']+m['fn'])
def gates(base,new):
    return dict(ap=new['ap50']>=base['ap50']+.005,precision=new['precision']>=base['precision'],
        recall=new['recall']>=base['recall']+.005,fp=new['fp']<=base['fp'],f1=f1(new)>=f1(base)+.005)
