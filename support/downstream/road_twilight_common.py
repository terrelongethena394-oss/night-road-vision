from pathlib import Path
import hashlib,json
ROOT=Path('E:/FPGA_Enhance_Work/road_twilight_20261027')
BASE=Path('E:/FPGA_Enhance_Work/road_detection_20261026')
LIGHT=Path('E:/FPGA_Enhance_Work/road_light_20261027')
NN=Path('E:/FPGA_Enhance_Work/road_arm_prototype_20261026')
TEACHER=BASE/'frozen/road4_best.pt'
TEACHER_SHA='98f46429cd431d735e276d7735f50f61811a70cbb5feb2a0475fba562449a46f'
SEED=2026102745
EPOCHS=16
CHECKPOINTS=[4,8,12,16]
QUOTA={'night':192,'dawn/dusk':160,'daytime':128}
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):Path(p).write_text(json.dumps(v,indent=2,ensure_ascii=False),encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
