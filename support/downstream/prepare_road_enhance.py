"""Freeze a small validation-only tone-curve search and prove C/NumPy arithmetic."""
from pathlib import Path
import ctypes,os,shutil,subprocess
import numpy as np
from road_enhance_common import ROOT,NN,OLD,CAPS,GAMMA_LIFT,enhance,write,sha
HERE=Path(__file__).resolve().parent
def main():
 ROOT.mkdir(exist_ok=False);src=ROOT/'source';src.mkdir()
 for n in ['road_enhance.c','road_enhance.h','road_enhance_common.py','prepare_road_enhance.py']:shutil.copy2(HERE/n,src/n)
 (src/'road_enhance_tables.h').write_text('#ifndef ROAD_ENHANCE_TABLES_H\n#define ROAD_ENHANCE_TABLES_H\nstatic const unsigned char ROAD_GAMMA_LIFT[256]={'+','.join(map(str,GAMMA_LIFT))+'};\n#endif\n',encoding='ascii')
 write(ROOT/'protocol.json',dict(status='FROZEN_BEFORE_ENHANCED_DETECTION_EVALUATION',algorithm='Gamma0.65 positive lift, cap16/24/32, max gain2, dark-pixel mask below RGBmax192, common RGB ratio; integer whole-frame luma gate full<=40, bypass>=80, linear blend between',caps=CAPS,selection='Old validation320 only; require night mAP>=.95 raw, overall>=.97 raw, night person recall>=.9 raw; among passing choose highest nightAP, ties smaller cap. If none, preserve explicit experimental status, integrate mild16 for functional comparison only.',detection_weights_sha256=sha(NN/'weights.f32'),bit_sha256=sha(OLD/'display.bit'),neural_enhancer=False,enhancement_processor='ARM',no_training=True,sd_written=False,hardware_access=False,source_sha256={p.name:sha(p) for p in src.iterdir()}))
 gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=os.environ.copy();env['PATH']=str(gcc.parent)+';'+env['PATH'];dll=ROOT/'enhance.dll'
 p=subprocess.run([str(gcc),'-O3','-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-shared','-I'+str(src),str(src/'road_enhance.c'),'-o',str(dll)],env=env,capture_output=True,text=True);(ROOT/'native_build.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
 class Stats(ctypes.Structure):_fields_=[(n,ctypes.c_uint32) for n in ['mean_in','mean_out','alpha','cap','changed','max_delta']]
 lib=ctypes.CDLL(str(dll));fn=lib.road_enhance;fn.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint,ctypes.c_uint,ctypes.POINTER(Stats),ctypes.c_void_p,ctypes.c_void_p];fn.restype=ctypes.c_int
 rng=np.random.default_rng(2026102734);images=[np.zeros((240,400,3),np.uint8),np.full((240,400,3),255,np.uint8),rng.integers(0,256,(240,400,3),np.uint8),rng.integers(0,40,(240,400,3),np.uint8)]
 images+=[np.repeat(np.arange(256,dtype=np.uint8)[None,:,None],3,axis=2)]
 for f in (NN/'cases').glob('*/input400.u32'):
  w=np.fromfile(f,'<u4').reshape(240,400);images.append(np.stack([w&255,(w>>8)&255,(w>>16)&255],2).astype(np.uint8))
 checks=0
 for a in images:
  words=a[:,:,0].astype(np.uint32)|(a[:,:,1].astype(np.uint32)<<8)|(a[:,:,2].astype(np.uint32)<<16);words=np.ascontiguousarray(words)
  for mode in [0,1,2]:
   for cap in CAPS:
    guard=np.full(words.size+32,0xa5a5a5a5,np.uint32);out=guard[16:-16];s=Stats();assert fn(words.ctypes.data,out.ctypes.data,words.size,mode,cap,ctypes.byref(s),None,None)==0
    ref,stats=enhance(a,mode,cap);expected=ref[:,:,0].astype(np.uint32)|(ref[:,:,1].astype(np.uint32)<<8)|(ref[:,:,2].astype(np.uint32)<<16)
    assert out.tobytes()==expected.tobytes() and {n:getattr(s,n) for n,_ in Stats._fields_}==stats
    assert np.all(guard[:16]==0xa5a5a5a5) and np.all(guard[-16:]==0xa5a5a5a5)
    assert np.all(ref>=a) and stats['max_delta']<=cap+1
    if mode==0 or stats['alpha']==0:assert np.array_equal(ref,a)
    checks+=1
 write(ROOT/'numeric_complete.json',dict(status='NATIVE_C_NUMPY_EXACT_BOUNDARIES_AND_ALL8_FROZEN_INPUTS',checks=checks,guard_bytes_each_side=64,dll_sha256=sha(dll),source_sha256={p.name:sha(p) for p in src.iterdir()},hardware_access=False));print('ROAD_ENHANCE_C_NUMPY_EXACT',checks,flush=True)
if __name__=='__main__':main()
