"""Download a single unused confirmation set after freezing zoom selection."""
import shutil
from study_car_zoom_20261030 import ROOT
from road_enhanceadapt_common import read,write,sha

def main():
 selected=read(ROOT/'selected.json');assert selected['qualified']
 import prepare_viewadapt_exclusions as ex
 ex.ROOT=ROOT;ex.SEED=2026103043
 if not (ROOT/'holdout_exclusions.json').exists():ex.main()
 out=ROOT/'confirmation';out.mkdir();(out/'source').mkdir()
 write(out/'protocol.json',dict(status='FIXED_ZOOM_CANDIDATE_BEFORE_NEW_HOLDOUT',fresh_policy=read(ROOT/'protocol.json')['fresh_policy'],
  selection_sha256=sha(ROOT/'selected.json'),weight=selected['chosen']['weight'],
  model_sha256=selected['model_sha256'],hardware_access=False,sd_written=False))
 for n in ['holdout_exclusions.json','holdout_pool.json']:shutil.copy2(ROOT/n,out/n)
 import prepare_viewadapt_holdout as hold
 hold.ROOT=out;hold.RULES=[dict(cohort='low',timeofday='night',images=160,minimum=0,maximum=48),
                         dict(cohort='brighter',timeofday='daytime',images=64,minimum=70,maximum=255)]
 hold.main();shutil.copy2(__file__,ROOT/'source'/__import__('pathlib').Path(__file__).name)

if __name__=='__main__':main()
