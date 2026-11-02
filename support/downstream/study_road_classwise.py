"""Choose score multipliers on reused320 development images only."""
import itertools,shutil
from road_classwise_common import *
HERE=Path(__file__).resolve().parent
def main():
 assert not ROOT.exists();ROOT.mkdir();(ROOT/'source').mkdir()
 views={k:read(OLD/'development/views'/(k+'.json')) for k in ['global_raw','tile_raw_0','tile_raw_1','tile_raw_2']}
 protocol=dict(status='FROZEN_BEFORE_NEW_CALIBRATION_OUTPUTS',purpose='Reduce extra truck/bus false positives while retaining verified car gain. Fusion score multipliers only; no network training or change to image enhancement.',grid=dict(person=[0],car=[.75],truck=GRID,bus=GRID),development='Previously used original320 only; never call it a new holdout.',source_sha256={k:sha(OLD/'development/views'/(k+'.json')) for k in views},gates='Car AP each period and overall point precision/recall drop<=0.1pp; four-class AP drop<=0.5pp vs current; each truck/bus AP no worse than original single minus0.5pp, each TP>=single, combinedTP>=80%current, combinedFP<=75%current.',selection='Among eligible maximize combined truck/bus F0.5 at conf.25/IoU.5; tie break by overall AP. Freeze before reused low320 regression and any new confirmation.',fresh_plan='If eligible and reused low320 regression passes same gates, reserve240 new low-brightness and96 brighter images before any predictions. New test cannot reselect parameters.',hardware_access=False,sd_written=False)
 write(ROOT/'protocol.json',protocol)
 for pattern in ['*road_classwise*.py','road_vehicle_classwise.*']:
  for p in HERE.glob(pattern):shutil.copy2(p,ROOT/'source'/p.name)
 raw=metrics(views['global_raw']);records=[]
 for tw,bw in itertools.product(GRID,GRID):
  weights=[0.,.75,tw,bw];rows=[]
  for i,r in enumerate(views['global_raw']):
   ts=[views['tile_raw_'+str(j)][i]['detections'] for j in range(3)]
   assert all(views['tile_raw_'+str(j)][i]['name']==r['name'] for j in range(3))
   pred=fuse(r['detections'],ts,weights)
   rows.append(dict(name=r['name'],timeofday=r['timeofday'],ground_truth=r['ground_truth'],detections=pred.tolist()))
  m=metrics(rows);records.append(dict(weights=weights,metrics=m,truck_bus=combined(m)))
  print('CLASSWISE_DEV',weights,combined(m),'mAP',m['all']['mAP50'],flush=True)
 current=next(r['metrics'] for r in records if r['weights']==[0.,.75,.75,.75])
 expected=read(OLD/'selected.json')['chosen']['metrics'];assert abs(current['all']['mAP50']-expected['all']['mAP50'])<1e-12
 qualified=[]
 for r in records:
  r['gates']=gates(raw,current,r['metrics'])
  if all(r['gates'].values()):qualified.append(r)
 chosen=max(qualified,key=lambda r:(r['truck_bus']['f05'],r['metrics']['all']['mAP50'])) if qualified else None
 write(ROOT/'selected.json',dict(status='CLASSWISE_FROZEN_BEFORE_REGRESSION_OR_NEW_TEST',qualified=bool(qualified),chosen=chosen,records=records,raw=raw,current=current,protocol_sha256=sha(ROOT/'protocol.json'),no_new_test_inference=True,hardware_access=False,sd_written=False))
 print('CLASSWISE_SELECTION',chosen,flush=True)
if __name__=='__main__':main()
