"""Equivalent C pixel preprocessing; no detector/ROI/metric changes."""
import ctypes as ct, os, time
import numpy as np
from road_enhanced_detection_common import BASE
from road_arm_common import preprocess400 as reference
from camera_snapshot_tools import words

class Preprocess:
    def __init__(self):
        self.dir=os.add_dll_directory('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin')
        self.lib=ct.CDLL(str(BASE/'road_car_roi_delivery_20261031_r1/board_candidate/firmware/host/post.dll'))
        self.up=ct.POINTER(ct.c_uint32);self.bp=ct.POINTER(ct.c_uint8)
        self.lib.road_preprocess400.argtypes=[self.up,self.bp];self.lib.road_preprocess400.restype=None
    def __call__(self,a):
        src=words(a).reshape(-1).copy();out=np.empty((320,320,3),np.uint8)
        self.lib.road_preprocess400(src.ctypes.data_as(self.up),out.ctypes.data_as(self.bp))
        return out

def audit():
    p=Preprocess();rng=np.random.default_rng(2026103199);a=rng.integers(0,256,(240,400,3),np.uint8)
    for _ in range(16):
        a=rng.integers(0,256,(240,400,3),np.uint8)
        assert np.array_equal(reference(a),p(a))
    result={'synthetic_cases':16,'byte_exact':True}
    for tag,fn in [('numpy',reference),('C',p)]:
        t=time.monotonic()
        for _ in range(20):fn(a)
        result[tag+'_seconds_each']=(time.monotonic()-t)/20
    return p,result

if __name__=='__main__':
    print(audit()[1],flush=True)
