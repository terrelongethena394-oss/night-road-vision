"""Freeze exclusion ledger only;no new photos downloaded or evaluated."""
import shutil
from road_enhanced_detection_common import *
def main():
    import prepare_viewadapt_exclusions as ex
    ex.ROOT=ROOT;ex.SEED=2026103131;ex.main()
    ledger=read(ROOT/'holdout_exclusions.json');dev=read(ROOT/'development_manifest.json');prior=read(BASE/'road_car_balanced_20261030_r1/confirmation/fresh/manifest.json')
    assert {r['group'] for r in dev+prior}<=set(ledger['groups'])
    assert {r['image_sha256'] for r in dev+prior}<=set(ledger['image_hashes'])
    write(ROOT/'unused_pool_proof.json',dict(status='PRIOR304_AND_CURRENT640_EXPLICITLY_EXCLUDED',no_new_images_downloaded=True,no_new_predictions=True,ledger_sha256=sha(ROOT/'holdout_exclusions.json'),development_sha256=sha(ROOT/'development_manifest.json')))
    shutil.copy2(__file__,ROOT/'source'/Path(__file__).name)
if __name__=='__main__':main()
