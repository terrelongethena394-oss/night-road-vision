"""Portable C fusion proof on cached actual-C network outputs; no hardware."""
import ctypes as ct,os,shutil,subprocess
from road_classwise_common import *
HERE=Path(__file__).resolve().parent
class Box(ct.Structure):_fields_=[(k,ct.c_float) for k in ['x1','y1','x2','y2','score']]+[('cls',ct.c_int),('order',ct.c_int)]

class Engine:
 def __init__(self,root):
  out=root/'c_fusion';out.mkdir(exist_ok=True)
  for n in ['road_vehicle_classwise.c','road_vehicle_classwise.h']:shutil.copy2(HERE/n,out/n)
  for n in ['road_fp32.h','road_graph.h']:shutil.copy2(OLD/'firmware/source'/n,out/n)
  gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH']
  dll=out/'classwise.dll';cmd=[str(gcc),'-O3','-std=c99','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror','-shared','-static-libgcc','-Wl,--export-all-symbols',str(out/'road_vehicle_classwise.c'),'-lm','-o',str(dll)]
  p=subprocess.run(cmd,capture_output=True,text=True,env=env);assert p.returncode==0,p.stderr
  self.lib=ct.CDLL(str(dll));self.fn=self.lib.road_vehicle_classwise;self.fn.argtypes=[ct.POINTER(Box),ct.c_int,ct.POINTER(Box),ct.POINTER(ct.c_int),ct.POINTER(ct.c_float),ct.POINTER(Box),ct.c_int];self.fn.restype=ct.c_int
  write(out/'build.json',dict(compiler=cmd,dll_sha256=sha(dll),source_sha256=sha(out/'road_vehicle_classwise.c'),hardware_access=False))
 def run(self,full,localtiles,weights):
  a=(Box*300)();b=(Box*900)();dst=(Box*302)()
  for j,p in enumerate(full):a[j]=Box(*map(float,p[:5]),int(p[5]),j)
  for t,ps in enumerate(localtiles):
   for j,p in enumerate(ps):b[t*300+j]=Box(*map(float,p[:5]),int(p[5]),j)
  aa=bytes(a);bb=bytes(b);dst[0].order=dst[301].order=0x12345678
  ptr=ct.cast(ct.byref(dst,ct.sizeof(Box)),ct.POINTER(Box))
  n=self.fn(a,len(full),b,(ct.c_int*3)(*[len(v) for v in localtiles]),(ct.c_float*4)(*weights),ptr,300)
  assert 0<=n<=300 and dst[0].order==dst[301].order==0x12345678 and bytes(a)==aa and bytes(b)==bb
  return np.array([[dst[i+1].x1,dst[i+1].y1,dst[i+1].x2,dst[i+1].y2,dst[i+1].score,dst[i+1].cls] for i in range(n)],'<f4').reshape(-1,6)

def apply_cached(engine,folder,weights,out,tag):
 full=read(folder/'global_raw.json');local=[read(folder/('tile_raw_'+str(i)+'_local.json')) for i in range(3)]
 records=[];car_point_diffs=0
 uniform=read(folder/'candidate_predictions.json')
 for at,r in enumerate(full):
  tiles=[local[i][at] for i in range(3)]
  pred=engine.run(r['detections'],tiles,weights);mapped=[map_tile(v,*[(0,120),(200,120),(400,120)][i]) for i,v in enumerate(tiles)]
  reference=fuse(r['detections'],mapped,weights)
  assert pred.shape==reference.shape and pred.tobytes()==reference.tobytes(),(tag,r['name'])
  if weights==[0.,.75,.75,.75]:assert pred.tobytes()==np.asarray(uniform[at]['detections'],'<f4').tobytes()
  a=np.asarray(uniform[at]['detections'],np.float32).reshape(-1,6);a=a[(a[:,5]==1)&(a[:,4]>=.25)];b=pred[(pred[:,5]==1)&(pred[:,4]>=.25)]
  if sorted(map(tuple,a.tolist()))!=sorted(map(tuple,b.tolist())):car_point_diffs+=1
  records.append(dict(name=r['name'],timeofday=r['timeofday'],ground_truth=r['ground_truth'],detections=pred.tolist()))
 m=metrics(records);write(out/(tag+'_predictions.json'),records);write(out/(tag+'_metrics.json'),m)
 return dict(metrics=m,all_c_numpy_fusion_byte_exact=True,input_immutable=True,output_guards_pass=True,car_operating_point_different_images=car_point_diffs)

def main():
 selected=read(ROOT/'selected.json');assert selected['qualified'];out=ROOT/'reused_low320';out.mkdir();engine=Engine(ROOT)
 raw=read(LOW/'native/baseline_metrics.json')
 current=apply_cached(engine,LOW/'native',[0.,.75,.75,.75],out,'current')
 candidate=apply_cached(engine,LOW/'native',selected['chosen']['weights'],out,'candidate')
 g=gates(raw,current['metrics'],candidate['metrics']);result=dict(status='REUSED_LOW320_REGRESSION_PASS' if all(g.values()) else 'REUSED_LOW320_REGRESSION_REJECTED_NO_NEW_TEST',passes=all(g.values()),gates=g,current=current,candidate=candidate,source='Reused previously evaluated low320, descriptive regression only; not new independent evidence',selection_sha256=sha(ROOT/'selected.json'),hardware_access=False,sd_written=False)
 write(ROOT/'regression.json',result);print('CLASSWISE_REUSED_REGRESSION',result['status'],g,'before',combined(current['metrics']),'after',combined(candidate['metrics']),flush=True)
if __name__=='__main__':main()
