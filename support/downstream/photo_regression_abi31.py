"""One real photo roundtrip after adding camera ABI31; no SD modifications."""
from pathlib import Path
from photo_station_core import STAGING,process_photo
from camera_station_core import CAMERA
from car_roi_delivery_common import read,write
old=read(STAGING/'actual_roundtrip_verified.json')
result=process_photo(old['input']['original_path'],notify=lambda s:print(s,flush=True))
assert result['firmware_abi']==31
previous=Path(old['packet_evidence']);current=Path(result['packet_evidence'])
same={name:(previous/name).read_bytes()==(current/name).read_bytes() for name in ['source800.bgr','raw.u32','enhanced.u32','boxes.f32','baseline.f32']}
assert all(same.values()),same
proof=dict(status='ABI31_PHOTO_REGRESSION_PASS',byte_exact_to_previous_ABI30=same,result=result,sd_written=False)
write(CAMERA/'photo_regression_verified.json',proof)
print('ABI31_PHOTO_REGRESSION_PASS',result['car_count'],round(result['board_processing_seconds'],2),flush=True)
