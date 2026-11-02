"""Portable C kernel and C postprocessing for one frozenallview candidate."""
from pathlib import Path
import ctypes as ct,os
import numpy as np
from road_enhanced_detection_common import BASE,read,write,sha
from shadowlift_lab import words,unpack
from confirm_car_zoom_native import BaseFusion
from prove_balanced_car_c import RefinerC
from study_car_zoom_20261030 import map_zoom,XS
from evaluate_car_boxrefine import eligible,fuse_refined
ROOT=BASE/'road_allview_enhance_20261031_r1'
class Engine:
    def __init__(self):
        self.directory=os.add_dll_directory('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin');p=ROOT/'c_proof/enhance.dll';self.lib=ct.CDLL(str(p))
        class Stats(ct.Structure):_fields_=[(n,ct.c_float) for n in ['mean_in','mean_out','noise_proxy','alpha','max_gain']]
        self.Stats=Stats;self.up=ct.POINTER(ct.c_uint32);self.fp=ct.POINTER(ct.c_float);self.work=np.empty(32*96000+65540,np.float32);self.work.view(np.uint32)[-4:]=0x7fcabcde
        self.lib.road_retinex_c.argtypes=[self.up,self.up,ct.c_uint,self.fp,ct.POINTER(Stats),ct.c_void_p,ct.c_void_p]
    def run(self,a):
        raw=words(a).reshape(-1).copy();before=raw.copy();dst=np.empty(96004,np.uint32);dst[-4:]=0xdeadbeef;stats=self.Stats()
        assert self.lib.road_retinex_c(raw.ctypes.data_as(self.up),dst.ctypes.data_as(self.up),96000,self.work.ctypes.data_as(self.fp),ct.byref(stats),None,None)==0
        assert np.array_equal(raw,before) and np.all(dst[-4:]==0xdeadbeef) and np.all(self.work.view(np.uint32)[-4:]==0x7fcabcde)
        return unpack(dst[:96000]).reshape(240,400,3)
class Post:
    def __init__(self):
        self.base=BaseFusion();self.refiner=RefinerC();self.params=read(BASE/'road_car_balanced_20261030_r1/selected.json')['chosen']['source']
    def run(self,views,sensor,prove_numpy=False):
        import road_accuracy_common as ac
        a=self.base.run(views[0],views[1:4],.75);a=a[a[:,5]==1];strong=a[a[:,4]>=.25]
        mapped=[map_zoom(views[4+j],x,152) for j,x in enumerate(XS)];outputs=[np.zeros((len(p),5),np.float32) for p in mapped];count=0;self.refiner.begin(sensor)
        for j,pp in enumerate(mapped):
            for i,b in enumerate(pp):
                if not eligible(b,strong):continue
                im,meta=self.refiner.crop(b);outputs[j][i]=self.refiner.predict(im,meta);count+=1
        self.refiner.end();result=self.refiner.fuse(a,views[4:],outputs,self.params)
        if prove_numpy:
            b=ac.fuse(views[0],[ac.map_tile(views[j+1],*ac.TILES[j]) for j in range(3)],.75);b=b[b[:,5]==1];assert a.tobytes()==b.tobytes()
            q=fuse_refined(b,mapped,outputs,self.params['strength'],self.params['cap'],self.params['class_gate']);assert q.shape==result.shape and np.max(np.abs(q-result),initial=0)<=.0001
        return result,count
