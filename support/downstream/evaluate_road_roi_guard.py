"""Old-validation selection only; previous fresh480 is never used in this search."""
from pathlib import Path
from road_roi_guard_common import *

def main():
 out=ROOT/'validation';out.mkdir(exist_ok=False)
 policies=[]
 for border,aspect in [(1.,.65),(2.,.65),(4.,.65),(2.,.8)]:
  for w in [.55,.70,.85]:policies.append(dict(border=border,person_aspect=[.2,aspect],weights=[w,.45,.5,.25],dedup_iou=.3,dedup_containment=.8))
 write(ROOT/'protocol.json',dict(status='GEOMETRY_POLICIES_FROZEN_BEFORE_VALIDATION_SEARCH',policies=policies,validation='Original320 only; weights checkpoint and preprocessing unchanged.',merge='Preserve all full-frame proposals. Reject only extra ROI boxes using boundary, person aspect and overlap with strong sameclass full detections, then scale scores and class-aware NMS0.6 max300.',selection='Unchanged duskAP gain>=.02, dusk person recall gain>=.03, night/day>=original-.005, dusk total/personFP<=1.10*original+2; additionally overallAP gain>=.01. Select maximum duskAP among passing policies, then overallAP. No threshold relaxation after results.',new_test='Requires a new previously unseen-group480 after policy freeze. Previous R2 test is excluded from search and future heldout images.',cost='Two detector forwards; not a speed improvement. No automatic live replacement without board latency evidence.',hardware_access=False,sd_written=False))
 from road_adapt_eval_core import evaluate_serial_predictions
 full=read(OLD/'full_predictions.json');roi={r['name']:r for r in read(OLD/'center_only_diagnostic_predictions.json')};baseline=read(OLD/'full_metrics.json');rows=[dict(name=r['name'],timeofday=r['timeofday'],label_path=str(BASE/'dataset/labels/val'/(Path(r['name']).stem+'.txt'))) for r in full]
 records=[]
 for i,p in enumerate(policies):
  tag=f'guard{i:02d}';pred={r['name']:fuse(r['detections'],roi[r['name']]['detections'],p) for r in full};m=evaluate_serial_predictions(rows,pred,out,tag);g=gates(baseline,m);records.append(dict(id=i,policy=p,metrics=m,gates=g,passed=all(g.values())))
  print('ROI_GUARD_VALIDATION',i,m['by_time']['dawn/dusk']['mAP50'],m['by_time']['dawn/dusk']['classes']['person']['recall'],m['by_time']['dawn/dusk']['classes']['person']['fp'],g,flush=True)
  write(out/'progress.json',records)
 good=[r for r in records if r['passed']];chosen=max(good,key=lambda r:(r['metrics']['by_time']['dawn/dusk']['mAP50'],r['metrics']['all']['mAP50'])) if good else None
 write(ROOT/'selected.json',dict(status='ROI_GUARD_SELECTION_FROZEN_BEFORE_NEW_TEST',baseline=baseline,records=records,chosen=chosen,qualified=bool(good),protocol_sha256=sha(ROOT/'protocol.json'),new_test_inference=False,hardware_access=False))
 print('ROI_GUARD_VALIDATION_COMPLETE',chosen['id'] if chosen else None,flush=True)
if __name__=='__main__':main()
