"""Validate host C implementation, then build isolated ABI22 application."""
from pathlib import Path
import json
import numpy as np
from PIL import Image
import validate_retinex_c as v
import build_retinex_arm as b
from road_retinex_noiseguard import enhance

HERE=Path(__file__).resolve().parent
ROOT=Path('E:/FPGA_Enhance_Work/road_retinex_noiseguard_arm_20261029_r1')
PHOTOS=Path('E:/FPGA_Enhance_Work/road_retinex_noiseguard_20261029_r2')
NAMES=['a2a8d23a-90b0b3df','a32543af-7cf90f4a','c81ff2c0-420a8956']

def main():
    assert not ROOT.exists()
    v.ROOT=ROOT;v.CORE_SOURCE=HERE/'road_retinex_noiseguard_c.c'
    v.CORE_HEADER=HERE/'road_retinex_detail_c.h'
    v.REFERENCE_SOURCE=HERE/'road_retinex_noiseguard.py';v.REFERENCE_PRESET='guard_light';v.enhance=enhance
    v.EXTRA_INPUTS=[(n,np.array(Image.open(PHOTOS/n/'raw.png').convert('RGB'))) for n in NAMES[:2]]
    v.main()
    b.ROOT=ROOT;b.VERSION=22;b.DEFAULT_CAP=48
    b.CORE_SOURCE=v.CORE_SOURCE;b.CORE_HEADER=v.CORE_HEADER
    b.PHOTO_ROOT=PHOTOS;b.PHOTO_NAMES=NAMES;b.UI_LABEL='GUARD / RAW DET'
    b.main()
    (ROOT/'selection.json').write_text(json.dumps(dict(selected='guard_light',reason='Small visual improvement in dark grain; preserve structure rather than medium-strength filtering. Known-image development selection, not best-model claim.',previous='ABI21 retained; ABI18 remains formal camera fallback',pretrained_enhancement_weights=False,sd_written=False),indent=2),encoding='utf-8')

if __name__=='__main__':main()
