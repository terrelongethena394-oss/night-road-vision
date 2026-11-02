"""Second development attempt: keep the same gates on BOTH reused cohorts."""
import concurrent.futures as cf,hashlib,itertools,os,shutil,subprocess,time
from road_classwise_common import *
from road_accuracy_common import sensor400
from road_classwise_native import Engine
HERE=Path(__file__).resolve().parent
ROOT=BASE/'road_classwise_20261030_r2'
GRID_T=[.4,.425,.45,.475,.5,.525,.55,.575,.6,.65,.75]
GRID_B=[.25,.35,.4,.45,.5,.55,.6,.65,.75]

def encode(a):
 z=a.astype(np.uint32);return (z[:,:,0]|z[:,:,1]<<8|z[:,:,2]<<16).astype('<u4')
def cache_known_development():
 out=ROOT/'known320_native';out.mkdir()
 raw=read(BASE/'road_local_enhance_20261029_r2/road_validation320/raw_predictions.json')
 for r in raw:
  _,full=sensor400(DATA/'dataset/images/val'/r['name']);assert hashlib.sha256(encode(full).tobytes()).hexdigest()==r['input_sha256']
 write(out/'global_raw.json',raw)
 exe=BASE/'road_local_enhance_20261029_r2/host/road_ap.exe';build=read(BASE/'road_local_enhance_20261029_r2/host/build.json')
 assert sha(exe)==build['exe_sha256'] and sha(APP/'runtime/weights.f32')==build['weights_sha256']
 env=dict(os.environ);env['PATH']='E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin;'+env['PATH']
 scratch=out/'scratch';scratch.mkdir();begin=time.monotonic()
 def one(item):
  at,r,t=item;sensor,_=sensor400(DATA/'dataset/images/val'/r['name']);tile=sensor[120:360,t*200:t*200+400];folder=scratch/(str(t)+'_'+str(at));folder.mkdir();ip=folder/'input.u32';encode(tile).tofile(ip)
  p=subprocess.run([str(exe),str(APP/'runtime/weights.f32'),str(ip),str(folder)],capture_output=True,text=True,env=env,timeout=90);assert p.returncode==0 and 'ROAD_FP32_HOST_DONE' in p.stdout
  pred=np.fromfile(folder/'boxes400.f32','<f4').reshape(-1,6)
  for f in folder.iterdir():assert f.resolve().is_relative_to(scratch.resolve()) and f.is_file();f.unlink()
  folder.rmdir();return pred
 for t in range(3):
  local=[];mapped=[]
  with cf.ThreadPoolExecutor(2) as pool:
   for at,pred in enumerate(pool.map(one,[(i,r,t) for i,r in enumerate(raw)])):
    local.append(pred.tolist());r=raw[at];mapped.append(dict(name=r['name'],timeofday=r['timeofday'],ground_truth=r['ground_truth'],detections=map_tile(pred,t*200,120).tolist()))
    if (at+1)%80==0:print('CLASSWISE_KNOWN_C_VIEWS',t,at+1,round(time.monotonic()-begin),flush=True)
  write(out/('tile_raw_'+str(t)+'_local.json'),local);write(out/('tile_raw_'+str(t)+'.json'),mapped)
 write(out/'complete.json',dict(status='KNOWN320_ALL_RGB888_INPUT_SHA_MATCH_REUSED_C_GLOBAL_NEW_C_TILES',global_source=build,images=320,weights_sha256=sha(APP/'runtime/weights.f32'),hardware_access=False))
 return out

def load_cohort(folder):
 return dict(full=read(folder/'global_raw.json'),mapped=[read(folder/('tile_raw_'+str(i)+'.json')) for i in range(3)],local=[read(folder/('tile_raw_'+str(i)+'_local.json')) for i in range(3)])
def score(data,weights):
 rows=[]
 for at,r in enumerate(data['full']):
  pred=fuse(r['detections'],[data['mapped'][i][at]['detections'] for i in range(3)],weights)
  rows.append(dict(name=r['name'],timeofday=r['timeofday'],ground_truth=r['ground_truth'],detections=pred.tolist()))
 return metrics(rows),rows
