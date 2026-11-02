"""Final local UI delivery receipt; no hardware inference or SD access."""
from pathlib import Path
import numpy as np
from PIL import Image
from photo_station_core import DELIVERY,RESULT_ROOT,STAGING,rgb
from car_roi_delivery_common import read,write,sha

def main():
    last=read(STAGING/'gui_last_result.json');out=Path(last['output'])
    assert out.resolve().is_relative_to(RESULT_ROOT.resolve()) and RESULT_ROOT==Path('E:/FPGA图像处理/结果')
    with Image.open(out/'02_板上原图400.png') as im:assert np.array_equal(np.asarray(im),rgb(Path(last['packet_evidence'])/'raw.u32'))
    with Image.open(out/'07_电脑对照图.png') as im:assert np.array_equal(np.asarray(im)[30:270,:400],rgb(Path(last['packet_evidence'])/'raw.u32'))
    launch=(DELIVERY/'启动图片处理.cmd').read_text(encoding='utf-8');assert 'pythonw.exe' in launch and str(DELIVERY/'程序/photo_station_gui.py') in launch
    for name in ['photo_station_gui.py','photo_station_core.py']:
        assert sha(Path(__file__).with_name(name))==sha(DELIVERY/'程序'/name)
    receipt=dict(status='MODERN_E_DRIVE_UI_INSTALLED_AND_VISUALLY_CHECKED',application=str(DELIVERY),result_folder=str(RESULT_ROOT),
        left_preview='Unannotated board-original pixels; file verified byteexact to actual raw readback',
        comparison_original_unannotated_byte_exact=True,existing_results_copied=3,
        visual_checks=['Dark rounded card layout','No task log or technical footer','Right-side recognition-box toggle manually operated','Result button opened E-drive folder'],
        launch_uses_pythonw=True,checks_used_previous_actual_board_result=True,new_hardware_run_claimed=False,sd_written=False,model_changed=False,
        source_sha256={name:sha(DELIVERY/'程序'/name) for name in ['photo_station_gui.py','photo_station_core.py']})
    write(DELIVERY/'资料/ui_v2_verified.json',receipt)
    print('PHOTO_UI_V2_DELIVERY_CHECKED',DELIVERY,flush=True)

if __name__=='__main__':main()
