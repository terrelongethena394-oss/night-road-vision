"""Strict paired-model board readback; exact same captured pixels for8 forwards."""
import ctypes as ct,os,struct,subprocess
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity
from car_pair_common import *
import _capture_io as io
from _capture_io import words,rgb,fnv,run,start

def capture(out,kind=4,source=None,photo=1,check_native=True):
 io.validate=validate
 return io.capture(out,kind,source,photo,check_native)

def validate(out,kind,check_native=True):
 m=struct.unpack('<176I',(out/'mail.bin').read_bytes());proof=read(APP/'arm_complete.json')
 assert m[0]==0x524f4144 and m[1]==26 and m[2]==3 and m[57]==1 and m[155]==kind and m[156]==m[158]==1
 assert m[93]==m[99]==2 and m[72]==m[132]==2 and m[104]==408 and m[169]==m[170]==204
 assert m[6]==m[35]==m[41]==m[74]==0 and m[30]==0x7084 and m[40]==0x5640
 assert m[161]==proof['weight_fnv']['stable'] and m[162]==m[17]==proof['weight_fnv']['candidate'] and m[8]==m[160]==0x1B000000 and m[164]==0x1B800000 and m[163]==2
 assert m[171]==m[142] and m[172]==m[52]
 assert m[144]==0x1A300000 and m[149:152]==(1152000,800,480) and m[159]==0x46524f5a
 source=(out/'source800.bgr').read_bytes();assert fnv(source)==m[145]==m[148]
 if kind==4:assert source==(out/'camera_bank.bgr').read_bytes() and m[56]==0
 else:assert m[56]==1
 sensor=np.frombuffer(source,np.uint8).reshape(480,800,3)[:,:,::-1].copy();full=((sensor.astype(np.uint16).reshape(240,2,400,2,3).sum(axis=(1,3))+2)//4).astype(np.uint8);views=[full]+[sensor[120:360,x:x+400] for x in [0,200,400]]
 for i,v in enumerate(views):assert words(v).tobytes()==(out/('raw.u32' if i==0 else f'tile{i-1}.u32')).read_bytes()
 assert fnv(words(full).tobytes())==m[16]
 for i in range(3):assert fnv(words(views[i+1]).tobytes())==m[133+i]
 cp=read(BASE/'road_retinex_noiseguard_arm_20261029_r1/c_complete.json');lib=ct.CDLL(str(Path(cp['attempt'])/'retinex.dll'))
 class Stats(ct.Structure):_fields_=[(n,ct.c_float) for n in ['mean_in','mean_out','noise_proxy','alpha','max_gain']]
 up=ct.POINTER(ct.c_uint32);fp=ct.POINTER(ct.c_float);lib.road_retinex_c.argtypes=[up,up,ct.c_uint,fp,ct.POINTER(Stats),ct.c_void_p,ct.c_void_p]
 a=words(full).reshape(-1);b=np.empty_like(a);work=np.empty(17*96000+65536,np.float32);stats=Stats();assert lib.road_retinex_c(a.ctypes.data_as(up),b.ctypes.data_as(up),96000,work.ctypes.data_as(fp),ct.byref(stats),None,None)==0
 expected=np.stack([b&255,b>>8&255,b>>16&255],1).astype(np.uint8).reshape(240,400,3);actual=rgb(out/'enhanced.u32');diff=np.abs(expected.astype(np.int16)-actual.astype(np.int16));ssim=float(structural_similarity(expected,actual,channel_axis=2,data_range=255));assert diff.max()<=1 and diff.mean()<=.01 and ssim>=.99999
 env=dict(os.environ);env['PATH']='E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin;'+env['PATH'];neural=[]
 for model,weight,prefix in [('stable','weights.f32','stable_decoded'),('candidate','new_weights.f32','decoded')]:
  for i in range(4) if check_native else []:
   folder=out/'native'/model/str(i);folder.mkdir(parents=True);ip=out/('raw.u32' if i==0 else f'tile{i-1}.u32')
   p=subprocess.run([str(APP/'host/road_ap.exe'),str(APP/'runtime'/weight),str(ip),str(folder)],capture_output=True,text=True,env=env);assert p.returncode==0 and 'ROAD_FP32_HOST_DONE' in p.stdout
   ar=np.fromfile(out/(prefix+str(i)+'.f32'),'<f4');pc=np.fromfile(folder/'decoded.f32','<f4');assert ar.shape==pc.shape==(56700,) and np.isfinite(ar).all();delta=np.abs(ar-pc);assert delta.max()<=.001 and delta.mean()<=.00002,(model,i,float(delta.max()),float(delta.mean()));neural.append(dict(model=model,view=i,max_abs=float(delta.max()),mean_abs=float(delta.mean())))
 post_and_frame(out)
 Image.fromarray(sensor).save(out/'source.png');Image.fromarray(np.fromfile(out/'frame.bgr',np.uint8).reshape(480,800,3)[:,:,::-1]).save(out/'lcd_readback.png')
 result=dict(status='CAR_PAIR_ALL_PIXELS_8_NEURAL_FUSION_AND_FRAME_PASS' if check_native else 'CAR_PAIR_PIXELS_FUSION_AND_FRAME_PASS',capture_id=m[147],source_kind=kind,source_bank=m[146],same_frozen_source_unchanged=True,camera_bank_byte_exact=kind==4,all4_input_views_byte_exact=True,stable_cars=m[142],candidate_cars=m[52],both_models_pl_calls=[m[169],m[170]],pl_calls=m[104],neural_comparisons=neural,native_neural_checked=check_native,source_sha256=sha(out/'source800.bgr'),enhancement_max_abs=int(diff.max()),enhancement_mean_abs=float(diff.mean()),enhancement_ssim=ssim,car_only_post_byte_exact=True,LCD_frame_byte_exact=True,total_seconds=(m[19]+(m[20]<<32))/m[18],stable_model_seconds=(m[165]+(m[166]<<32))/m[18],candidate_model_seconds=(m[167]+(m[168]<<32))/m[18],sd_written=False)
 write(out/'verified.json',result);print('CAR_PAIR_PACKET_PASS',result,flush=True);return result

def post_and_frame(out):
 class Box(ct.Structure):_fields_=[(n,ct.c_float) for n in ['x1','y1','x2','y2','score']]+[('cls',ct.c_int),('order',ct.c_int)]
 lib=ct.CDLL(str(APP/'host/post.dll'));lib.road_nms.argtypes=[ct.POINTER(ct.c_float),ct.POINTER(Box),ct.POINTER(Box),ct.c_int,ct.c_float,ct.c_float];lib.road_nms.restype=ct.c_int;lib.road_boxes_to400.argtypes=[ct.POINTER(Box),ct.c_int]
 post=ct.CDLL(str(APP/'host/car_post.dll'));post.road_car_multiview.argtypes=[ct.POINTER(Box),ct.c_int,ct.POINTER(Box),ct.POINTER(ct.c_int),ct.POINTER(Box),ct.c_int];post.road_car_multiview.restype=ct.c_int
 for prefix,file in [('stable_decoded','baseline.f32'),('decoded','boxes.f32')]:
  bufs=[];counts=[]
  for i in range(4):
   dec=np.fromfile(out/(prefix+str(i)+'.f32'),'<f4');cand=(Box*6300)();keep=(Box*300)();n=lib.road_nms(dec.ctypes.data_as(ct.POINTER(ct.c_float)),cand,keep,300,.001,.6);assert 0<=n<=300;lib.road_boxes_to400(keep,n);bufs.append(keep);counts.append(n)
  tiles=(Box*900)();result=(Box*302)();result[0].order=result[301].order=0x12345678
  for t in range(3):
   for i in range(counts[t+1]):tiles[t*300+i]=bufs[t+1][i]
  ptr=ct.cast(ct.byref(result,ct.sizeof(Box)),ct.POINTER(Box));n=post.road_car_multiview(bufs[0],counts[0],tiles,(ct.c_int*3)(*counts[1:]),ptr,300);assert 0<=n<=300 and result[0].order==result[301].order==0x12345678
  a=np.array([[result[i+1].x1,result[i+1].y1,result[i+1].x2,result[i+1].y2,result[i+1].score,result[i+1].cls] for i in range(n)],'<f4').reshape(-1,6);assert np.all(a[:,5]==1) and a.tobytes()==(out/file).read_bytes()
 p=subprocess.run([str(APP/'host/render.exe'),str(out/'raw.u32'),str(out/'enhanced.u32'),str(out/'boxes.f32'),str(out/'baseline.f32'),str(out/'ui.u32'),str(out/'expected.bgr')],capture_output=True,text=True,timeout=30);assert p.returncode==0 and 'GUARDS_PASS' in p.stdout and (out/'expected.bgr').read_bytes()==(out/'frame.bgr').read_bytes()
