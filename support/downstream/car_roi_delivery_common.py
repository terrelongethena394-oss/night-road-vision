from pathlib import Path
import ctypes as ct,os
import numpy as np
from road_enhanced_detection_common import BASE,INITIAL,read,write,sha,gates,f1
from native_car_roi_20261031 import Pixels
ROOT=BASE/'road_car_roi_delivery_20261031_r1'
STUDY=BASE/'road_car_roi_trainaug_20261031_r1'
CHECKPOINT=BASE/'road_allview_gammafit_20261031_r1/frozen/raw8/model.pt'
SEED=2026103191
class Native:
    def __init__(self):
        self.directory=os.add_dll_directory('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin');self.lib=ct.CDLL(str(ROOT/'c_proof/roi_verify.dll'));self.fp=ct.POINTER(ct.c_float);self.ip=ct.POINTER(ct.c_int)
        self.lib.road_roi_plan.argtypes=[self.fp,ct.c_int,self.ip,self.ip];self.lib.road_roi_plan.restype=ct.c_int
        self.lib.road_roi_refine.argtypes=[self.fp,ct.c_int,ct.c_int,self.ip,self.ip,self.fp,self.ip,self.fp];self.lib.road_roi_refine.restype=ct.c_int
    def plan(self,base):
        a=np.ascontiguousarray(base,np.float32).reshape(-1,6);old=a.tobytes();idx=np.full(10,123456,np.int32);xy=np.full(18,123456,np.int32);ptr=lambda x:ct.cast(ct.c_void_p(x.ctypes.data+4),self.ip)
        n=self.lib.road_roi_plan(a.ctypes.data_as(self.fp),len(a),ptr(idx),ptr(xy));assert 0<=n<=8 and a.tobytes()==old and np.all(idx[[0,-1]]==123456) and np.all(xy[[0,-1]]==123456)
        return [dict(index=int(idx[i+1]),x=int(xy[1+2*i]),y=int(xy[2+2*i]),width=160,height=96) for i in range(n)]
    def refine(self,base,rois,local):
        a=np.ascontiguousarray(base,np.float32).reshape(-1,6);before=a.tobytes();k=len(rois);indices=np.zeros(8,np.int32);xy=np.zeros(16,np.int32);counts=np.zeros(8,np.int32);p=np.zeros((8,300,6),np.float32)
        assert k==len(local)<=8
        for i,(r,boxes) in enumerate(zip(rois,local)):
            b=np.asarray(boxes,np.float32).reshape(-1,6);assert len(b)<=300;indices[i]=r['index'];xy[2*i:2*i+2]=[r['x'],r['y']];counts[i]=len(b);p[i,:len(b)]=b
        pb=p.tobytes();out=np.full((302,6),np.float32(12345.25));ptr=ct.cast(ct.c_void_p(out.ctypes.data+24),self.fp)
        n=self.lib.road_roi_refine(a.ctypes.data_as(self.fp),len(a),k,indices.ctypes.data_as(self.ip),xy.ctypes.data_as(self.ip),p.ctypes.data_as(self.fp),counts.ctypes.data_as(self.ip),ptr)
        assert 0<=n<=300 and a.tobytes()==before and p.tobytes()==pb and np.all(out[[0,-1]]==np.float32(12345.25));return out[1:1+n].copy()
