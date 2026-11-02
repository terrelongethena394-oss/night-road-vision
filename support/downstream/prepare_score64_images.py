"""Clone only immutable test inputs and software; no failed first bitstream."""
from pathlib import Path
import json,shutil
BASE=Path('E:/FPGA_Enhance_Work/real_cnn_image_test_20261025')
ROOT=Path('E:/FPGA_Enhance_Work/real_cnn_image_test_score64_20261025')
ROOT.mkdir(exist_ok=True)
assert not (ROOT/'runtime_identity.json').exists()
for name in ('inputs','pc_roi_references'):shutil.copytree(BASE/name,ROOT/name,dirs_exist_ok=True)
for name in ('image_test.elf','run_fixed_image.tcl','start_fixed_image.tcl','photo_sources_and_attribution.json'):shutil.copy2(BASE/name,ROOT/name)
for name in ('case_manifest.json','cases.tcl'):
    text=(BASE/name).read_text(encoding='utf-8').replace(BASE.as_posix(),ROOT.as_posix())
    (ROOT/name).write_text(text,encoding='utf-8')
(ROOT/'board').mkdir(exist_ok=True)
print('SCORE64_INPUTS_CLONED_WITHOUT_OLD_BITSTREAM',flush=True)
