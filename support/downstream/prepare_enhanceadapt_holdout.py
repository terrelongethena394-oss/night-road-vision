"""Expose no new detector predictions before a development candidate passes."""
import shutil,sys
from road_enhanceadapt_common import *

def main():
 import prepare_viewadapt_exclusions as ex
 ex.ROOT=ROOT;ex.SEED=SEED
 if not (ROOT/'holdout_exclusions.json').exists():ex.main()
 if '--ledger-only' in sys.argv:return
 selected=read(ROOT/'delivery_selection.json');assert selected['qualified'],'No development-qualified candidate; do not consume a fresh test'
 out=ROOT/'confirmation';out.mkdir();(out/'source').mkdir()
 policy=read(ROOT/'protocol.json')['fresh_policy'] if selected['input_mode']=='enh' else read(ROOT/'secondary_protocol.json')['fresh']
 write(out/'protocol.json',dict(status='ONE_CANDIDATE_FIXED_BEFORE_FRESH_DATA_OR_PREDICTIONS',fresh_policy=policy,
  delivery_selection_sha256=sha(ROOT/'delivery_selection.json'),input_mode=selected['input_mode'],
  checkpoint_sha256=selected['chosen']['sha256'],hardware_access=False,sd_written=False))
 for name in ['holdout_exclusions.json','holdout_pool.json']:shutil.copy2(ROOT/name,out/name)
 import prepare_viewadapt_holdout as hold
 hold.ROOT=out;hold.RULES=[dict(cohort='low',timeofday='night',images=160,minimum=0,maximum=48),
                          dict(cohort='brighter',timeofday='daytime',images=64,minimum=70,maximum=255)]
 hold.main()
 shutil.copy2(Path(__file__),ROOT/'source'/Path(__file__).name)

if __name__=='__main__':main()
