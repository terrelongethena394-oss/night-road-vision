"""Independent ABI28 validation; simulated packets never count as board proof."""
from pathlib import Path
import ctypes as ct,os,struct,subprocess
import numpy as np
from PIL import Image
from balanced_board_tools import ROOT,APP,STUDY,fnv
from car_box_refine_common import BASE,read,write,sha
from camera_snapshot_tools import words,rgb
from prove_balanced_car_c import RefinerC
from prove_car_zoom_c import ZoomC
from confirm_car_zoom_native import BaseFusion
from road_classwise_native import Box
from evaluate_car_boxrefine import eligible
from study_car_zoom_20261030 import map_zoom,XS
from audit_bright_detector_20261030 import Enhancer

def decode_boxes(decoded):
 lib=ct.CDLL(str(BASE/'road_car_bright_20261030_r1/firmware/host/post.dll'));fp=ct.POINTER(ct.c_float)
 lib.road_nms.argtypes=[fp,ct.POINTER(Box),ct.POINTER(Box),ct.c_int,ct.c_float,ct.c_float];lib.road_nms.restype=ct.c_int
 lib.road_boxes_to400.argtypes=[ct.POINTER(Box),ct.c_int];lib.road_boxes_to400.restype=None
 a=np.ascontiguousarray(decoded,np.float32);assert a.size==56700 and np.isfinite(a).all()
 candidates=(Box*6300)();out=(Box*300)();n=lib.road_nms(a.ctypes.data_as(fp),candidates,out,300,.001,.6);assert 0<=n<=300
 lib.road_boxes_to400(out,n)
 return np.array([[out[i].x1,out[i].y1,out[i].x2,out[i].y2,out[i].score,out[i].cls] for i in range(n)],np.float32).reshape(-1,6)

