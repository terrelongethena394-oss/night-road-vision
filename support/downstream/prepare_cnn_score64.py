"""Second isolated hardware revision; preserve first-route failure evidence."""
from pathlib import Path
import shutil
from train_real_digit_cnn import OUT

HERE=Path(__file__).resolve().parent

def main():
    src=OUT/'hls_corrected';dst=OUT/'hls_score64';dst.mkdir(exist_ok=True)
    for name in ('cnn_weights.h','digit_monitor.h','digit_monitor.cpp','cases.txt','cases.json','tb_digit.cpp','build.tcl','verify.tcl','cosim.tcl','export.tcl'):
        shutil.copy2(src/name,dst/name)
    shutil.copy2(HERE/'real_cnn_kernel.h',dst/'real_cnn_kernel.h')
    p=dst/'tb_digit.cpp';p.write_text(p.read_text().replace(src.as_posix(),dst.as_posix()),encoding='ascii')
    p=dst/'export.tcl';p.write_text(p.read_text().replace('-version 1.0','-version 1.1'),encoding='ascii')
    root=Path('E:/FPGA_Enhance_Work/camera_real_cnn_score64_20261025');root.mkdir(exist_ok=True);(root/'rtl').mkdir(exist_ok=True)
    old=Path('E:/FPGA_Enhance_Work/camera_real_cnn_20261025')
    shutil.copy2(old/'rtl/axis_rgb_bridge.v',root/'rtl/axis_rgb_bridge.v')
    tcl=(old/'build_board.tcl').read_text().replace(old.as_posix(),root.as_posix()).replace('hls_corrected/real_cnn_project','hls_score64/real_cnn_project').replace('fpga.user:hls:real_digit_monitor:1.0','fpga.user:hls:real_digit_monitor:1.1')
    (root/'build_board.tcl').write_text(tcl,encoding='ascii')
    print('SCORE64_ISOLATED_REVISION_PREPARED',flush=True)

if __name__=='__main__':main()
