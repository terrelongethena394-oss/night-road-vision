"""One frozen balanced detector/refiner on unused240 low+64 bright, actual C."""
from pathlib import Path
import concurrent.futures as cf,os,shutil,subprocess,time
import numpy as np
from study_balanced_car_20261030 import ROOT,gates,f1
from car_box_refine_common import BASE,ZOOM,patch,read,write,sha
from car_patch_verifier_common import INITIAL
from prove_balanced_car_c import RefinerC
from prove_car_zoom_c import ZoomC
from confirm_car_zoom_native import BaseFusion
from road_accuracy_common import sensor400,truth,TILES,fuse,map_tile
from road_numpy_eval import evaluate
from evaluate_car_boxrefine import eligible,fuse_refined
from study_car_zoom_20261030 import XS,map_zoom
from confirm_road_viewadapt import statistics,car_ap50
from shadowlift_lab import words,mean_y

def main():
 selection=read(ROOT/'selected.json');assert selection['qualified'] and selection['chosen']['family']=='box_refiner'
 chosen=selection['chosen']['source'];assert read(ROOT/'c_complete.json')['selection_sha256']==sha(ROOT/'selected.json')
 out=ROOT/'confirmation';dataset=out/'fresh';manifest=read(dataset/'manifest.json');assert len(manifest)==304
 assert sum(r['cohort']=='low' for r in manifest)==240 and read(out/'protocol.json')['selection_sha256']==sha(ROOT/'selected.json')
 ledger=read(ROOT/'holdout_exclusions.json');assert not {r['group'] for r in manifest}&set(ledger['groups'])
 assert not {r['image_sha256'] for r in manifest}&set(ledger['image_hashes'])
 for r in manifest:
  assert sha(dataset/'images'/r['name'])==r['image_sha256']
  assert sha(dataset/'labels'/(Path(r['name']).stem+'.txt'))==r['label_sha256']
 weights=INITIAL.parent/'weights.f32';assert sha(weights)==read(INITIAL.parent/'complete.json')['weights_sha256']
 exe=BASE/'road_local_enhance_20261029_r2/host/road_ap.exe';assert sha(exe)==read(exe.parent/'build.json')['exe_sha256']
 policy=dict(status='FROZEN_BEFORE_UNUSED304_C_NETWORK_AND_REFINER_INFERENCE',selection_sha256=sha(ROOT/'selected.json'),
  detector_weights_sha256=sha(weights),refiner_weights_sha256=sha(ROOT/'export/weights.f32'),manifest_sha256=sha(dataset/'manifest.json'),
  balanced_gates=read(ROOT/'protocol.json')['balanced_gates'],ap_ci_confidence=.99,bootstrap_replicates=2000,bootstrap_seed=2026103083,
  unrefined7_control='Descriptive attribution only, never use to replace selected candidate after test.',
  no_fresh_driven_reselection=True,hardware_access=False,sd_written=False)
 if (out/'inference_policy.json').exists():assert read(out/'inference_policy.json')==policy
 else:write(out/'inference_policy.json',policy)
 scratch=out/'native_scratch';scratch.mkdir(exist_ok=True);pixels=ZoomC();basefusion=BaseFusion();refiner=RefinerC();y=read(ZOOM/'protocol.json')['geometry']['y']
 env=dict(os.environ);env['PATH']='E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin;'+env['PATH']
 begin=time.monotonic();views={};receipts=[]
 def one(task):
  at,r,tag=task;sensor,full=sensor400(dataset/'images'/r['name'])
  if tag=='global':im=full
  elif tag.startswith('raw'):
   x0,y0=TILES[int(tag[-1])];im=sensor[y0:y0+240,x0:x0+400]
  else:im=pixels.image(sensor,XS[int(tag[-1])],y)
  folder=scratch/(tag+'_'+str(at));folder.mkdir();ip=folder/'input.u32';words(im).tofile(ip)
  p=subprocess.run([str(exe),str(weights),str(ip),str(folder)],capture_output=True,text=True,env=env,timeout=90)
  assert p.returncode==0 and 'ROAD_FP32_HOST_DONE' in p.stdout,(r['name'],tag,p.stderr)
  pred=np.fromfile(folder/'boxes400.f32','<f4').reshape(-1,6);assert np.isfinite(pred).all()
  record=dict(name=r['name'],detections=pred.tolist());receipt=dict(name=r['name'],view=tag,input_sha256=sha(ip),boxes_sha256=sha(folder/'boxes400.f32'),decoded_sha256=sha(folder/'decoded.f32'))
  for f in folder.iterdir():
   assert f.resolve().is_relative_to(scratch.resolve()) and f.is_file();f.unlink()
  folder.rmdir();return record,receipt
 for tag in ['global','raw0','raw1','raw2','zoom0','zoom1','zoom2']:
  rows=[r for r in manifest if r['cohort']=='low'] if tag.startswith('zoom') else manifest
  cache=out/(tag+'_actual_c.json');rc=out/(tag+'_receipts.json')
  if cache.exists():views[tag]={r['name']:r['detections'] for r in read(cache)};receipts.extend(read(rc));continue
  records=[];evidence=[]
  with cf.ThreadPoolExecutor(4) as pool:
   for i,(record,receipt) in enumerate(pool.map(one,[(j,r,tag) for j,r in enumerate(rows)]),1):
    records.append(record);evidence.append(receipt)
    if i%48==0:print('BALANCED_CONFIRM_ACTUAL_C',tag,i,len(rows),round(time.monotonic()-begin),flush=True)
  write(cache,records);write(rc,evidence);views[tag]={r['name']:r['detections'] for r in records};receipts.extend(evidence)
 baseline=[];candidate=[];control=[];refiner_receipts=[];max_post=0.
 for at,r in enumerate(manifest):
  name=r['name'];sensor,full=sensor400(dataset/'images'/name);is_low=mean_y(full)<=48;assert is_low==(r['cohort']=='low')
  a=basefusion.run(views['global'][name],[views['raw'+str(i)][name] for i in range(3)],.75)
  reference=fuse(views['global'][name],[map_tile(views['raw'+str(i)][name],*TILES[i]) for i in range(3)],.75);assert a.tobytes()==reference.tobytes();a=a[a[:,5]==1]
  if is_low:
   local=[views['zoom'+str(i)][name] for i in range(3)];mapped=[map_zoom(local[j],x,y) for j,x in enumerate(XS)]
   outputs=[np.zeros((len(v),5),np.float32) for v in mapped];refiner.begin(sensor);count=0;strong=a[a[:,4]>=.25]
   for j,pp in enumerate(mapped):
    for i,b in enumerate(pp):
     if not eligible(b,strong):continue
     image,meta=refiner.crop(b);ref_image,ref_meta=patch(sensor,b)
     assert image.tobytes()==ref_image.tobytes() and np.max(np.abs(meta-ref_meta))<=1e-7
     outputs[j][i]=refiner.predict(image,meta);count+=1
   refiner.end();b=refiner.fuse(a,local,outputs,chosen);npref=fuse_refined(a,mapped,outputs,chosen['strength'],chosen['cap'],chosen['class_gate'])
   assert b.shape==npref.shape and np.max(np.abs(b-npref),initial=0)<=.0001,(name,b.shape,npref.shape)
   max_post=max(max_post,float(np.max(np.abs(b-npref),initial=0)));c=pixels.run(a,local,.65)
   refiner_receipts.append(dict(name=name,calls=count,outputs_sha256=__import__('hashlib').sha256(np.concatenate(outputs).tobytes()).hexdigest()))
  else:b=a.copy();c=a.copy();assert a.tobytes()==b.tobytes()==c.tobytes()
  gt=truth(dataset/'labels'/(Path(name).stem+'.txt'));gt=gt[gt[:,0]==1]
  baseline.append(dict(name=name,ground_truth=gt.tolist(),detections=a.tolist()));candidate.append(dict(name=name,ground_truth=gt.tolist(),detections=b.tolist()));control.append(dict(name=name,ground_truth=gt.tolist(),detections=c.tolist()))
  if (at+1)%80==0:print('BALANCED_C_REFINEMENT',at+1,len(manifest),flush=True)
 write(out/'baseline_predictions.json',baseline);write(out/'candidate_predictions.json',candidate);write(out/'unrefined_control_predictions.json',control);write(out/'refiner_receipts.json',refiner_receipts)
 scores={}
 for cohort in ['low','brighter']:
  names={r['name'] for r in manifest if r['cohort']==cohort};split={key:[r for r in values if r['name'] in names] for key,values in [('baseline',baseline),('candidate',candidate),('unrefined_control',control)]}
  scores[cohort]={key:evaluate(values)['classes']['car'] for key,values in split.items()}
  if cohort=='low':old=split['baseline'];new=split['candidate']
  else:assert split['baseline']==split['candidate']==split['unrefined_control']
 aa=statistics(old);bb=statistics(new);ids=np.arange(len(aa));assert abs(car_ap50(aa,ids)-scores['low']['baseline']['ap50'])<1e-12
 assert abs(car_ap50(bb,ids)-scores['low']['candidate']['ap50'])<1e-12
 rng=np.random.default_rng(policy['bootstrap_seed']);gain=[]
 for _ in range(2000):
  draw=rng.integers(0,len(aa),len(aa));gain.append(car_ap50(bb,draw)-car_ap50(aa,draw))
 ci=np.quantile(gain,[.005,.995]).tolist();gg=gates(scores['low']['baseline'],scores['low']['candidate']);gg['ap_gain_ci99_positive']=ci[0]>0
 accepted=all(gg.values());result=dict(status='BALANCED_UNUSED304_ACTUAL_C_CONFIRMATION_ACCEPTED' if accepted else 'BALANCED_UNUSED304_ACTUAL_C_CONFIRMATION_REJECTED_KEEP_ABI27',accepted=accepted,
  scores=scores,gates=gg,car_ap50_difference_interval99=ci,bootstrap_replicates=2000,
  f1={cohort:{key:f1(m) for key,m in values.items()} for cohort,values in scores.items()},brighter_outputs_byte_exact=True,
  actual_detector_c_forwards=len(receipts),actual_refiner_c_calls=sum(r['calls'] for r in refiner_receipts),all_refiner_crop_pixels_numpy_byte_exact=True,max_post_c_numpy_abs=max_post,
  selection_sha256=sha(ROOT/'selected.json'),manifest_sha256=sha(dataset/'manifest.json'),inference_policy_sha256=sha(out/'inference_policy.json'),
  no_test_driven_reselection=True,seconds=time.monotonic()-begin,hardware_access=False,sd_written=False)
 write(out/'fresh_result.json',result);shutil.copy2(__file__,ROOT/'source'/Path(__file__).name)
 print('BALANCED_UNUSED304_RESULT',result,flush=True)

if __name__=='__main__':main()
