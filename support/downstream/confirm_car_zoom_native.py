"""One frozen zoom method, actual portable C on all unused224 images."""
from pathlib import Path
import concurrent.futures as cf,ctypes as ct,os,shutil,subprocess,time
import numpy as np
from study_car_zoom_20261030 import ROOT,XS,gates,map_zoom,fuse_zoom
from prove_car_zoom_c import ZoomC
from road_enhanceadapt_common import BASE,INITIAL,read,write,sha
from road_accuracy_common import sensor400,truth,TILES,fuse,map_tile
from road_numpy_eval import evaluate
from road_classwise_native import Box
from confirm_road_viewadapt import statistics,car_ap50
from shadowlift_lab import words,mean_y

class BaseFusion(ZoomC):
 def __init__(self):
  path=BASE/'road_brightness_route_20261030_r1/fresh_evaluation/routed_low/native/fusion.dll'
  self.lib=ct.CDLL(str(path));self.bp=ct.POINTER(Box);self.fuse=self.lib.road_vehicle_multiview
  self.fuse.argtypes=[self.bp,ct.c_int,self.bp,ct.POINTER(ct.c_int),ct.c_float,self.bp,ct.c_int];self.fuse.restype=ct.c_int

def main():
 selected=read(ROOT/'selected.json');assert selected['qualified']
 assert read(ROOT/'c_complete.json')['selection_sha256']==sha(ROOT/'selected.json')
 out=ROOT/'confirmation';dataset=out/'fresh';manifest=read(dataset/'manifest.json');assert len(manifest)==224
 assert read(out/'protocol.json')['selection_sha256']==sha(ROOT/'selected.json')
 assert sha(INITIAL)==selected['model_sha256']
 weights=INITIAL.parent/'weights.f32';expected=read(INITIAL.parent/'complete.json')['weights_sha256'];assert sha(weights)==expected
 exe=BASE/'road_local_enhance_20261029_r2/host/road_ap.exe';assert sha(exe)==read(exe.parent/'build.json')['exe_sha256']
 seen=read(ROOT/'holdout_exclusions.json');assert not {r['group'] for r in manifest}&set(seen['groups'])
 assert not {r['image_sha256'] for r in manifest}&set(seen['image_hashes'])
 for r in manifest:
  assert sha(dataset/'images'/r['name'])==r['image_sha256']
  assert sha(dataset/'labels'/(Path(r['name']).stem+'.txt'))==r['label_sha256']
 policy=dict(status='FROZEN_BEFORE_ANY_UNUSED224_C_INFERENCE',selection_sha256=sha(ROOT/'selected.json'),
  weights_sha256=expected,manifest_sha256=sha(dataset/'manifest.json'),
  post_C_proof_sha256=sha(ROOT/'c_complete.json'),primary='Same frozen gates and99%paired image bootstrap AP gain lower>0 on low160,brighter64 route outputs byte-identical.',
  bootstrap_seed=2026103045,bootstrap_replicates=2000,hardware_access=False,sd_written=False)
 if (out/'inference_policy.json').exists():assert read(out/'inference_policy.json')==policy
 else:write(out/'inference_policy.json',policy)
 env=dict(os.environ);env['PATH']='E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin;'+env['PATH']
 scratch=out/'native_scratch';scratch.mkdir(exist_ok=True);zoomer=ZoomC();basefusion=BaseFusion()
 y=read(ROOT/'protocol.json')['geometry']['y'];weight=selected['chosen']['weight'];begin=time.monotonic()
 views={};receipts=[]
 def one(task):
  at,r,tag=task;sensor,full=sensor400(dataset/'images'/r['name'])
  if tag=='global':im=full
  elif tag.startswith('raw'):
   x0,y0=TILES[int(tag[-1])];im=sensor[y0:y0+240,x0:x0+400]
  else:im=zoomer.image(sensor,XS[int(tag[-1])],y)
  folder=scratch/(tag+'_'+str(at));folder.mkdir();ip=folder/'input.u32';words(im).tofile(ip)
  p=subprocess.run([str(exe),str(weights),str(ip),str(folder)],capture_output=True,text=True,env=env,timeout=90)
  assert p.returncode==0 and 'ROAD_FP32_HOST_DONE' in p.stdout,(r['name'],tag,p.stdout,p.stderr)
  pred=np.fromfile(folder/'boxes400.f32','<f4').reshape(-1,6);assert np.isfinite(pred).all()
  receipt=dict(name=r['name'],view=tag,input_sha256=sha(ip),boxes_sha256=sha(folder/'boxes400.f32'),
               decoded_sha256=sha(folder/'decoded.f32') if (folder/'decoded.f32').exists() else None)
  for f in folder.iterdir():
   assert f.resolve().is_relative_to(scratch.resolve()) and f.is_file();f.unlink()
  folder.rmdir();return dict(name=r['name'],detections=pred.tolist()),receipt
 for tag in ['global','raw0','raw1','raw2','zoom0','zoom1','zoom2']:
  rr=[r for r in manifest if r['cohort']=='low'] if tag.startswith('zoom') else manifest
  cache=out/(tag+'_actual_c.json');rc=out/(tag+'_receipts.json')
  if cache.exists():views[tag]={r['name']:r['detections'] for r in read(cache)};receipts.extend(read(rc));continue
  records=[];evidence=[]
  with cf.ThreadPoolExecutor(4) as pool:
   for i,(record,receipt) in enumerate(pool.map(one,[(j,r,tag) for j,r in enumerate(rr)]),1):
    records.append(record);evidence.append(receipt)
    if i%32==0:print('ZOOM_CONFIRM_ACTUAL_C',tag,i,len(rr),round(time.monotonic()-begin),flush=True)
  write(cache,records);write(rc,evidence);views[tag]={r['name']:r['detections'] for r in records};receipts.extend(evidence)
 old=[];new=[];route={}
 for r in manifest:
  name=r['name'];sensor,full=sensor400(dataset/'images'/name);mean=mean_y(full);is_low=mean<=48
  assert is_low==(r['cohort']=='low')
  a=basefusion.run(views['global'][name],[views['raw'+str(i)][name] for i in range(3)],.75)
  reference=fuse(views['global'][name],[map_tile(views['raw'+str(i)][name],*TILES[i]) for i in range(3)],.75)
  assert a.tobytes()==reference.tobytes();a=a[a[:,5]==1]
  if is_low:
   b=zoomer.run(a,[views['zoom'+str(i)][name] for i in range(3)],weight)
   ref=fuse_zoom(a,[map_zoom(views['zoom'+str(i)][name],x,y) for i,x in enumerate(XS)],weight)
   assert b.tobytes()==ref.tobytes()
  else:b=a.copy();assert b.tobytes()==a.tobytes()
  gt=truth(dataset/'labels'/(Path(name).stem+'.txt'));gt=gt[gt[:,0]==1]
  old.append(dict(name=name,ground_truth=gt.tolist(),detections=a.tolist()))
  new.append(dict(name=name,ground_truth=gt.tolist(),detections=b.tolist()));route[name]=is_low
 scores={};gg={}
 for group in ['low','brighter']:
  mask={r['name'] for r in manifest if r['cohort']==group};aa=[r for r in old if r['name'] in mask];bb=[r for r in new if r['name'] in mask]
  scores[group]=dict(baseline=evaluate(aa)['classes']['car'],candidate=evaluate(bb)['classes']['car'])
  if group=='low':gg=gates(scores[group]['baseline'],scores[group]['candidate']);low_old=aa;low_new=bb
  else:assert aa==bb
 a=statistics(low_old);b=statistics(low_new);ids=np.arange(len(a))
 assert abs(car_ap50(a,ids)-scores['low']['baseline']['ap50'])<1e-12
 assert abs(car_ap50(b,ids)-scores['low']['candidate']['ap50'])<1e-12
 rng=np.random.default_rng(policy['bootstrap_seed']);differences=[]
 for _ in range(policy['bootstrap_replicates']):
  draw=rng.integers(0,len(a),len(a));differences.append(car_ap50(b,draw)-car_ap50(a,draw))
 interval=np.quantile(differences,[.005,.995]).tolist();gg['ap_gain_ci99_positive']=interval[0]>0
 accepted=all(gg.values());write(out/'baseline_predictions.json',old);write(out/'candidate_predictions.json',new)
 result=dict(status='ZOOM_UNUSED224_ACTUAL_C_CONFIRMATION_ACCEPTED' if accepted else 'ZOOM_UNUSED224_ACTUAL_C_CONFIRMATION_REJECTED_KEEP_ABI27',accepted=accepted,
  scores=scores,low_gates=gg,car_ap50_difference_interval99=interval,bootstrap_replicates=2000,
  brighter_outputs_byte_identical=True,all_actual_c_fusion_numpy_byte_exact=True,
  images=224,actual_c_forwards=len(receipts),source_manifest_sha256=sha(dataset/'manifest.json'),
  selection_sha256=sha(ROOT/'selected.json'),weights_sha256=expected,inference_policy_sha256=sha(out/'inference_policy.json'),
  seconds=time.monotonic()-begin,no_test_driven_reselection=True,hardware_access=False,sd_written=False)
 write(out/'fresh_result.json',result);shutil.copy2(__file__,ROOT/'source'/Path(__file__).name)
 print('ZOOM_UNUSED_CONFIRMATION',result,flush=True)

if __name__=='__main__':main()
