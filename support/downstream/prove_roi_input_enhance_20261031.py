"""Portable C transform check only; not a detector accuracy or board claim."""
from pathlib import Path
import ctypes as ct,os,subprocess,shutil
import numpy as np
from road_enhanced_detection_common import BASE,read,write,sha
from study_roi_enhancement_attribution_20261031 import ROOT,METHODS,enhance
from prove_student_fusion_20261031 import Engine
from camera_snapshot_tools import words

class InputEngine:
    def __init__(self):
        self.dir=os.add_dll_directory('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin');self.lib=ct.CDLL(str(ROOT/'pixel_c/enhance.dll'));self.up=ct.POINTER(ct.c_uint32)
        self.lib.road_roi_input_enhance.argtypes=[self.up,self.up,self.up,ct.c_int];self.lib.road_roi_input_enhance.restype=ct.c_int;self.learned=Engine()
    def run(self,a,method,bright=None):
        n=METHODS.index(method);src=words(a).reshape(-1).copy();before=src.copy()
        if bright is None:bright=self.learned.run(a) if 1<=n<=4 else a
        b=words(bright).reshape(-1).copy();dst=np.empty(96004,np.uint32);dst[-4:]=0xdeadbeef
        assert self.lib.road_roi_input_enhance(src.ctypes.data_as(self.up),b.ctypes.data_as(self.up),dst.ctypes.data_as(self.up),n)==0
        assert np.array_equal(src,before) and np.all(dst[-4:]==0xdeadbeef)
        q=dst[:96000].reshape(240,400);return np.stack([q&255,(q>>8)&255,(q>>16)&255],2).astype(np.uint8)

def main():
    out=ROOT/'pixel_c';out.mkdir(exist_ok=True);src=Path(__file__).with_name('road_roi_input_enhance.c');shutil.copy2(src,out/src.name)
    gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH']
    cmd=[str(gcc),'-shared','-O2','-std=c99','-Wall','-Wextra','-Werror','-msse2','-mfpmath=sse','-ffp-contract=off',str(src),'-lm','-o',str(out/'enhance.dll')]
    p=subprocess.run(cmd,capture_output=True,text=True,env=env);(out/'build.log').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stderr
    e=InputEngine();rng=np.random.default_rng(2026103107)
    aa=[np.zeros((240,400,3),np.uint8),np.full((240,400,3),96,np.uint8),rng.integers(0,48,(240,400,3),np.uint8),rng.integers(0,80,(240,400,3),np.uint8)];rows=[]
    for i,a in enumerate(aa):
        bright=e.learned.run(a)
        for method in METHODS:
            expected=enhance(a,method,bright);actual=e.run(a,method,bright);d=np.abs(expected.astype(np.int16)-actual.astype(np.int16))
            assert d.max()<=1 and d.mean()<=.01,(i,method,d.max(),d.mean())
            rows.append(dict(case=i,method=method,max_abs=int(d.max()),mean_abs=float(d.mean()),byte_exact=bool(d.max()==0)))
    write(out/'complete.json',dict(status='SYNTHETIC_C_PIXEL_TRANSFORM_CHECK_ONLY',tests=rows,source_sha256=sha(src),dll_sha256=sha(out/'enhance.dll'),command=cmd,detector_accuracy_evidence=False,new_photographs_used=False,hardware_access=False,sd_written=False))
    print('ROI_INPUT_ENHANCE_C_SYNTHETIC_PASS',len(rows),flush=True)

if __name__=='__main__':main()
