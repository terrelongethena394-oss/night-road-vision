import ctypes as ct,os
from pathlib import Path
import numpy as np
from road_enhanced_detection_common import BASE
from shadowlift_lab import unpack
ROOT=BASE/'road_car_roi_trainaug_20261031_r1'
class Pixels:
    def __init__(self,dll=None):
        self.directory=os.add_dll_directory('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin');self.lib=ct.CDLL(str(dll or ROOT/'native_pixels/roi.dll'));self.up=ct.POINTER(ct.c_ubyte);self.wp=ct.POINTER(ct.c_uint32)
        self.fn=self.lib.road_native_car_roi;self.fn.argtypes=[self.up,ct.c_int,ct.c_int,self.wp];self.fn.restype=ct.c_int
    def begin(self,sensor):
        assert sensor.dtype==np.uint8 and sensor.shape==(480,800,3)
        self.source=np.ascontiguousarray(sensor[:,:,::-1]);self.before=self.source.tobytes()
    def image(self,r):
        dst=np.empty(96004,np.uint32);dst[-4:]=0xdeadbeef
        assert self.fn(self.source.ctypes.data_as(self.up),r['x'],r['y'],dst.ctypes.data_as(self.wp))==0 and np.all(dst[-4:]==0xdeadbeef)
        return unpack(dst[:96000]).reshape(240,400,3)
    def end(self):assert self.source.tobytes()==self.before
