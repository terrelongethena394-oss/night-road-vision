from pathlib import Path
import os,subprocess,shutil
import numpy as np
from road_enhanced_detection_common import BASE,read,write,sha
from native_car_roi_20261031 import ROOT,Pixels
from pilot_car_roi_verify_20261031 import roi_pixels
def main():
    out=ROOT/'native_pixels';assert not out.exists();out.mkdir();source=Path(__file__).with_name('road_native_car_roi.c');shutil.copy2(source,out/source.name)
    gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH'];cmd=[str(gcc),'-shared','-O2','-std=c99','-Wall','-Wextra','-Werror',str(out/source.name),'-o',str(out/'roi.dll')]
    p=subprocess.run(cmd,capture_output=True,text=True,env=env);(out/'build.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
    e=Pixels();rng=np.random.default_rng(2026103183);cases=[np.zeros((480,800,3),np.uint8),np.full((480,800,3),255,np.uint8),rng.integers(0,32,(480,800,3),np.uint8),rng.integers(0,256,(480,800,3),np.uint8)];tests=[]
    for i,a in enumerate(cases):
        e.begin(a)
        for x,y in [(0,0),(640,384),(123,177),(321,111)]:
            r=dict(x=x,y=y);b=e.image(r);ref=roi_pixels(a,r);assert b.tobytes()==ref.tobytes();tests.append(dict(case=i,x=x,y=y,byte_exact=True))
        e.end()
    write(out/'complete.json',dict(status='EXACT_NATIVE_ROI_C_KERNEL_PROVED_NOT_MODEL_ACCURACY',cases=len(tests),source_immutable=True,output_canary=True,byte_exact_to_frozen_numpy=True,source_sha256=sha(out/source.name),dll_sha256=sha(out/'roi.dll'),compiler=cmd,hardware_access=False,sd_written=False));print('NATIVE_CAR_ROI_PIXELS_BYTE_EXACT',len(tests),flush=True)
if __name__=='__main__':main()
