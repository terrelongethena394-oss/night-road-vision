"""Compile the real ARM-compatible C filter, prove Python/C outputs before board use."""
from pathlib import Path
import os,shutil,struct,subprocess
import cv2,numpy as np
from road_roi_guard_common import *
HERE=Path(__file__).resolve().parent

def main():
 selected=read(ROOT/'selected.json');assert selected['qualified'];policy=selected['chosen']['policy'];out=ROOT/'native';out.mkdir(exist_ok=False);src=out/'source';src.mkdir()
 for n in ['road_roi_guard.h','road_roi_guard.c','road_roi_guard_host.c']:shutil.copy2(HERE/n,src/n)
 for n in ['road_fp32.h','road_graph.h']:shutil.copy2(BASE.parent/'road_enhance_20261027/firmware/source'/n,src/n)
 gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=os.environ.copy();env['PATH']=str(gcc.parent)+';'+env['PATH'];exe=out/'guard.exe'
 cmd=list(map(str,[gcc,'-O3','-std=c99','-ffp-contract=off','-fno-fast-math','-Wall','-Wextra','-Werror','-I'+str(src),src/'road_roi_guard.c',src/'road_roi_guard_host.c','-lm','-o',exe]));r=subprocess.run(cmd,capture_output=True,text=True,env=env);(out/'build.log').write_text(r.stdout+r.stderr,encoding='utf-8');assert r.returncode==0,r.stderr
 pv=[policy['border'],*policy['person_aspect'],*policy['weights'],policy['dedup_iou'],policy['dedup_containment']];np.asarray(pv,'<f4').tofile(out/'policy.f32');assert len(pv)==9
 def invoke(a,z,mode='fuse'):
  a=np.asarray(a,'<f4').reshape(-1,6);z=np.asarray(z,'<f4').reshape(-1,6);(out/'input.bin').write_bytes(struct.pack('<II',len(a),len(z))+a.tobytes()+z.tobytes());r=subprocess.run([str(exe),str(out/'policy.f32'),str(out/'input.bin'),str(out/'answer.f32'),mode],capture_output=True,text=True,env=env);assert r.returncode==0 and 'ROI_NATIVE_FUSION_DONE' in r.stdout,(r.returncode,r.stderr);return np.fromfile(out/'answer.f32','<f4').reshape(-1,6)
 def compare(a,b,name):
  a=np.asarray(a,np.float32).reshape(-1,6);b=np.asarray(b,np.float32).reshape(-1,6);assert a.shape==b.shape,(name,a.shape,b.shape)
  if not len(a):return 0.
  a=a[np.lexsort(a[:,::-1].T)];b=b[np.lexsort(b[:,::-1].T)];d=abs(a-b);assert np.array_equal(a[:,5],b[:,5]) and d[:,:4].max()<=1e-4 and d[:,4].max()<=1e-7,(name,float(d.max()));return float(d.max())
 records=[]
 full=read(OLD/'full_predictions.json');roi={r['name']:r['detections'] for r in read(OLD/'center_only_diagnostic_predictions.json')}
 for i,r in enumerate(full):records.append(dict(name=r['name'],max_abs=compare(invoke(r['detections'],roi[r['name']]),fuse(r['detections'],roi[r['name']],policy),r['name'])))
 print('ROI_NATIVE_OLD320_FUSION_PASS',flush=True)
 rng=np.random.default_rng(2026102853);z=rng.uniform(2,120,(200,6)).astype(np.float32);z[:,2]=z[:,0]+rng.uniform(1,240,200).astype(np.float32);z[:,3]=z[:,1]+rng.uniform(1,100,200).astype(np.float32);z[:,4]=rng.uniform(0,1,200);z[:,5]=rng.integers(0,4,200);z=np.concatenate([z,np.array([[1,10,30,40,.5,0],[10,1,30,40,.5,0],[10,10,399,40,.5,0],[10,10,30,239,.5,0]],np.float32)])
 good=z[(z[:,0]>1)&(z[:,1]>1)&(z[:,2]<399)&(z[:,3]<239)].copy();good[:,[0,2]]=good[:,[0,2]]*.5+100;good[:,[1,3]]=good[:,[1,3]]*.5+60;compare(invoke([],z,'map'),good,'mapping_edges_random')
 crops=[];meta=read(ROOT/'fresh_selection.json')
 for period in ['night','dawn/dusk','daytime']:
  for r in [r for r in meta if r['timeofday']==period][:2]:
   img=cv2.imread(str(ROOT/'fresh/images'/r['name']))[:,:,::-1].copy();sensor=cv2.resize(img,(800,480),interpolation=cv2.INTER_LINEAR);sensor[:,:,0]&=248;sensor[:,:,1]&=252;sensor[:,:,2]&=248;a=sensor[120:360,200:600].astype(np.uint32);expected=(a[:,:,0]|(a[:,:,1]<<8)|(a[:,:,2]<<16)).astype('<u4').tobytes();(out/'source.bgr').write_bytes(sensor[:,:,::-1].tobytes());p=subprocess.run([str(exe),'crop',str(out/'source.bgr'),str(out/'crop.u32')],capture_output=True,text=True,env=env);assert p.returncode==0 and (out/'crop.u32').read_bytes()==expected;crops.append(dict(name=r['name'],sha256=sha(out/'crop.u32')))
 write(out/'complete.json',dict(status='ARM_COMPATIBLE_C_OLD320_FUSION_AND_CAMERA_CROP_EXACT',policy=policy,compiler=cmd,old320=records,mapping_random204_and_edges_passed=True,real_crop6_byte_exact=crops,source_sha256={p.name:sha(p) for p in src.iterdir()},hardware_access=False,sd_written=False));print('ROI_NATIVE_GEOMETRY_AND_CROP_ALL_PASS',flush=True)
if __name__=='__main__':main()
