"""One qualified allview expert -> frozen unused304, never test-driven reselection."""
from pathlib import Path
import shutil
from train_allview_gamma_20261031 import ROOT,SEED
from road_enhanced_detection_common import BASE,read,write,sha
def main():
    assert read(ROOT/'selected.json')['qualified'] and read(ROOT/'c_proof/complete.json')['qualified']
    import prepare_viewadapt_exclusions as ex
    ex.ROOT=ROOT;ex.SEED=SEED+7;ex.main()
    ledger=read(ROOT/'holdout_exclusions.json');known=read(ROOT/'development_manifest.json')+read(BASE/'road_car_balanced_20261030_r1/confirmation/fresh/manifest.json')
    assert {r['group'] for r in known}<=set(ledger['groups']) and {r['image_sha256'] for r in known}<=set(ledger['image_hashes'])
    out=ROOT/'confirmation';out.mkdir();(out/'source').mkdir()
    for n in ['holdout_exclusions.json','holdout_pool.json']:shutil.copy2(ROOT/n,out/n)
    write(out/'protocol.json',dict(status='FROZEN_BEFORE_UNUSED_SELECTION',selection_sha256=sha(ROOT/'selected.json'),c_proof_sha256=sha(ROOT/'c_proof/complete.json'),
      fresh_policy='Exactly one frozen model, unused240night meanY<=48 and64day meanY>=70. Exclude all prior exposed source prefixgroups, exact hashes and manifestnames. Original annotations. All detector inputs, inference and postprocessing actualC. Candidate vs originalRAW7 and strongest matchedRAW7:AP+.5pp,P>=,R+.5pp,FP<=,F1+.5pp. Samecandidate ENHvsRAW AP+.2pp,TP>=,FP<=. Paired2000 image-bootstrap99%APgainCI lower>0 vsbothRAWcontrols;no holdout-driven replacement. Bright64 originalCB4RAW predictions copied byteexact inallconditions.',hardware_access=False,sd_written=False))
    import prepare_viewadapt_holdout as hold
    hold.ROOT=out;hold.RULES=[dict(cohort='low',timeofday='night',images=240,minimum=0,maximum=48),dict(cohort='brighter',timeofday='daytime',images=64,minimum=70,maximum=255)];hold.main()
    shutil.copy2(__file__,ROOT/'source'/Path(__file__).name)
if __name__=='__main__':main()
