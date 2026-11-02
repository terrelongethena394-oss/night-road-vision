"""Integer brightness selector matches independent float mean and is immutable."""
import ctypes as ct,os,shutil,subprocess
import numpy as np
from road_brightness_route_common import *

class Router:
 def __init__(self):
  out=ROOT/'router_c';out.mkdir(exist_ok=True);src=Path(__file__).with_name('road_brightness_route.c');dll=out/'router.dll'
  if not (out/'build.json').exists():
   shutil.copy2(src,out/src.name);gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH'];cmd=[str(gcc),'-O3','-std=c99','-Wall','-Wextra','-Werror','-shared','-static-libgcc','-Wl,--export-all-symbols',str(out/src.name),'-o',str(dll)]
   p=subprocess.run(cmd,capture_output=True,text=True,env=env);assert p.returncode==0,p.stderr;write(out/'build.json',dict(command=cmd,source_sha256=sha(src),dll_sha256=sha(dll)))
  proof=read(out/'build.json');assert proof['source_sha256']==sha(src) and proof['dll_sha256']==sha(dll)
  self.lib=ct.CDLL(str(dll));self.fn=self.lib.road_brightness_route;self.fn.argtypes=[ct.POINTER(ct.c_uint32),ct.c_uint];self.fn.restype=ct.c_int
 def run(self,rgb):
  assert rgb.shape==(240,400,3) and rgb.dtype==np.uint8
  a=rgb.astype(np.uint32);buf=np.full(96002,0x12345678,np.uint32);buf[1:-1]=(a[:,:,0]|a[:,:,1]<<8|a[:,:,2]<<16).reshape(-1);before=buf.tobytes()
  p=ct.cast(ct.c_void_p(buf.ctypes.data+4),ct.POINTER(ct.c_uint32));actual=self.fn(p,96000);expected=float(((54*a[:,:,0]+183*a[:,:,1]+19*a[:,:,2])/256).mean())<=GATE_MEAN
  assert actual==expected and buf.tobytes()==before;return actual

def main():
 engine=Router();cases=[]
 for value in [0,47,48,49,255]:cases.append(np.full((240,400,3),value,np.uint8))
 for delta in [-1,1]:
  a=np.full((240,400,3),48,np.uint8);a[0,0,0]=48+delta;cases.append(a)
 rng=np.random.default_rng(SEED)
 for ceiling in [32,64,96,255]:
  for _ in range(8):cases.append(rng.integers(0,ceiling+1,(240,400,3),dtype=np.uint8))
 for a in cases:engine.run(a)
 assert engine.fn(None,96000)==-1
 a=(ct.c_uint32*1)(0);assert engine.fn(a,1)==-1
 write(ROOT/'router_c/complete.json',dict(status='INTEGER_ROUTE_FLOAT_REFERENCE_EXACT',cases=len(cases),threshold=GATE_MEAN,boundaries_tested=True,input_immutable=True,invalid_inputs_rejected=True,hardware_access=False));print('BRIGHTNESS_ROUTER_C_PROVED',len(cases),flush=True)

if __name__=='__main__':main()
