"""Freeze a new routed system hypothesis; old failures remain failures."""
import shutil
from road_brightness_route_common import *

def main():
 assert not ROOT.exists();ROOT.mkdir();(ROOT/'source').mkdir()
 failed=read(ADAPT/'fresh_result.json');assert not failed['accepted'] and read(ADAPT/'c_development_result.json')['qualified']
 protocol=dict(status='NEW_ROUTED_SYSTEM_PROTOCOL_FROZEN_BEFORE_NEW_TEST',reason='Unconditional new model failed complete unused224 confirmation, including brighter truck/bus degradation and inconclusive car AP intervals. Preserve that failure. New hypothesis is specifically low-brightness truck/bus false-positive reduction with quality retention; it is NOT a claim of significant car AP improvement.',route='Unenhanced global400 meanY=(54R+183G+19B)/256. Mean<=48: fixed trained epoch4 model plus truck/bus odds gains1.75/1.1. Mean>48: exact accepted original model/fusion. Decision uses image only, no ground truth/prediction filtering. One model per shot, four forwards, no ensembling.',threshold=GATE_MEAN,weights=dict(bright_stable='4c15d4b3ad9765f96204d0caa767e024f414149165150c94ed1701a48c4d47d1',dark_adapted=read(ADAPT/'export/complete.json')['weights_sha256']),gains=GAINS,development='Previous unused224 results are now explicitly reused development. They no longer independently validate this new routing rule.',fresh_policy='New unused320 low (night-labelled mean<=48) plus96 brighter(day-labelled mean>=70), excluding every recorded prior training/evaluation/screened prefix/hash. Low primary: truck+bus FP reduce>=25%, TP retain>=90%, carAP/P/R not worse by>.5pp, fourclassAP not worse by>.2pp, paired-image99.5% lower CI for truck+bus precision gain>0 and FP reduction>0. Brighter outputs must be byte-for-byte equal to stable model. CarAP positive-gain CI descriptive; no significant-carAP claim unless supported. One fixed test, no parameter adjustment using new results.',uncertainty=dict(replicates=2000,confidence=.995,seed=SEED+100,unit='paired unique image/prefix group'),hardware_access=False,sd_written=False)
 write(ROOT/'protocol.json',protocol)
 # Check the route against now-reused224; do not call this independent proof.
 source_manifest=read(ADAPT/'fresh/manifest.json');old=read(ADAPT/'fresh_evaluation/baseline/native/candidate_predictions.json');new=read(ADAPT/'fresh_evaluation/candidate/calibrated_predictions.json')
 routed=[b if m['mean_y']<=GATE_MEAN else a for a,b,m in zip(old,new,source_manifest)]
 lowids=[i for i,m in enumerate(source_manifest) if m['cohort']=='low'];brids=[i for i,m in enumerate(source_manifest) if m['cohort']=='brighter'];before=metrics([old[i] for i in lowids]);after=metrics([routed[i] for i in lowids]);gg=gates(before,after)
 assert all(gg.values()) and all(routed[i]==old[i] for i in brids)
 write(ROOT/'development.json',dict(status='REUSED224_ROUTING_DEVELOPMENT_PASS_NOT_INDEPENDENT',low_gates=gg,low_baseline=before,low_candidate=after,brighter_all96_or64_exact=len(brids),old_failed_test_sha256=sha(ADAPT/'fresh_result.json')))
 for name in ['road_brightness_route_common.py','prepare_road_brightness_route.py','prepare_viewadapt_exclusions.py','prepare_viewadapt_holdout.py','confirm_road_brightness_route.py']:
  p=Path(__file__).with_name(name)
  if p.exists():shutil.copy2(p,ROOT/'source'/name)
 import prepare_viewadapt_exclusions as exclusions
 exclusions.ROOT=ROOT;exclusions.SEED=SEED;exclusions.main()
 import prepare_viewadapt_holdout as holdout
 holdout.ROOT=ROOT;holdout.RULES=[dict(cohort='low',timeofday='night',images=320,minimum=0,maximum=48),dict(cohort='brighter',timeofday='daytime',images=96,minimum=70,maximum=255)];holdout.main()

if __name__=='__main__':main()