def validate(out,kind,physical=True):
 out=Path(out);proof=read(APP/'arm_complete.json');m=struct.unpack('<208I',(out/'mail.bin').read_bytes())
 if physical:
  assert (out/'packet_origin.txt').read_text().strip()=='actual_hardware_jtag_readback'
  assert 'BALANCED_BOARD_PACKET_READY' in (out/'request.log').read_text(encoding='utf-8',errors='replace')
 else:assert (out/'packet_origin.txt').read_text().strip()=='SIMULATED_HOST_PACKET_NOT_BOARD_PROOF'
 assert m[0]==0x524f4144 and m[1]==28 and m[2]==3 and m[57]==1 and m[155]==kind and m[156]==m[158]==1
 assert m[93]==m[99]==2 and m[72]==m[132]==2 and m[163]==1 and m[199]==0x42414c32
 assert m[6]==m[35]==m[41]==m[74]==0 and m[30]==0x7084 and m[40]==0x5640
 assert m[17]==m[161]==proof['weight_fnv']['detector'] and m[162]==m[192]==m[193]==proof['weight_fnv']['refiner']
 assert m[144]==0x1A300000 and m[149:152]==(1152000,800,480) and m[159]==0x46524f5a
 assert m[176:179]==(0x1C000000,0x1C120000,152) and m[186:189]==(0x1C200000,0x1C240000,0x1C250000)
 assert m[191]==17549 and m[195]==5 and m[196:199]==(0x3f000000,0x3dcccccd,0)
 source=(out/'source800.bgr').read_bytes();assert fnv(source)==m[145]==m[148]
 if kind==4:assert source==(out/'camera_bank.bgr').read_bytes() and m[56]==0
 else:assert m[56]==1
 sensor=np.frombuffer(source,np.uint8).reshape(480,800,3)[:,:,::-1].copy()
 full=((sensor.astype(np.uint16).reshape(240,2,400,2,3).sum(axis=(1,3))+2)//4).astype(np.uint8)
 rawviews=[full]+[sensor[120:360,x:x+400] for x in [0,200,400]]
 files=['raw.u32']+[f'raw_tile{i}.u32' for i in range(3)]
 for i,(image,name) in enumerate(zip(rawviews,files)):
  assert words(image).tobytes()==(out/name).read_bytes()
  assert fnv(words(image).tobytes())==(m[16] if i==0 else m[132+i])
 z=full.astype(np.uint64);dark=int((54*z[:,:,0]+183*z[:,:,1]+19*z[:,:,2]).sum())<=48*256*96000
 assert m[189]==int(dark) and m[104]==(357 if dark else 204) and m[169]==204 and m[170]==(153 if dark else 0) and m[190]==(3 if dark else 0)
 pix=ZoomC();native_tasks=[(name,f'decoded_base{i}.f32') for i,name in enumerate(files)]
 if dark:
  for i,x in enumerate(XS):
   expected=pix.image(sensor,x,152);name=f'zoom{i}.u32';assert words(expected).tobytes()==(out/name).read_bytes() and fnv((out/name).read_bytes())==m[180+i]
   native_tasks.append((name,f'decoded_zoom{i}.f32'))
 expected=Enhancer().run(full);actual=rgb(out/'enhanced.u32');delta=np.abs(actual.astype(np.int16)-expected.astype(np.int16));assert delta.max()<=1 and delta.mean()<=.01
 # Independent CPU network on every actual board input, not on fixture copies.
 env=dict(os.environ);env['PATH']='E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin;'+env['PATH'];exe=BASE/'road_local_enhance_20261029_r2/host/road_ap.exe'
 neural=[]
 for i,(input_name,decode_name) in enumerate(native_tasks):
  folder=out/'native'/str(i);folder.mkdir(parents=True,exist_ok=False)
  p=subprocess.run([str(exe),str(APP/'runtime/weights.f32'),str(out/input_name),str(folder)],capture_output=True,text=True,env=env,timeout=90)
  assert p.returncode==0 and 'ROAD_FP32_HOST_DONE' in p.stdout
  a=np.fromfile(out/decode_name,'<f4');b=np.fromfile(folder/'decoded.f32','<f4');assert a.shape==b.shape and np.isfinite(a).all()
  d=np.abs(a-b);assert d.max()<=.001 and d.mean()<=.00002,(i,d.max(),d.mean())
  neural.append(dict(view=i,max_abs=float(d.max()),mean_abs=float(d.mean())))
 base_boxes=[decode_boxes(np.fromfile(out/f'decoded_base{i}.f32','<f4')) for i in range(4)]
 allbase=BaseFusion().run(base_boxes[0],base_boxes[1:],.75);allbase=allbase[allbase[:,5]==1];strong=allbase[allbase[:,4]>=.25]
 baseline=np.fromfile(out/'baseline.f32','<f4').reshape(-1,6)
 assert strong.shape==baseline.shape and strong.tobytes()==baseline.tobytes() and len(strong)==m[142]==m[171]
 arm_predictions=np.fromfile(out/'refiner_outputs.f32','<f4').reshape(900,5);assert np.isfinite(arm_predictions).all()
 wanted=np.zeros((900,5),np.float32);refiner=RefinerC();refiner.begin(sensor);count=0
 if dark:
  local=[decode_boxes(np.fromfile(out/f'decoded_zoom{i}.f32','<f4')) for i in range(3)]
  assert [len(v) for v in local]==list(m[183:186]);mapped_arm=[]
  for j,pp in enumerate(local):
   q=[]
   for i,p in enumerate(pp):
    if int(p[5])!=1 or not(p[0]>1 and p[1]>1 and p[2]<399 and p[3]<239):continue
    mapped=map_zoom(np.asarray([p]),XS[j],152);assert len(mapped)==1;b=mapped[0]
    q.append(arm_predictions[j*300+i])
    if eligible(b,strong):
     image,meta=refiner.crop(b);wanted[j*300+i]=refiner.predict(image,meta);count+=1
   mapped_arm.append(np.asarray(q,np.float32).reshape(-1,5))
  chosen=read(STUDY/'selected.json')['chosen']['source'];post=refiner.fuse(strong,local,mapped_arm,chosen);post=post[post[:,4]>=.25]
 else:post=strong.copy()
 refiner.end();diff=np.abs(wanted-arm_predictions);assert diff.max()<=.001 and diff.mean()<=.00002 and m[194]==count
 boxes=np.fromfile(out/'boxes.f32','<f4').reshape(-1,6);assert boxes.shape==post.shape and len(boxes)==m[52]==m[172]
 postdiff=np.abs(boxes-post);assert np.max(postdiff,initial=0)<=.001
 # Verify rasterization independently, using actual board box payload and UI.
 p=subprocess.run([str(APP/'host/render.exe'),str(out/'raw.u32'),str(out/'enhanced.u32'),str(out/'boxes.f32'),str(out/'baseline.f32'),str(out/'ui.u32'),str(out/'expected_frame.bgr')],capture_output=True,text=True,env=env,timeout=30)
 assert p.returncode==0 and 'GUARDS_PASS' in p.stdout and (out/'expected_frame.bgr').read_bytes()==(out/'frame.bgr').read_bytes()
 Image.fromarray(np.fromfile(out/'frame.bgr',np.uint8).reshape(480,800,3)[:,:,::-1]).save(out/'lcd_readback.png')
 result=dict(status='ABI28_ACTUAL_BOARD_PACKET_PASS' if physical else 'SIMULATED_READER_SMOKE_PASS_NOT_BOARD_PROOF',physical_readback=physical,
  kind=kind,route_dark=dark,source_sha256=sha(out/'source800.bgr'),source_immutable=True,all_input_views_byte_exact=True,
  detector_native_comparisons=neural,detector_forward_count=len(neural),refiner_calls=count,refiner_max_abs=float(diff.max()),refiner_mean_abs=float(diff.mean()),
  baseline_post_byte_exact=True,new_post_max_abs=float(np.max(postdiff,initial=0)),frame_byte_exact=True,enhancement_max_abs=int(delta.max()),
  baseline_cars=len(baseline),candidate_cars=len(boxes),pl_calls=m[104],processing_seconds=(m[19]+(m[20]<<32))/m[18],camera_source_bank=m[146],sd_written=False)
 write(out/'verified.json',result);print('BALANCED_BOARD_PACKET_VERIFIED',result,flush=True);return result