def main():
 assert not ROOT.exists();ROOT.mkdir();(ROOT/'source').mkdir()
 assert read(BASE/'road_classwise_20261030_r1/regression.json')['passes'] is False
 write(ROOT/'protocol.json',dict(status='FROZEN_BEFORE_JOINT_DEVELOPMENT',reason='R1 failed known low320 true-positive retention and is rejected. No new test images were used. R2 uses both reused cohorts as development and refines grid; all previous acceptance gates remain required separately on each cohort.',grids=dict(car=[.75],truck=GRID_T,bus=GRID_B),cohorts=['Original320 reused validation','Previous low320 confirmation, now reused development, no longer independent for this candidate'],all_same_gates_per_cohort=True,required_tp_retention=.8,required_fp_retention=.75,allowed_fourclass_map_drop=.005,car_ap_allowed_drop=.001,selection='Among candidates passing every gate on both cohorts, maximize pooled truck/bus F0.5, tie break by mean four-class AP. Freeze before any new independent test.',fresh_plan=dict(low_brightness=240,brighter=96,raw_low_mean_max=48,raw_brighter_mean_min=70),hardware_access=False,sd_written=False))
 for pattern in ['*road_classwise*.py','road_vehicle_classwise.*']:
  for p in HERE.glob(pattern):shutil.copy2(p,ROOT/'source'/p.name)
 folder=cache_known_development();data={'known':load_cohort(folder),'low':load_cohort(LOW/'native')}
 raw={k:metrics(v['full']) for k,v in data.items()};current={k:score(v,[0.,.75,.75,.75])[0] for k,v in data.items()};records=[]
 for index,(tw,bw) in enumerate(itertools.product(GRID_T,GRID_B),1):
  weights=[0.,.75,tw,bw];scores={k:score(v,weights)[0] for k,v in data.items()};gg={k:gates(raw[k],current[k],scores[k]) for k in data}
  a=[combined(scores[k]) for k in data];tp=sum(r['tp'] for r in a);fp=sum(r['fp'] for r in a);objects=sum(r['objects'] for r in a);p=tp/(tp+fp);r=tp/objects;f=1.25*p*r/(.25*p+r)
  record=dict(weights=weights,scores=scores,gates=gg,passes=all(all(g.values()) for g in gg.values()),pooled=dict(tp=tp,fp=fp,precision=p,recall=r,f05=f));records.append(record)
  if index%9==0:print('CLASSWISE_JOINT_SCORED',index,len(GRID_T)*len(GRID_B),'qualified',sum(r['passes'] for r in records),flush=True)
 candidates=[r for r in records if r['passes']];chosen=max(candidates,key=lambda r:(r['pooled']['f05'],np.mean([z['all']['mAP50'] for z in r['scores'].values()]))) if candidates else None
 write(ROOT/'selected.json',dict(status='JOINT_CANDIDATE_FROZEN_BEFORE_NEW_TEST',qualified=bool(chosen),chosen=chosen,records=records,raw=raw,current=current,protocol_sha256=sha(ROOT/'protocol.json'),hardware_access=False,sd_written=False))
 if chosen:
  engine=Engine(ROOT);proofs={}
  for k,v in data.items():
   m,rows=score(v,chosen['weights']);out=ROOT/('chosen_'+k);out.mkdir();car_point_diffs=0
   _,uniform=score(v,[0.,.75,.75,.75])
   for at,r in enumerate(rows):
    actual=engine.run(v['full'][at]['detections'],[v['local'][i][at] for i in range(3)],chosen['weights']);assert actual.tobytes()==np.asarray(r['detections'],'<f4').tobytes()
    a=np.asarray(uniform[at]['detections'],np.float32).reshape(-1,6);a=a[(a[:,5]==1)&(a[:,4]>=.25)];b=actual[(actual[:,5]==1)&(actual[:,4]>=.25)]
    car_point_diffs+=sorted(map(tuple,a.tolist()))!=sorted(map(tuple,b.tolist()))
   write(out/'predictions.json',rows);write(out/'metrics.json',m);proofs[k]=dict(images=len(rows),c_numpy_all_fusion_byte_exact=True,guards_pass=True,car_point_changed_images=car_point_diffs)
  write(ROOT/'c_complete.json',dict(status='ALL640_C_AND_NUMPY_CLASSWISE_FUSION_BYTE_EXACT',cohorts=proofs,selection_sha256=sha(ROOT/'selected.json'),hardware_access=False,sd_written=False))
 print('CLASSWISE_JOINT_SELECTION',None if not chosen else dict(weights=chosen['weights'],pooled=chosen['pooled'],per_cohort={k:combined(v) for k,v in chosen['scores'].items()}),flush=True)
if __name__=='__main__':main()
