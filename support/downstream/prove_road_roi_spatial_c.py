"""Export13k weights, prove C logits/probabilities and actual sensor crop bytes."""
from pathlib import Path
import os,shutil,struct,subprocess
import cv2,numpy as np
from road_roi_spatial_common import *
HERE=Path(__file__).resolve().parent

def main():
 selected=read(ROOT/'selected.json');assert selected['qualified'];chosen=selected['chosen'];assert sha(chosen['checkpoint'])==chosen['sha256'];out=ROOT/'native_verifier';out.mkdir(exist_ok=False);src=out/'source';src.mkdir()
 for n in ['road_person_verifier.h','road_person_verifier.c','road_person_verifier_host.c']:shutil.copy2(HERE/n,src/n)
 for n in ['road_fp32.h','road_graph.h']:shutil.copy2(BASE.parent/'road_enhance_20261027/firmware/source'/n,src/n)
 import torch
 torch.set_num_threads(3);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
 model=make_model().cuda().eval();state=torch.load(chosen['checkpoint'],map_location='cpu',weights_only=False)['state_dict'];model.load_state_dict(state);weights=np.concatenate([state[str(i)+'.'+k].numpy().ravel() for i in [0,2,4,7,9] for k in ['weight','bias']]).astype('<f4');assert len(weights)==12993;weights.tofile(out/'weights.f32')
 gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=os.environ.copy();env['PATH']=str(gcc.parent)+';'+env['PATH'];exe=out/'person.exe';cmd=list(map(str,[gcc,'-O3','-std=c99','-ffp-contract=off','-fno-fast-math','-Wall','-Wextra','-Werror','-I'+str(src),src/'road_person_verifier.c',src/'road_person_verifier_host.c','-lm','-o',exe]));r=subprocess.run(cmd,capture_output=True,text=True,env=env);(out/'build.log').write_text(r.stdout+r.stderr,encoding='utf-8');assert r.returncode==0,r.stderr
 p=read(ROOT/'prepared.json');assert sha(ROOT/'patches.u8')==p['patches_sha256'];patches=np.memmap(ROOT/'patches.u8',np.uint8,mode='r',shape=tuple(p['shape']));n=len(patches);gold=[]
 with torch.inference_mode():
  for at in range(0,n,256):
   x=torch.from_numpy(np.ascontiguousarray(np.asarray(patches[at:at+256]).transpose(0,3,1,2))).cuda().float()/255;gold.extend(model(x).sigmoid().flatten().cpu().tolist())
 (out/'patches.bin').write_bytes(struct.pack('<I',n)+(ROOT/'patches.u8').read_bytes());r=subprocess.run([str(exe),str(out/'weights.f32'),str(out/'patches.bin'),str(out/'probabilities.f32')],capture_output=True,text=True,env=env);(out/'run.log').write_text(r.stdout+r.stderr,encoding='utf-8');assert r.returncode==0 and 'PERSON_VERIFIER_NATIVE_DONE' in r.stdout
 a=np.fromfile(out/'probabilities.f32','<f4');b=np.asarray(gold,np.float32);assert a.shape==b.shape and np.isfinite(a).all();err=float(abs(a-b).max());assert err<=1e-5,err
 meta=read(ROOT/'patches.json')[p['train_patches']:];roi={r['name']:r['detections'] for r in read(OLD/'center_only_diagnostic_predictions.json')};crops=[]
 selected_rows=[]
 for period in ['night','dawn/dusk','daytime']:
  selected_rows.extend([r for r in meta if r['timeofday']==period][:2])
 for r in selected_rows:
  image=cv2.imread(str(BASE/'dataset/images/val'/r['name']))[:,:,::-1].copy();sensor=cv2.resize(image,(800,480),interpolation=cv2.INTER_LINEAR);sensor[:,:,0]&=248;sensor[:,:,1]&=252;sensor[:,:,2]&=248;box=np.asarray(roi[r['name']][r['roi_index']],np.float32);(out/'source.bgr').write_bytes(sensor[:,:,::-1].tobytes());box.astype('<f4').tofile(out/'box.f32');z=subprocess.run([str(exe),'crop',str(out/'source.bgr'),str(out/'box.f32'),str(out/'patch.u8')],capture_output=True,text=True,env=env);assert z.returncode==0 and (out/'patch.u8').read_bytes()==crop_patch(sensor,box).tobytes();crops.append(dict(name=r['name'],roi_index=r['roi_index'],patch_sha256=sha(out/'patch.u8')))
 write(out/'complete.json',dict(status='SPATIAL_PERSON_VERIFIER_FP32_C_AND_CROP_PROVEN',parameters=12993,checkpoint_sha256=chosen['sha256'],weights_sha256=sha(out/'weights.f32'),test_patches=n,max_probability_abs=err,tolerance_probability=1e-5,real_sensor_crops6_byte_exact=crops,compiler=cmd,source_sha256={p.name:sha(p) for p in src.iterdir()},hardware_access=False,sd_written=False));print('SPATIAL_VERIFIER_C_ALL_PROBABILITIES_AND_CROPS_PASS',n,err,flush=True)
if __name__=='__main__':main()
