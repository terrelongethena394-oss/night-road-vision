"""Materialize an auditable verifier extension to the frozen paired-test harness."""
from pathlib import Path
import runpy
from road_roi_verifier_common import ROOT,read,sha,write
HERE=Path(__file__).resolve().parent
COMMON_MODULE='road_roi_verifier_common'

def main():
 assert read(ROOT/'selected.json')['qualified']
 source=(HERE/'test_road_roi_guard.py').read_text(encoding='utf-8')
 def replace(a,b):
  nonlocal source
  assert source.count(a)==1,(a,source.count(a));source=source.replace(a,b)
 replace('from road_roi_guard_common import *','from '+COMMON_MODULE+' import *\nfrom road_roi_guard_common import gates')
 replace("policy=selected['chosen']['policy'];","policy=read(ROOT/'protocol.json')['roi_policy'];")
 replace("original={};merged={};roi_only={};t=time.monotonic()","original={};merged={};roi_only={};verifier_scores={};sensors={};t=time.monotonic();choice=selected['chosen'];assert sha(choice['checkpoint'])==choice['sha256'];verifier=make_model().cuda().eval();verifier.load_state_dict(torch.load(choice['checkpoint'],map_location='cpu',weights_only=False)['state_dict']);floor=choice['floor']")
 replace('    inputs.extend([preprocess400(full)',"    sensors[r['name']]=sensor\n    inputs.extend([preprocess400(full)")
 replace("merged[r['name']]=fuse(original[r['name']],roi_only[r['name']],policy)","merged[r['name']],verifier_scores[r['name']]=verified_merge(original[r['name']],roi_only[r['name']],sensors[r['name']],verifier,floor,policy)")
 replace("write(out/'unmerged_roi_predictions.json',roi_only);","write(out/'unmerged_roi_predictions.json',roi_only);write(out/'verifier_probabilities.json',verifier_scores);")
 replace("checkpoint_sha256=TEACHER_SHA))","checkpoint_sha256=TEACHER_SHA,verifier_sha256=selected['chosen']['sha256'],verifier_floor=selected['chosen']['floor']))")
 replace("policy=policy,source='BDD", "policy=policy,verifier_sha256=choice['sha256'],verifier_floor=floor,source='BDD")
 source=source.replace('2026102852','2026102856').replace('np.percentile(deltas,[2.5,97.5])','np.percentile(deltas,[1.25,98.75])').replace('interval95=ci','interval97_5=ci').replace('ROI_GUARD','VERIFIER')
 helper='''
def verified_merge(full,roi,sensor,model,floor,policy):
 import torch
 indices=[i for i,p in enumerate(np.asarray(roi,np.float32).reshape(-1,6)) if person_eligible(full,p,policy)]
 probs={}
 if indices:
  patches=np.stack([crop_patch(sensor,roi[i]) for i in indices]);x=torch.from_numpy(np.ascontiguousarray(patches.transpose(0,3,1,2))).cuda().float()/255
  values=model(x).sigmoid().flatten().cpu().tolist();probs=dict(zip(indices,values))
 return verified_fuse(full,roi,policy,probs,floor),probs

'''
 replace("if __name__=='__main__':main()",helper+"if __name__=='__main__':main()")
 path=ROOT/'source/test_new_verifier_materialized.py';assert not path.exists();compile(source,str(path),'exec');path.write_text(source,encoding='utf-8');write(ROOT/'materialized_test_source.json',dict(source_sha256=sha(path),parent_harness_sha256=sha(HERE/'test_road_roi_guard.py'),no_test_outcomes_read=True));runpy.run_path(str(path),run_name='__main__')
if __name__=='__main__':main()
