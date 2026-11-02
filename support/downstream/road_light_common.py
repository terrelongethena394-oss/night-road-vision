from pathlib import Path
from road_adapt_common import BASE,NAMES,read,write,sha
ROOT=Path('E:/FPGA_Enhance_Work/road_light_20261027')
TEACHER=BASE/'frozen/road4_best.pt'
TEACHER_SHA='98f46429cd431d735e276d7735f50f61811a70cbb5feb2a0475fba562449a46f'
SEED=2026102707
VARIANTS={'c0625':.0625,'c09375':.09375,'c1250':.125}
EPOCHS=40
