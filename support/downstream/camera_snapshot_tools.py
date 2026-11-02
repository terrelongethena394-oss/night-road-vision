"""Local one-shot control and independent snapshot readback validation."""
from pathlib import Path
import ctypes as ct,hashlib,json,os,struct,subprocess
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity
ROOT=Path('E:/FPGA_Enhance_Work/road_camera_snapshot_20261030_r1')
APP=ROOT/'firmware'
OLD=Path('E:/FPGA_Enhance_Work/road_accuracy_20261030_r1')
BASE=ROOT.parent
XSCT='E:/Xilinx/Vitis/2020.2/bin/xsct.bat'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def fnv(data):
 v=2166136261
 for b in data:v=((v^b)*16777619)&0xffffffff
 return v
def words(rgb):
 a=rgb.astype(np.uint32);return (a[:,:,0]|a[:,:,1]<<8|a[:,:,2]<<16).astype('<u4')
def rgb(p):
 a=np.fromfile(p,'<u4').reshape(240,400);return np.stack([a&255,a>>8&255,a>>16&255],2).astype(np.uint8)
def run(script,log,marker,timeout=300):
 with Path(log).open('w',encoding='utf-8') as f:p=subprocess.run([XSCT,str(script)],stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
 text=Path(log).read_text(encoding='utf-8');assert p.returncode==0 and marker in text,text[-4000:]
def start(out):run(APP/'start_idle.tcl',out/'start.log','ROAD_RETINEX_IDLE_READY')

def capture(out,kind=4,source=None,photo=1,check_native=True):
 out.mkdir(parents=True);d=out.as_posix();a=APP.as_posix()
 upload=''
 if kind==5:
  source=Path(source);assert source.stat().st_size==1152000
  upload=f'dow -data {source.as_posix()} 0x1A300000\n catch {{con}}\n mwr 0x13800274 {fnv(source.read_bytes())}'
 assert kind in [4,5]
 script=out/'request.tcl';script.write_text(f'''source {a}/camera_common.tcl
connect -url tcp:127.0.0.1:3121
if {{[catch {{
 targets -set -filter {{name =~ "ARM*#0"}} -timeout 10
 loadhw -hw $root/display.xsa
 rc_check
 if {{[word 0x13800008]==3 && [word 0x13800270]!=1}} {{error "Paused inside incomplete inference"}}
 mwr 0x1380000c 0
 set idle 0
 for {{set i 0}} {{$i<100}} {{incr i}} {{after 100;rc_check;if {{[word 0x13800008] in {{1 5}}}} {{set idle 1;break}}}}
 if {{!$idle}} {{error "No safe idle boundary"}}
 {upload}
 mwr 0x1380006c 0
 mwr 0x13800220 0
 mwr 0x13800224 0
 mwr 0x13800228 0
 mwr 0x138000b8 {photo}
 mwr 0x13800070 0
 mwr 0x13800120 2
 mwr 0x13800140 2
 mwr 0x13800144 48
 mwr 0x13800178 2
 set wanted [expr {{[word 0x13800010]+1}}]
 mwr 0x1380000c {kind}
 set ready 0
 for {{set i 0}} {{$i<1800}} {{incr i}} {{after 100;rc_check;if {{[word 0x13800008]==5 && [word 0x13800010]==$wanted && [word 0x13800270]==1}} {{set ready 1;break}}}}
 if {{!$ready}} {{error "Snapshot inference timeout"}}
 mwr 0x1380000c 1
 set paused 0
 for {{set i 0}} {{$i<100}} {{incr i}} {{after 100;rc_check;if {{[word 0x13800008]==3 && [word 0x138000e4]==1}} {{set paused 1;break}}}}
 if {{!$paused}} {{error "Snapshot pause timeout"}}
 mrd -bin -file {d}/mail.bin 0x13800000 160
 mrd -bin -file {d}/ui.u32 0x16500000 17
 mrd -bin -file {d}/source800.bgr 0x1A300000 288000
 if {{{kind}==4}} {{
  set bank [word 0x13800248]
  if {{$bank>1}} {{error "Invalid source bank"}}
  mrd -bin -file {d}/camera_bank.bgr [expr {{0x06000000+$bank*1152000}}] 288000
 }}
 mrd -bin -file {d}/raw.u32 0x16700000 96000
 mrd -bin -file {d}/enhanced.u32 0x16100000 96000
 mrd -bin -file {d}/decoded0.f32 0x17100000 56700
 for {{set j 0}} {{$j<3}} {{incr j}} {{
  mrd -bin -file {d}/tile$j.u32 [expr {{0x1A000000+$j*0x60000}}] 96000
  mrd -bin -file {d}/decoded[expr {{$j+1}}].f32 [expr {{0x1A120000+$j*0x40000}}] 56700
 }}
 set n [word 0x138000d0]
 set bn [word 0x13800238]
 if {{$n>300 || $bn>300}} {{error "Invalid box count"}}
 if {{$n>0}} {{mrd -bin -file {d}/boxes.f32 0x16200000 [expr {{$n*6}}]}} else {{close [open {d}/boxes.f32 w]}}
 if {{$bn>0}} {{mrd -bin -file {d}/baseline.f32 0x1A200000 [expr {{$bn*6}}]}} else {{close [open {d}/baseline.f32 w]}}
 set frame [word 0x13800080]
 if {{$frame!=0x02000000 && $frame!=0x02119400}} {{error "Invalid display frame"}}
 mrd -bin -file {d}/frame.bgr $frame 288000
 mrd -bin -file {d}/vdma.bin 0x43000000 16
 disconnect
 puts "CAMERA_SNAPSHOT_PACKET_READY"
}} why opts]}} {{puts stderr "CAMERA_SNAPSHOT_FAILED $why";catch {{disconnect}};exit 1}}
exit 0
''',encoding='ascii')
 run(script,out/'request.log','CAMERA_SNAPSHOT_PACKET_READY')
 return validate(out,kind,check_native)

def validate(out,kind,check_native=True):
 m=struct.unpack('<160I',(out/'mail.bin').read_bytes())
 assert m[0]==0x524f4144 and m[1]==24 and m[2]==3 and m[57]==1 and m[155]==kind and m[156]==m[158]==1
 assert m[93]==m[99]==2 and m[72]==m[132]==2 and m[104]==204
 assert m[6]==m[35]==m[41]==m[74]==0 and m[17]==1483844061 and m[30]==0x7084 and m[40]==0x5640
 assert m[144]==0x1A300000 and m[149:152]==(1152000,800,480) and m[159]==0x46524f5a
 rawsource=(out/'source800.bgr').read_bytes();assert fnv(rawsource)==m[145]==m[148]
 if kind==4:assert rawsource==(out/'camera_bank.bgr').read_bytes() and m[56]==0
 else:assert m[56]==1
 sensor=np.frombuffer(rawsource,np.uint8).reshape(480,800,3)[:,:,::-1].copy()
 full=((sensor.astype(np.uint16).reshape(240,2,400,2,3).sum(axis=(1,3))+2)//4).astype(np.uint8)
 views=[full]+[sensor[120:360,x:x+400] for x in [0,200,400]]
 for i,v in enumerate(views):assert words(v).tobytes()==(out/('raw.u32' if i==0 else 'tile'+str(i-1)+'.u32')).read_bytes()
 assert fnv(words(full).tobytes())==m[16]
 for i in range(3):assert fnv(words(views[i+1]).tobytes())==m[133+i]
 # Existing enhancement port uses the predeclared max1LSB / MAE.01 / SSIM.99999 gates.
 cproof=read(BASE/'road_retinex_noiseguard_arm_20261029_r1/c_complete.json');enh=ct.CDLL(str(Path(cproof['attempt'])/'retinex.dll'))
 class Stats(ct.Structure):_fields_=[(n,ct.c_float) for n in ['mean_in','mean_out','noise_proxy','alpha','max_gain']]
 up=ct.POINTER(ct.c_uint32);fp=ct.POINTER(ct.c_float);enh.road_retinex_c.argtypes=[up,up,ct.c_uint,fp,ct.POINTER(Stats),ct.c_void_p,ct.c_void_p]
 a=words(full).reshape(-1);b=np.empty_like(a);work=np.empty(17*96000+65536,np.float32);stats=Stats()
 assert enh.road_retinex_c(a.ctypes.data_as(up),b.ctypes.data_as(up),96000,work.ctypes.data_as(fp),ct.byref(stats),None,None)==0
 expected=np.stack([b&255,b>>8&255,b>>16&255],1).astype(np.uint8).reshape(240,400,3);actual=rgb(out/'enhanced.u32');diff=np.abs(expected.astype(np.int16)-actual.astype(np.int16));ssim=float(structural_similarity(expected,actual,channel_axis=2,data_range=255))
 assert diff.max()<=1 and diff.mean()<=.01 and ssim>=.99999
 # Independent x86 FP32 forward comparison; established CPU/ARM difference is
 # around1e-4 in coordinates. Freeze max.001/mean.00002 before camera results.
 exe=BASE/'road_local_enhance_20261029_r2/host/road_ap.exe';env=dict(os.environ);env['PATH']='E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin;'+env['PATH'];native=[]
 for i in range(4) if check_native else []:
  folder=out/'native'/str(i);folder.mkdir(parents=True);p=out/('raw.u32' if i==0 else 'tile'+str(i-1)+'.u32')
  r=subprocess.run([str(exe),str(APP/'runtime/weights.f32'),str(p),str(folder)],capture_output=True,text=True,env=env);assert r.returncode==0 and 'ROAD_FP32_HOST_DONE' in r.stdout
  ar=np.fromfile(out/('decoded'+str(i)+'.f32'),'<f4');pc=np.fromfile(folder/'decoded.f32','<f4');dd=np.abs(ar-pc);assert np.isfinite(ar).all() and dd.max()<=.001 and dd.mean()<=.00002,(i,dd.max(),dd.mean())
  native.append(dict(view=i,max_abs=float(dd.max()),mean_abs=float(dd.mean())))
 post_and_frame(out)
 Image.fromarray(sensor).save(out/'CAMERA_SOURCE.png' if kind==4 else out/'INJECTED_SOURCE.png')
 Image.fromarray(np.fromfile(out/'frame.bgr',np.uint8).reshape(480,800,3)[:,:,::-1]).save(out/'lcd_readback.png')
 result=dict(status='SNAPSHOT_PACKET_PIXEL_NEURAL_FUSION_AND_FRAME_PASS' if check_native else 'SNAPSHOT_PACKET_PIXEL_FUSION_AND_FRAME_PASS',kind=kind,capture_id=m[147],source_bank=m[146],source_sha256=sha(out/'source800.bgr'),source_fnv=m[145],actual_camera_bank_byte_exact=kind==4,all4_input_views_byte_exact=True,frozen_source_unchanged=True,enhancement_max_abs=int(diff.max()),enhancement_mean_abs=float(diff.mean()),native_neural_check_performed=check_native,native_fp32_comparisons=native,postprocessing_byte_exact=True,frame_byte_exact=True,pl_calls=204,baseline_boxes=m[142],new_boxes=m[52],processing_seconds=(m[19]+(m[20]<<32))/m[18],capture_and_view_prep_seconds=(m[153]+(m[154]<<32))/m[18],sd_written=False)
 write(out/'verified.json',result);print('CAMERA_SNAPSHOT_PACKET_PASS',result,flush=True);return result

def post_and_frame(out):
 class Box(ct.Structure):_fields_=[(k,ct.c_float) for k in ['x1','y1','x2','y2','score']]+[('cls',ct.c_int),('order',ct.c_int)]
 post=ct.CDLL(str(OLD/'firmware/host/post.dll'));fuse=ct.CDLL(str(OLD/'native/fusion.dll'))
 post.road_nms.argtypes=[ct.POINTER(ct.c_float),ct.POINTER(Box),ct.POINTER(Box),ct.c_int,ct.c_float,ct.c_float];post.road_nms.restype=ct.c_int;post.road_boxes_to400.argtypes=[ct.POINTER(Box),ct.c_int]
 fuse.road_vehicle_multiview.argtypes=[ct.POINTER(Box),ct.c_int,ct.POINTER(Box),ct.POINTER(ct.c_int),ct.c_float,ct.POINTER(Box),ct.c_int];fuse.road_vehicle_multiview.restype=ct.c_int
 bufs=[];counts=[]
 for i in range(4):
  dec=np.fromfile(out/('decoded'+str(i)+'.f32'),'<f4');cand=(Box*6300)();keep=(Box*300)();n=post.road_nms(dec.ctypes.data_as(ct.POINTER(ct.c_float)),cand,keep,300,.001,.6);assert 0<=n<=300;post.road_boxes_to400(keep,n);bufs.append(keep);counts.append(n)
 tiles=(Box*900)()
 for i in range(3):
  for j in range(counts[i+1]):tiles[i*300+j]=bufs[i+1][j]
 result=(Box*300)();n=fuse.road_vehicle_multiview(bufs[0],counts[0],tiles,(ct.c_int*3)(*counts[1:]),.75,result,300);assert 0<=n<=300
 def array(buf,n):
  z=np.array([[buf[i].x1,buf[i].y1,buf[i].x2,buf[i].y2,buf[i].score,buf[i].cls] for i in range(n)],'<f4').reshape(-1,6);return z[z[:,4]>=.25]
 assert array(result,n).tobytes()==(out/'boxes.f32').read_bytes()
 assert array(bufs[0],counts[0]).tobytes()==(out/'baseline.f32').read_bytes()
 p=subprocess.run([str(APP/'host/render.exe'),str(out/'raw.u32'),str(out/'enhanced.u32'),str(out/'boxes.f32'),str(out/'baseline.f32'),str(out/'ui.u32'),str(out/'expected.bgr')],capture_output=True,text=True,timeout=30)
 assert p.returncode==0 and 'GUARDS_PASS' in p.stdout and (out/'expected.bgr').read_bytes()==(out/'frame.bgr').read_bytes()
