"""Independent NumPy mapping, guards and source-immutability acceptance."""
from pathlib import Path
import ctypes as ct,json,hashlib,os,shutil,subprocess
import numpy as np
from PIL import Image
HERE=Path(__file__).resolve().parent
ROOT=Path('E:/FPGA_Enhance_Work/road_camera_snapshot_20261030_r1')
OLD=Path('E:/FPGA_Enhance_Work/road_accuracy_20261030_r1/firmware')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2),encoding='utf-8')
def words(rgb):
 a=rgb.astype(np.uint32);return (a[:,:,0]|a[:,:,1]<<8|a[:,:,2]<<16).reshape(-1)
def main():
 assert not ROOT.exists();ROOT.mkdir();out=ROOT/'pixel_proof';out.mkdir()
 for n in ['road_capture_views.c','road_capture_views.h']:shutil.copy2(HERE/n,out/n)
 write(out/'protocol.json',dict(status='FROZEN_BEFORE_MAPPING_OUTPUTS',all_bytes_exact=True,source_immutable=True,guards_required=True,full='NumPy 2x2 rounded integer mean',tiles='Direct slices [120:360,x:x+400] for x0/200/400',hardware_access=False,sd_written=False))
 gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH']
 dll=out/'views.dll';cmd=[str(gcc),'-O3','-std=c99','-Wall','-Wextra','-Werror','-shared','-static-libgcc','-Wl,--export-all-symbols',str(out/'road_capture_views.c'),'-o',str(dll)]
 p=subprocess.run(cmd,capture_output=True,text=True,env=env);assert p.returncode==0,p.stderr
 lib=ct.CDLL(str(dll));fn=lib.road_capture_views;fn.argtypes=[ct.POINTER(ct.c_uint8)]+[ct.POINTER(ct.c_uint32)]*4
 inputs=[]
 for p in sorted((OLD/'runtime/cases').glob('*/sensor800.png')):inputs.append((p.parent.name,np.array(Image.open(p).convert('RGB'))))
 yy,xx=np.mgrid[:480,:800];inputs.append(('coordinates',np.stack([xx%256,yy%256,(xx+yy)%256],2).astype(np.uint8)))
 inputs.append(('random',np.random.default_rng(2026103009).integers(0,256,(480,800,3),np.uint8)))
 for name,rgb in [('black',[0,0,0]),('white',[255,255,255]),('red',[255,0,0]),('green',[0,255,0]),('blue',[0,0,255])]:inputs.append((name,np.tile(np.array(rgb,np.uint8),(480,800,1))))
 records=[]
 for name,rgb in inputs:
  bgr=np.ascontiguousarray(rgb[:,:,::-1]);src=np.full(1152000+64,0xA5,np.uint8);src[32:-32]=bgr.reshape(-1);original=src.copy()
  dest=[np.full(96000+32,0x5AA5A55A,np.uint32) for _ in range(4)]
  args=[src[32:-32].ctypes.data_as(ct.POINTER(ct.c_uint8))]+[v[16:-16].ctypes.data_as(ct.POINTER(ct.c_uint32)) for v in dest]
  assert fn(*args)==0 and np.array_equal(src,original)
  full=((rgb.astype(np.uint16).reshape(240,2,400,2,3).sum(axis=(1,3))+2)//4).astype(np.uint8)
  refs=[full]+[rgb[120:360,x:x+400] for x in [0,200,400]]
  for actual,ref in zip(dest,refs):
   assert (actual[:16]==0x5AA5A55A).all() and (actual[-16:]==0x5AA5A55A).all()
   assert actual[16:-16].tobytes()==words(ref).tobytes(),name
  case=OLD/'runtime/cases'/name
  if (case/'input400.u32').exists():assert dest[0][16:-16].tobytes()==(case/'input400.u32').read_bytes()
  records.append(dict(name=name,all4_byte_exact=True,guards_pass=True,source_immutable=True))
 write(ROOT/'pixel_complete.json',dict(status='ALL_CAPTURE_VIEW_BYTES_AND_GUARDS_PASS',cases=records,compiler=cmd,source_sha256=sha(HERE/'road_capture_views.c'),hardware_access=False,sd_written=False))
 print('CAMERA_VIEW_MAPPING_COMPLETE',len(records),flush=True)
if __name__=='__main__':main()
