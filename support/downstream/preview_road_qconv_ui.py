"""Offline renderer layout QA using an archived frame; not a new board capture."""
from pathlib import Path
import os,struct,subprocess
import numpy as np
from PIL import Image
ROOT=Path('E:/FPGA_Enhance_Work/road_qconv_app_20261027')
OLD=Path('E:/FPGA_Enhance_Work/road_hybrid_20261027_r1/physical_full_r1/first_hybrid_full')
QAT=Path('E:/FPGA_Enhance_Work/road_realtime_20261027/exports/epoch8/host/02e67bab-27594c1d')
def main():
    out=ROOT/'layout_qa_r2';out.mkdir(exist_ok=False);gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=os.environ.copy();env['PATH']=str(gcc.parent)+';'+env['PATH']
    exe=out/'render.exe';subprocess.run([str(gcc),'-O2','-std=c99','-Wall','-Wextra','-Werror','-I'+str(ROOT/'source'),str(ROOT/'source/road_camera_draw.c'),str(Path(__file__).with_name('road_camera_draw_host.c')),'-o',str(exe)],check=True,env=env)
    ui=list(struct.unpack('<11I',(OLD/'ui.u32').read_bytes()));ui[3]=0;ui[6]=(QAT/'boxes400.f32').stat().st_size//24;ui[8]=1;ui[9]=ui[10]=0;(out/'ui.u32').write_bytes(struct.pack('<11I',*ui))
    subprocess.run([str(exe),str(OLD/'live400.u32'),str(OLD/'result400.u32'),str(QAT/'boxes400.f32'),str(out/'ui.u32'),str(out/'frame.bgr')],check=True,env=env)
    a=np.fromfile(out/'frame.bgr',np.uint8).reshape(480,800,3);Image.fromarray(a[:,:,::-1]).save(out/'offline_layout.png')
    (out/'README.txt').write_text('Offline UI layout render from archived input and candidate host detections. Not a new board capture or timing measurement. Placeholder processing time 0ms.\n')
if __name__=='__main__':main()
