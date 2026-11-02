"""One new confirmation set for the user-selected balanced objective."""
import shutil
from pathlib import Path
from study_balanced_car_20261030 import ROOT
from car_box_refine_common import read,write,sha

def main():
 selected=read(ROOT/'selected.json');assert selected['qualified']
 import prepare_viewadapt_exclusions as ex
 ex.ROOT=ROOT;ex.SEED=2026103081;ex.main()
 # Ensure nested previous confirmation data is explicitly excluded.
 ledger=read(ROOT/'holdout_exclusions.json')
 previous=read(ROOT.parent/'road_car_zoom_20261030_r1/confirmation/fresh/manifest.json')
 assert {r['group'] for r in previous}<=set(ledger['groups'])
 assert {r['image_sha256'] for r in previous}<=set(ledger['image_hashes'])
 out=ROOT/'confirmation';out.mkdir();(out/'source').mkdir()
 write(out/'protocol.json',dict(status='ONE_BALANCED_CANDIDATE_FIXED_BEFORE_FRESH_SELECTION',
  fresh_policy=read(ROOT/'protocol.json')['fresh_policy'],selection_sha256=sha(ROOT/'selected.json'),hardware_access=False,sd_written=False))
 for n in ['holdout_exclusions.json','holdout_pool.json']:shutil.copy2(ROOT/n,out/n)
 import prepare_viewadapt_holdout as hold
 hold.ROOT=out;hold.RULES=[dict(cohort='low',timeofday='night',images=240,minimum=0,maximum=48),dict(cohort='brighter',timeofday='daytime',images=64,minimum=70,maximum=255)]
 hold.main();shutil.copy2(__file__,ROOT/'source'/Path(__file__).name)

if __name__=='__main__':main()
