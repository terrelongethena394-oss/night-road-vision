"""C/NumPy exact score calibration and output/input safety checks."""
import ctypes as ct,os,shutil,subprocess
import numpy as np
from road_viewadapt_common import *
from road_score_calibration import calibrate
from road_classwise_native import Box

def main():
 selected=read(ROOT/'selected_calibrated.json');assert selected['qualified'];gain=selected['chosen']['gain'];epoch=selected['chosen']['epoch'];out=ROOT/'calibration_c';out.mkdir()
 here=Path(__file__).resolve().parent
 for n in ['road_score_calibration.c','road_score_calibration.h']:shutil.copy2(here/n,out/n)
 for n in ['road_fp32.h','road_graph.h']:shutil.copy2(BASE/'road_accuracy_20261030_r1/firmware/source'/n,out/n)
 gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH'];dll=out/'calibration.dll'
 cmd=[str(gcc),'-O3','-std=c99','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror','-shared','-static-libgcc','-Wl,--export-all-symbols',str(out/'road_score_calibration.c'),'-lm','-o',str(dll)]
 p=subprocess.run(cmd,capture_output=True,text=True,env=env);assert p.returncode==0,p.stderr
 lib=ct.CDLL(str(dll));fn=lib.road_score_calibrate;fn.argtypes=[ct.POINTER(Box),ct.c_int,ct.c_float];fn.restype=ct.c_int
 def invoke(pred,g):
  z=np.asarray(pred,np.float32).reshape(-1,6);buf=(Box*302)();buf[0].order=buf[301].order=0x12345678
  for i,r in enumerate(z):buf[i+1]=Box(*map(float,r[:5]),int(r[5]),i)
  ptr=ct.cast(ct.byref(buf,ct.sizeof(Box)),ct.POINTER(Box));n=fn(ptr,len(z),g)
  assert n==len(z) and buf[0].order==buf[301].order==0x12345678
  a=np.array([[buf[i+1].x1,buf[i+1].y1,buf[i+1].x2,buf[i+1].y2,buf[i+1].score,buf[i+1].cls] for i in range(n)],np.float32).reshape(-1,6)
  assert a.tobytes()==calibrate(z,g).tobytes()
  for cls in [0,1]:assert sorted(map(tuple,z[z[:,5]==cls].tolist()))==sorted(map(tuple,a[a[:,5]==cls].tolist()))
  return a
 count=0
 for cohort in ['original320','low320']:
  rows=read(ROOT/'development'/f'epoch{epoch}'/cohort/'fused_predictions.json')
  for r in rows:invoke(r['detections'],gain);count+=1
 for g in [1.,gain,2.]:
  invoke([],g);invoke([[0,0,1,1,0,2],[0,0,1,1,1,3],[0,0,1,1,.25,1],[0,0,1,1,.25,0]],g)
 buf=(Box*1)(Box(0,0,1,1,.5,2,0));before=bytes(buf)
 for n,g in [(-1,1.),(301,1.),(1,0.),(1,float('nan'))]:assert fn(buf,n,g)<0 and bytes(buf)==before
 buf[0].score=float('inf');before=bytes(buf);assert fn(buf,1,gain)<0 and bytes(buf)==before
 write(out/'complete.json',dict(status='ALL640_CALIBRATED_SCORES_C_NUMPY_BYTE_EXACT',images=count,gain=gain,compiler=cmd,dll_sha256=sha(dll),selection_sha256=sha(ROOT/'selected_calibrated.json'),car_person_values_unchanged=True,guards_pass=True,invalid_inputs_rejected_without_mutation=True,hardware_access=False))
 print('VIEWADAPT_SCORE_C_EXACT',count,gain,flush=True)

if __name__=='__main__':main()
