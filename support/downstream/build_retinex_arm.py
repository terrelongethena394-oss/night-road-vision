"""Isolated ABI19 build: custom ARM enhancement + unchanged P16 detector bit."""
from pathlib import Path
import json,shutil,hashlib,subprocess,struct,ctypes as ct,os,re
import numpy as np
from PIL import Image

HERE=Path(__file__).resolve().parent
ROOT=Path('E:/FPGA_Enhance_Work/road_retinex_arm_20261029_r1')
OLD=Path('E:/FPGA_Enhance_Work/road_conv13_p16_runtime_20261028_r1/firmware')
REF=Path('E:/FPGA_Enhance_Work/road_project_retinex_20261029_r3')
VERSION=19
DEFAULT_CAP=48
WRAPPER=HERE/'road_retinex_wrapper.c'
CORE_SOURCE=HERE/'road_retinex_c.c'
CORE_HEADER=HERE/'road_retinex_c.h'
PHOTO_NAMES=None
PHOTO_ROOT=REF/'showcase'
UI_LABEL='RETI VIEW / RAW DET'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def fnv(raw):
 v=2166136261
 for b in raw:v=((v^b)*16777619)&0xffffffff
 return v
def main():
 cproof=read(ROOT/'c_complete.json');assert cproof['source_sha256']==sha(CORE_SOURCE)
 app=ROOT/'firmware';assert not app.exists();app.mkdir();src=app/'source';shutil.copytree(OLD/'source',src)
 for n in ['display.bit','display.xsa','road_conv.bit','ps7_init.tcl','Xilinx.spec']:
  shutil.copy2(OLD/n,app/n)
 (app/'runtime').mkdir();shutil.copy2(OLD/'runtime/weights.f32',app/'runtime/weights.f32')
 shutil.copy2(CORE_SOURCE,src/'road_retinex_c.c');shutil.copy2(CORE_HEADER,src/'road_retinex_c.h')
 shutil.copy2(WRAPPER,src/'road_enhance.c')
 header='#ifndef ROAD_ENHANCE_H\n#define ROAD_ENHANCE_H\n#include <stdint.h>\ntypedef struct {uint32_t mean_in,mean_out,alpha,cap,changed,max_delta;} RoadEnhanceStats;\n/* ABI%d custom Retinex; mode0 raw; default cap%d. See wrapper for cap semantics. */\nint road_enhance(const uint32_t *,uint32_t *,uint32_t,unsigned,unsigned,RoadEnhanceStats *,void (*)(void *),void *);\n#endif\n'%(VERSION,DEFAULT_CAP)
 (src/'road_enhance.h').write_text(header,encoding='ascii')
 (src/'road_enhance_config.h').write_text('#define ROAD_ENHANCE_DEFAULT_CAP %dU\n'%DEFAULT_CAP,encoding='ascii')
 p=src/'road_camera_main.c';s=p.read_text(encoding='utf-8');assert 'm[M_VERSION]=18;' in s
 s=s.replace('m[M_VERSION]=18;',f'm[M_VERSION]={VERSION};').replace('ROAD_CONV13_READY V18',f'ROAD_RETINEX_READY V{VERSION}')
 s=s.replace('ARM adaptive gamma','ARM custom Retinex');p.write_text(s,encoding='ascii')
 p=src/'road_camera_draw.c';s=p.read_text(encoding='utf-8').replace('ENH VIEW / RAW DET',UI_LABEL).replace('ENH INPUT + DET','RETI INPUT + DET').replace('AUTO GAMMA / BRIGHT AREAS PROTECTED','CUSTOM RETINEX / BRIGHT PROTECTED').replace('ENH %u%% / MEAN','RETI %u%% / MEAN');p.write_text(s,encoding='ascii')
 for name in ['road_fp32.c','road_pl.c','road_conv3_pack.c','road_camera_io.c','road_camera_average.c','road_graph.h']:
  assert sha(src/name)==sha(OLD/'source'/name),name
 # Retarget the exact verified compiler configuration; add only one C object.
 old=read(OLD/'arm_complete.json');origin=Path(next(v for cmd in old['commands'] for v in cmd if Path(v).name=='road_fp32.c')).parent.parent
 obj=app/'obj';obj.mkdir();commands=[];logs=[]
 def run(cmd):
  cmd=list(map(str,cmd));commands.append(cmd);p=subprocess.run(cmd,capture_output=True,text=True);logs.append(p.stdout+p.stderr);(app/'build.log').write_text('\n'.join(logs),encoding='utf-8');assert p.returncode==0,p.stderr
 templates=[[v.replace(str(origin),str(app)).replace(origin.as_posix(),app.as_posix()) for v in cmd] for cmd in old['commands'] if Path(cmd[0]).name=='arm-none-eabi-gcc.exe']
 example=next(cmd for cmd in templates if any(Path(v).name=='road_enhance.c' for v in cmd))
 extra=[v.replace(str(src/'road_enhance.c'),str(src/'road_retinex_c.c')).replace((src/'road_enhance.c').as_posix(),(src/'road_retinex_c.c').as_posix()) for v in example]
 extra[extra.index('-o')+1]=str(obj/'road_retinex_c.o')
 for cmd in templates:
  if '-c' not in cmd:
   run(extra);cmd=cmd.copy();cmd.insert(cmd.index('-Wl,--start-group'),str(obj/'road_retinex_c.o'))
  run(cmd)
 elf=app/'road_detail.elf';raw=elf.read_bytes();assert f'ROAD_RETINEX_READY V{VERSION}'.encode() in raw
 phoff=struct.unpack_from('<I',raw,28)[0];ent,num=struct.unpack_from('<HH',raw,42);loads=[]
 for i in range(num):
  typ,off,va,pa,fs,mem,fl,al=struct.unpack_from('<8I',raw,phoff+i*ent)
  if typ==1 and mem:assert 0x100000<=pa<pa+mem<=0x1000000;loads.append([pa,pa+mem])
 regions=list(old['regions']);regions.append(['custom_retinex_workspace',0x19000000,cproof['workspace_bytes']])
 for i,(name,a,n) in enumerate(regions):
  assert a+n<=0x20000000
  for name2,b,l in regions[:i]:assert a+n<=b or b+l<=a,(name,name2)
  for b,e in loads:assert a+n<=b or e<=a
 common=(OLD/'camera_common.tcl').read_text(encoding='ascii').replace('!=18',f'!={VERSION}')
 common=re.sub(r'elf_sha256=[0-9a-f]{64}','elf_sha256='+sha(elf),common)
 (app/'camera_common.tcl').write_text(common,encoding='ascii')
 start=(OLD/'start_default.tcl').read_text(encoding='ascii').replace('==18',f'=={VERSION}')
 marker=' set ready 0\n for {set i 0} {$i<600} {incr i}'
 first=start.index(marker)
 end=start.index(' disconnect',first)
 start=start[:first]+' mwr 0x1380000c 0\n'+start[end:]
 start=start.replace('ROAD_CONV13_LIVE_READY','ROAD_RETINEX_IDLE_READY')
 start=start.replace('mwr 0x1380000c 3','mwr 0x1380000c 0')
 (app/'start_idle.tcl').write_text(start,encoding='ascii')
 host=app/'host';host.mkdir();gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH']
 renderer=[str(gcc),'-O2','-std=c99','-Wall','-Wextra','-Werror','-I'+str(src),str(src/'road_camera_draw.c'),str(src/'road_camera_draw_host.c'),'-lm','-o',str(host/'render.exe')]
 p=subprocess.run(renderer,capture_output=True,text=True,env=env);assert p.returncode==0,p.stderr
 # C-port reference images are used, not a silently substituted Python output.
 cdir=Path(cproof['attempt']);lib=ct.CDLL(str(cdir/'retinex.dll'))
 class Stats(ct.Structure):_fields_=[(n,ct.c_float) for n in ['mean_in','mean_out','noise_proxy','alpha','max_gain']]
 ptr=ct.POINTER(ct.c_uint32);fp=ct.POINTER(ct.c_float);lib.road_retinex_c.argtypes=[ptr,ptr,ct.c_uint,fp,ct.POINTER(Stats),ct.c_void_p,ct.c_void_p]
 cases=[];raw_host=Path('E:/FPGA_Enhance_Work/road_roi_spatial_verifier_20261028/native_detector_full/host.exe')
 photo_inputs=[(Path(name).stem,np.array(Image.open(PHOTO_ROOT/Path(name).stem/'raw.png').convert('RGB'))) for name in (PHOTO_NAMES if PHOTO_NAMES is not None else read(REF/'protocol.json')['showcase'])]
 for i,(name,a) in enumerate(photo_inputs+[('control_black',np.zeros((240,400,3),np.uint8))]):
  folder=app/'runtime/cases'/name;folder.mkdir(parents=True);v=a.astype(np.uint32);v=np.ascontiguousarray(v[:,:,0]|v[:,:,1]<<8|v[:,:,2]<<16).reshape(-1);v.tofile(folder/'input400.u32')
  dest=np.zeros_like(v);workspace=np.empty(17*96000+65536,np.float32);stats=Stats();assert lib.road_retinex_c(v.ctypes.data_as(ptr),dest.ctypes.data_as(ptr),96000,workspace.ctypes.data_as(fp),ct.byref(stats),None,None)==0
  if DEFAULT_CAP!=48:
   aa=np.stack([v&255,v>>8&255,v>>16&255],1);bb=np.stack([dest&255,dest>>8&255,dest>>16&255],1)
   mix=(aa*(48-DEFAULT_CAP)+bb*DEFAULT_CAP+24)//48
   dest=(mix[:,0]|mix[:,1]<<8|mix[:,2]<<16).astype('<u4')
  dest.tofile(folder/'enhanced400.u32');native=folder/'native_raw';native.mkdir()
  p=subprocess.run([str(raw_host),str(app/'runtime/weights.f32'),str(folder/'input400.u32'),str(native)],capture_output=True,text=True,env=env);assert p.returncode==0,p.stdout+p.stderr
  cases.append(dict(name=name,photo=i+1,input_fnv=fnv(v.tobytes()),input_sha256=sha(folder/'input400.u32'),enhanced_sha256=sha(folder/'enhanced400.u32'),host_boxes_sha256=sha(native/'boxes400.f32'),host_decode_sha256=sha(native/'decoded.f32')))
 write(app/'cases.json',cases)
 proof=dict(status=f'ABI{VERSION}_RETINEX_ARM_COMPILED_NOT_BOARD_TESTED',version=VERSION,default_cap=DEFAULT_CAP,default_pipe=2,default_pl_mode=2,roi_default=0,commands=commands,regions=regions,elf_loads=loads,elf_sha256=sha(elf),bit_sha256=sha(app/'display.bit'),weights_sha256=sha(app/'runtime/weights.f32'),detector_source_unchanged=True,enhancer_workspace_bytes=cproof['workspace_bytes'],source_sha256={str(p.relative_to(src)):sha(p) for p in src.rglob('*') if p.is_file()},cases=cases,hardware_access=False,sd_written=False)
 write(app/'arm_complete.json',proof)
 checks={str(p.relative_to(app)):sha(p) for p in app.rglob('*') if p.is_file() and 'obj' not in p.relative_to(app).parts and p.suffix not in ['.log','.map','.su']}
 write(app/'runtime_checksums.json',checks);print('RETINEX_ARM_APP_READY',sha(elf),cases,flush=True)
if __name__=='__main__':main()
