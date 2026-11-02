"""Prepare isolated board build using the corrected, frozen CNN IP."""
from pathlib import Path
import hashlib,json,shutil
from train_real_digit_cnn import OUT

ROOT=Path('E:/FPGA_Enhance_Work/camera_real_cnn_20261025')
HERE=Path(__file__).resolve().parent

def main():
    ROOT.mkdir(exist_ok=True);(ROOT/'rtl').mkdir(exist_ok=True)
    source=Path('E:/FPGA_Enhance_Work/camera_nn8_20261023/rtl/axis_rgb_bridge.v')
    shutil.copy2(source,ROOT/'rtl/axis_rgb_bridge.v')
    tcl=(HERE/'build_digit_board.tcl').read_text(encoding='utf-8')
    tcl=tcl.replace('E:/FPGA_Enhance_Work/camera_nn_digit_20261023',ROOT.as_posix())
    tcl=tcl.replace('E:/FPGA_Enhance_Work/digit_recognition_20261023/hls/digit_project/solution_100mhz/impl/ip',
        (OUT/'hls_corrected/real_cnn_project/solution_100mhz/impl/ip').as_posix())
    tcl=tcl.replace('xilinx.com:hls:digit_monitor:1.0','fpga.user:hls:real_digit_monitor:1.0')
    tcl=tcl.replace('DIGIT_BOARD_BUILD_PASS','REAL_CNN_BOARD_BUILD_PASS')
    (ROOT/'build_board.tcl').write_text(tcl,encoding='ascii')
    report=json.loads((OUT/'frozen_candidate.json').read_text(encoding='utf-8'))
    (ROOT/'model_identity.json').write_text(json.dumps(dict(model=report,source=str(OUT),
        hardware_downloaded=False,sd_written=False,stage='PREPARED_WAITING_FOR_CORRECTED_RTL_VERIFICATION'),indent=2),encoding='utf-8')
    print('ISOLATED_REAL_CNN_BOARD_PREPARED',str(ROOT),flush=True)

if __name__=='__main__':main()
