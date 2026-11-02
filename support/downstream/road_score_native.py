"""Host C wrapper for fixed classwise score mapping, with exact independent checks."""
import ctypes as ct,os,shutil,subprocess
import numpy as np
from road_viewadapt_common import *
from road_score_calibration import calibrate
from road_classwise_native import Box

class Calibrator:
 def __init__(self,root):
  out=root/'calibration_c';out.mkdir(exist_ok=True);here=Path(__file__).resolve().parent
  sources={n:sha(here/n) for n in ['road_score_calibration.c','road_score_calibration.h']}
  gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');dll=out/'calibration.dll'
  if not (out/'build.json').exists():
   for n in sources:shutil.copy2(here/n,out/n)
   for n in ['road_fp32.h','road_graph.h']:shutil.copy2(BASE/'road_accuracy_20261030_r1/firmware/source'/n,out/n)
   env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH'];cmd=[str(gcc),'-O3','-std=c99','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror','-shared','-static-libgcc','-Wl,--export-all-symbols',str(out/'road_score_calibration.c'),'-lm','-o',str(dll)]
   p=subprocess.run(cmd,capture_output=True,text=True,env=env);assert p.returncode==0,p.stderr
   write(out/'build.json',dict(compiler=cmd,sources=sources,dll_sha256=sha(dll)))
  receipt=read(out/'build.json');assert receipt['sources']==sources and receipt['dll_sha256']==sha(dll)
  self.lib=ct.CDLL(str(dll));self.fn=self.lib.road_score_calibrate_classwise;self.fn.argtypes=[ct.POINTER(Box),ct.c_int,ct.c_float,ct.c_float];self.fn.restype=ct.c_int
 def run(self,pred,gains):
  z=np.asarray(pred,np.float32).reshape(-1,6);before=z.tobytes();buf=(Box*302)();buf[0].order=buf[301].order=0x12345678
  for i,r in enumerate(z):buf[i+1]=Box(*map(float,r[:5]),int(r[5]),i)
  ptr=ct.cast(ct.byref(buf,ct.sizeof(Box)),ct.POINTER(Box));n=self.fn(ptr,len(z),*gains)
  assert n==len(z) and buf[0].order==buf[301].order==0x12345678 and z.tobytes()==before
  actual=np.array([[buf[i+1].x1,buf[i+1].y1,buf[i+1].x2,buf[i+1].y2,buf[i+1].score,buf[i+1].cls] for i in range(n)],'<f4').reshape(-1,6)
  assert actual.tobytes()==calibrate(z,gains).tobytes()
  for cls in [0,1]:assert sorted(map(tuple,z[z[:,5]==cls].tolist()))==sorted(map(tuple,actual[actual[:,5]==cls].tolist()))
  return actual

def main():
 selected=read(ROOT/'selected_classcalibrated.json');assert selected['qualified'];chosen=selected['chosen'];engine=Calibrator(ROOT);count=0
 for cohort in ['original320','low320']:
  for r in read(ROOT/'development'/f"epoch{chosen['epoch']}"/cohort/'fused_predictions.json'):engine.run(r['detections'],chosen['gains']);count+=1
 for gains in [[1.,1.],chosen['gains'],[2.,2.]]:
  engine.run([],gains);engine.run([[0,0,1,1,0,2],[0,0,1,1,1,3],[0,0,1,1,.25,1],[0,0,1,1,.25,0]],gains)
 b=(Box*1)(Box(0,0,1,1,.5,2,0));before=bytes(b)
 for n,tg,bg in [(-1,1.,1.),(301,1.,1.),(1,0.,1.),(1,1.,float('nan'))]:assert engine.fn(b,n,tg,bg)<0 and bytes(b)==before
 b[0].score=float('inf');before=bytes(b);assert engine.fn(b,1,*chosen['gains'])<0 and bytes(b)==before
 write(ROOT/'calibration_c/complete.json',dict(status='ALL640_CLASS_CALIBRATION_C_NUMPY_BYTE_EXACT',images=count,gains=chosen['gains'],guards_pass=True,input_immutable=True,car_person_values_unchanged=True,invalid_inputs_rejected_without_mutation=True,selection_sha256=sha(ROOT/'selected_classcalibrated.json'),hardware_access=False));print('VIEWADAPT_CLASS_SCORE_C_EXACT',count,chosen['gains'],flush=True)

if __name__=='__main__':main()
