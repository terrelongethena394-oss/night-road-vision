"""Actual C forward and frozen classwise fusion on the new confirmation set."""
import shutil
from road_classwise_common import *
from road_classwise_native import Engine,apply_cached
ROOT=BASE/'road_classwise_20261030_r2'
HERE=Path(__file__).resolve().parent

def point_counts(rows):
 out=[]
 for r in rows:
  p=np.asarray(r['detections'],np.float32).reshape(-1,6);p=p[p[:,4]>=.25];g=np.asarray(r['ground_truth'],np.float32).reshape(-1,5);ok=correct(p,g,np.array([.5],np.float32))[0][:,0];mask=np.isin(p[:,5],[2,3])
  out.append([int((mask&ok).sum()),int((mask&~ok).sum()),int(np.isin(g[:,0],[2,3]).sum())])
 return np.asarray(out,np.int64)
def paired_uncertainty(before,after,seed):
 a=point_counts(before);b=point_counts(after);n=len(a);assert n==len(b) and [r['name'] for r in before]==[r['name'] for r in after]
 rng=np.random.default_rng(seed);fp=[];precision=[];tp=[]
 for _ in range(1000):
  ix=rng.integers(0,n,n);aa=a[ix].sum(0);bb=b[ix].sum(0)
  fp.append((aa[1]-bb[1])*100/n);tp.append((bb[0]-aa[0])*100/n)
  precision.append(bb[0]/max(1,bb[0]+bb[1])-aa[0]/max(1,aa[0]+aa[1]))
 return dict(images=n,replicates=1000,seed=seed,unit='one unique image/first8 prefix group',fp_reduction_per100_images_interval99=np.quantile(fp,[.005,.995]).tolist(),precision_difference_interval99=np.quantile(precision,[.005,.995]).tolist(),tp_change_per100_images_interval99=np.quantile(tp,[.005,.995]).tolist())

def main():
 assert (ROOT/'fresh/complete.json').exists() and not (ROOT/'fresh_result.json').exists()
 selected=read(ROOT/'selected.json');policy=read(ROOT/'fresh_protocol.json')
 assert selected['qualified'] and policy['selected_sha256']==sha(ROOT/'selected.json')
 assert read(ROOT/'c_complete.json')['selection_sha256']==sha(ROOT/'selected.json')
 write(ROOT/'evaluation_policy.json',dict(status='FROZEN_BEFORE_CONFIRMATION_INFERENCE',selected_sha256=sha(ROOT/'selected.json'),data_sha256=sha(ROOT/'fresh/manifest.json'),weights=selected['chosen']['weights'],primary='Truck+bus false-positive count per image, with retained TP and car/fourclass quality vetoes',bootstrap=1000,confidence99=True,cohorts=read(ROOT/'fresh/complete.json')['cohorts'],hardware_access=False,sd_written=False))
 import native_road_accuracy as native
 native.ROOT=ROOT;native.SELECTION_FILE=OLD/'selected.json'
 if not (ROOT/'native/complete.json').exists():native.main()
 else:assert read(ROOT/'native/complete.json')['selection_sha256']==sha(OLD/'selected.json')
 out=ROOT/'confirmation';out.mkdir(exist_ok=True);engine=Engine(ROOT)
 proof=apply_cached(engine,ROOT/'native',selected['chosen']['weights'],out,'classwise')
 base=read(ROOT/'native/baseline_predictions.json');current=read(ROOT/'native/candidate_predictions.json');candidate=read(out/'classwise_predictions.json')
 manifest=read(ROOT/'fresh/manifest.json');cohorts={r['name']:r['cohort'] for r in manifest};scores={};uncertainty={};gg={}
 for cohort in ['low','brighter']:
  a=[r for r in base if cohorts[r['name']]==cohort];b=[r for r in current if cohorts[r['name']]==cohort];c=[r for r in candidate if cohorts[r['name']]==cohort]
  scores[cohort]=dict(single=metrics(a),current=metrics(b),candidate=metrics(c));g=gates(scores[cohort]['single'],scores[cohort]['current'],scores[cohort]['candidate'])
  u=paired_uncertainty(b,c,SEED+71+(0 if cohort=='low' else 1));uncertainty[cohort]=u;g['fp_reduction_ci99_positive']=u['fp_reduction_per100_images_interval99'][0]>0;gg[cohort]=g
  print('CLASSWISE_CONFIRMATION_COHORT',cohort,'before',combined(scores[cohort]['current']),'after',combined(scores[cohort]['candidate']),'gates',g,'uncertainty',u,flush=True)
 accepted=all(all(g.values()) for g in gg.values())
 result=dict(status='CLASSWISE_INDEPENDENT_CONFIRMATION_ACCEPTED' if accepted else 'CLASSWISE_INDEPENDENT_CONFIRMATION_REJECTED_RETAIN_ABI24',accepted=accepted,weights=selected['chosen']['weights'],scores=scores,gates=gg,paired_uncertainty=uncertainty,c_proof=proof,selection_sha256=sha(ROOT/'selected.json'),data_sha256=sha(ROOT/'fresh/manifest.json'),no_test_driven_reselection=True,hardware_access=False,sd_written=False)
 write(ROOT/'fresh_result.json',result);shutil.copy2(Path(__file__),ROOT/'source'/Path(__file__).name)
 print('CLASSWISE_INDEPENDENT_CONFIRMATION_DONE',result['status'],flush=True)
if __name__=='__main__':main()
