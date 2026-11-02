"""Car-only postprocessing equals frozen all-class fusion then car filtering."""
import ctypes as ct,subprocess,os,shutil
import numpy as np
from car_pair_common import *
from road_classwise_native import Box
from road_accuracy_common import fuse,map_tile,TILES

class Post:
 def __init__(self):
  out=APP/'host';dll=out/'car_post.dll';gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH']
  cmd=[str(gcc),'-O3','-std=c99','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror','-shared','-static-libgcc','-Wl,--export-all-symbols','-I'+str(APP/'source'),str(APP/'source/road_car_pair_post.c'),str(APP/'source/road_vehicle_multiview.c'),'-lm','-o',str(dll)]
  p=subprocess.run(cmd,capture_output=True,text=True,env=env);assert p.returncode==0,p.stderr
  self.lib=ct.CDLL(str(dll));self.fn=self.lib.road_car_multiview;self.fn.argtypes=[ct.POINTER(Box),ct.c_int,ct.POINTER(Box),ct.POINTER(ct.c_int),ct.POINTER(Box),ct.c_int];self.fn.restype=ct.c_int;self.cmd=cmd
 def run(self,full,local):
  a=(Box*300)();b=(Box*900)();dst=(Box*302)();dst[0].order=dst[301].order=0x12345678
  for i,p in enumerate(full):a[i]=Box(*map(float,p[:5]),int(p[5]),i)
  for t,rows in enumerate(local):
   for i,p in enumerate(rows):b[t*300+i]=Box(*map(float,p[:5]),int(p[5]),i)
  aa=bytes(a);bb=bytes(b);ptr=ct.cast(ct.byref(dst,ct.sizeof(Box)),ct.POINTER(Box));n=self.fn(a,len(full),b,(ct.c_int*3)(*[len(z) for z in local]),ptr,300)
  assert 0<=n<=300 and dst[0].order==dst[301].order==0x12345678 and bytes(a)==aa and bytes(b)==bb
  result=np.array([[dst[i+1].x1,dst[i+1].y1,dst[i+1].x2,dst[i+1].y2,dst[i+1].score,dst[i+1].cls] for i in range(n)],'<f4').reshape(-1,6)
  ref=fuse(full,[map_tile(v,*TILES[t]) for t,v in enumerate(local)],.75);ref=ref[(ref[:,5]==1)&(ref[:,4]>=.25)];assert result.tobytes()==ref.tobytes();return result

def main():
 engine=Post();cohorts=[ROUTE/'fresh_evaluation/baseline/native',ROUTE/'fresh_evaluation/routed_low/native',ROUTE/'fresh_evaluation/routed_bright/native',ADAPT/'native_development/native'];counts={}
 for folder in cohorts:
  full=read(folder/'global_raw.json');local=[read(folder/f'tile_raw_{i}_local.json') for i in range(3)];reference=read(folder/'candidate_predictions.json')
  for at,r in enumerate(full):
   out=engine.run(r['detections'],[local[t][at] for t in range(3)]);ref=np.asarray(reference[at]['detections'],'<f4').reshape(-1,6);ref=ref[(ref[:,5]==1)&(ref[:,4]>=.25)];assert out.tobytes()==ref.tobytes()
  counts[str(folder)]=len(full)
 engine.run([], [[],[],[]])
 write(ROOT/'post_complete.json',dict(status='ALL1472_CAR_POST_C_NUMPY_AND_EXISTING_C_BYTE_EXACT',cohorts=counts,images=sum(counts.values()),input_immutable=True,output_canaries=True,compiler=engine.cmd,source_sha256=sha(APP/'source/road_car_pair_post.c'),dll_sha256=sha(APP/'host/car_post.dll'),hardware_access=False));print('CAR_PAIR_POST_EXACT',sum(counts.values()),flush=True)

if __name__=='__main__':main()
