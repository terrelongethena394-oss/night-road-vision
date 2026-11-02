"""C sensor-crop + learned verification + geometry + NMS against old/new predictions."""
from pathlib import Path
import os,shutil,struct,subprocess
import cv2,numpy as np
from road_roi_spatial_common import *
HERE=Path(__file__).resolve().parent

def main():
 selected=read(ROOT/'selected.json');assert selected['qualified'];chosen=selected['chosen'];assert (ROOT/'fresh_complete.json').exists() and (ROOT/'native_verifier/complete.json').exists();out=ROOT/'native_pipeline';out.mkdir(exist_ok=False);src=out/'source';src.mkdir()
 for n in ['road_roi_verified.h','road_roi_verified.c','road_roi_verified_host.c','road_roi_guard.h','road_roi_guard.c','road_person_verifier.h','road_person_verifier.c']:shutil.copy2(HERE/n,src/n)
 for n in ['road_fp32.h','road_graph.h']:shutil.copy2(BASE.parent/'road_enhance_20261027/firmware/source'/n,src/n)
 gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=os.environ.copy();env['PATH']=str(gcc.parent)+';'+env['PATH'];exe=out/'pipeline.exe';cmd=list(map(str,[gcc,'-O3','-std=c99','-ffp-contract=off','-fno-fast-math','-Wall','-Wextra','-Werror','-I'+str(src),src/'road_roi_verified.c',src/'road_roi_guard.c',src/'road_person_verifier.c',src/'road_roi_verified_host.c','-lm','-o',exe]));r=subprocess.run(cmd,capture_output=True,text=True,env=env);(out/'build.log').write_text(r.stdout+r.stderr,encoding='utf-8');assert r.returncode==0,r.stderr
 p=read(ROOT/'protocol.json')['roi_policy'];np.asarray([p['border'],*p['person_aspect'],*p['weights'],p['dedup_iou'],p['dedup_containment']],'<f4').tofile(out/'policy.f32');weights=ROOT/'native_verifier/weights.f32';assert sha(weights)==read(ROOT/'native_verifier/complete.json')['weights_sha256'];records=[]
 tag=f"epoch{chosen['epoch']}_floor"+str(chosen['floor']).replace('.','p')
 groups=[('old320',read(OLD/'full_predictions.json'),{r['name']:r['detections'] for r in read(OLD/'center_only_diagnostic_predictions.json')},{r['name']:r['detections'] for r in read(ROOT/'validation'/(tag+'_predictions.json'))},BASE/'dataset/images/val'),('new480',read(ROOT/'fresh_evaluation/original_predictions.json'),read(ROOT/'fresh_evaluation/unmerged_roi_predictions.json'),{r['name']:r['detections'] for r in read(ROOT/'fresh_evaluation/guarded_roi_predictions.json')},ROOT/'fresh/images')]
 def ordered(a):return a[np.lexsort((a[:,3],a[:,2],a[:,1],a[:,0],a[:,5]))] if len(a) else a
 for label,full,roi,gold,folder in groups:
  for i,row in enumerate(full):
   name=row['name'];a=np.asarray(row['detections'],'<f4').reshape(-1,6);z=np.asarray(roi[name],'<f4').reshape(-1,6);(out/'boxes.bin').write_bytes(struct.pack('<II',len(a),len(z))+a.tobytes()+z.tobytes());image=cv2.imread(str(folder/name))[:,:,::-1].copy();sensor=cv2.resize(image,(800,480),interpolation=cv2.INTER_LINEAR);sensor[:,:,0]&=248;sensor[:,:,1]&=252;sensor[:,:,2]&=248;(out/'source.bgr').write_bytes(sensor[:,:,::-1].tobytes());r=subprocess.run([str(exe),str(out/'policy.f32'),str(weights),str(out/'source.bgr'),str(out/'boxes.bin'),str(out/'answer.f32'),str(chosen['floor'])],capture_output=True,text=True,env=env);assert r.returncode==0,(name,r.stderr)
   a=ordered(np.fromfile(out/'answer.f32','<f4').reshape(-1,6));b=ordered(np.asarray(gold[name],np.float32).reshape(-1,6));assert a.shape==b.shape,(label,name,a.shape,b.shape)
   if len(a):
    d=abs(a-b);assert np.array_equal(a[:,5],b[:,5]) and d[:,:4].max()<=1e-4 and d[:,4].max()<=1e-6,(label,name,float(d.max()));assert np.array_equal(a[:,4]>=.25,b[:,4]>=.25);err=float(d.max())
   else:err=0.
   records.append(dict(group=label,name=name,proposals_out=len(a),max_abs=err))
   if (i+1)%80==0:print('ROI_VERIFIED_C_PIPELINE_PASS',label,i+1,flush=True)
 write(out/'complete.json',dict(status='ACTUAL_C_CROP_PERSON_NETWORK_FUSION_ALL800_PROVEN',cases=records,tolerance_coordinates=1e-4,tolerance_score=1e-6,operating_threshold_decisions_exact=True,weights_sha256=sha(weights),compiler=cmd,source_sha256={p.name:sha(p) for p in src.iterdir()},detector_proposals='From independently evaluated original detector; this check validates new postprocessing, not a new all800 board inference.',hardware_access=False,sd_written=False));print('ROI_VERIFIED_C_FULL_PIPELINE_ALL800_PASS',flush=True)
if __name__=='__main__':main()
