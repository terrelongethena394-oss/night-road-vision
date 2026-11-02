"""Real-photo paired-model preview, with actual C enhancement and LCD rendering."""
import ctypes as ct,os,subprocess
import numpy as np
from PIL import Image
from car_pair_common import *
from road_accuracy_common import sensor400
from camera_snapshot_tools import words

def main():
 assert read(ROOT/'post_complete.json')['images']==1472
 name='028357c9-e07642f7.jpg';image=ROUTE/'fresh/images'/name;sensor,raw=sensor400(image);out=ROOT/'fixtures/road';out.mkdir(parents=True)
 (out/'source800.bgr').write_bytes(sensor[:,:,::-1].tobytes());words(raw).tofile(out/'raw.u32')
 old=next(r for r in read(ROUTE/'fresh_evaluation/baseline/native/candidate_predictions.json') if r['name']==name);new=next(r for r in read(ROUTE/'fresh_evaluation/routed_low/native/candidate_predictions.json') if r['name']==name)
 cars=[]
 for tag,r in [('stable',old),('candidate',new)]:
  p=np.asarray(r['detections'],'<f4').reshape(-1,6);p=p[(p[:,5]==1)&(p[:,4]>=.25)];p.tofile(out/(tag+'.f32'));cars.append(len(p))
 cp=read(BASE/'road_retinex_noiseguard_arm_20261029_r1/c_complete.json');lib=ct.CDLL(str(Path(cp['attempt'])/'retinex.dll'))
 class Stats(ct.Structure):_fields_=[(n,ct.c_float) for n in ['mean_in','mean_out','noise_proxy','alpha','max_gain']]
 up=ct.POINTER(ct.c_uint32);fp=ct.POINTER(ct.c_float);lib.road_retinex_c.argtypes=[up,up,ct.c_uint,fp,ct.POINTER(Stats),ct.c_void_p,ct.c_void_p]
 a=words(raw).reshape(-1);b=np.empty_like(a);work=np.empty(17*96000+65536,np.float32);stats=Stats();assert lib.road_retinex_c(a.ctypes.data_as(up),b.ctypes.data_as(up),96000,work.ctypes.data_as(fp),ct.byref(stats),None,None)==0;b.tofile(out/'enhanced.u32')
 ui=np.array([1,1,1,0,0,0,cars[1],1,1,1,0,int(stats.mean_in),0,48,2,2,cars[0]],'<u4');ui.tofile(out/'ui.u32');env=dict(os.environ);env['PATH']='E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin;'+env['PATH']
 cmd=[str(APP/'host/render.exe'),str(out/'raw.u32'),str(out/'enhanced.u32'),str(out/'candidate.f32'),str(out/'stable.f32'),str(out/'ui.u32'),str(out/'frame.bgr')];p=subprocess.run(cmd,capture_output=True,text=True,env=env);assert p.returncode==0 and 'GUARDS_PASS' in p.stdout,p.stdout+p.stderr
 Image.fromarray(np.fromfile(out/'frame.bgr',np.uint8).reshape(480,800,3)[:,:,::-1]).save(out/'preview.png')
 write(out/'fixture.json',dict(source_photo=name,ground_truth=old['ground_truth'],stable_cars=cars[0],candidate_cars=cars[1],source_sha256=sha(out/'source800.bgr'),raw_sha256=sha(out/'raw.u32'),enhancement_sha256=sha(out/'enhanced.u32'),same_enhanced_background_both_sides=True,both_neural_inputs_raw=True,not_board_tested=True))
 print('CAR_PAIR_OFFLINE_PREVIEW',cars,flush=True)

if __name__=='__main__':main()
