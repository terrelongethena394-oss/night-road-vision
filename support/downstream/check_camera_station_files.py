from pathlib import Path
import py_compile,json
from camera_station_core import CAMERA
from photo_station_core import STAGING
for name in ['camera_station_core.py','photo_station_core.py','photo_station_gui.py','install_photo_station_ui_v2.py']:
    py_compile.compile(str(Path(__file__).parent/name),doraise=True)
print('CAMERA_PYTHON_COMPILE_PASS',flush=True)
for name in ['actual_camera_roundtrip_verified.json']:
    p=CAMERA/name
    if p.exists():
        r=json.loads(p.read_text(encoding='utf-8'));print(json.dumps({k:r[k] for k in ['status','source_kind','firmware_abi','camera_bank_byte_exact','frame_byte_exact','board_processing_seconds','car_count','pl_conv_calls','output']},ensure_ascii=False),flush=True)
for job in sorted((STAGING/'jobs').glob('camera_*'))[-1:]:
    p=job/'packet/request.log'
    if p.exists():print(p.read_text(encoding='utf-8',errors='replace')[-1200:],flush=True)
