"""Retain spatial features instead of the first underfitting global-average head."""
from pathlib import Path
import os,shutil
from road_roi_spatial_common import *
PREV=BASE.parent/'road_roi_verifier_20261028'
HERE=Path(__file__).resolve().parent

def main():
 ROOT.mkdir(exist_ok=False);assert (PREV/'training_complete.json').exists() and not (PREV/'fresh_evaluation').exists()
 prepared=read(PREV/'prepared.json')
 for n in ['patches.u8','targets.i8','patches.json']:os.link(PREV/n,ROOT/n)
 write(ROOT/'prepared.json',prepared);(ROOT/'source').mkdir()
 protocol=read(PREV/'protocol.json');protocol.update(status='SPATIAL_VERIFIER_FROZEN_BEFORE_GRADIENTS',seed=SEED,epochs=EPOCHS,checkpoints=CHECKPOINTS,model='Same3conv, preserve final16x6x3 features, linear288->32 ReLU ->1;12993 FP32 parameters.',training='Balanced4000/epoch B128 AdamWlr.002 cosine to.0001 wd.0001,80epochs;noAMP/TF32. No data/label changes.',reason='Initial3729-parameter global-average verifier BCE stayed near.69 on training; no new verifier test consumed. Add spatial layout instead of consuming test on an underfitted verifier.',data_reused_sha256=sha(PREV/'prepared.json'))
 write(ROOT/'protocol.json',protocol);write(PREV/'superseded_before_new_test.json',dict(reason='Training BCE near chance; spatial-head continuation selected before any fresh test.',next_root=str(ROOT),no_new_test_inference=True))
 for n in ['road_roi_spatial_common.py','train_road_roi_spatial.py','road_roi_verifier_common.py']:shutil.copy2(HERE/n,ROOT/'source'/n)
 import train_road_roi_verifier as run
 run.ROOT=ROOT;run.SEED=SEED;run.EPOCHS=EPOCHS;run.CHECKPOINTS=CHECKPOINTS;run.PARAMETERS=12993;run.LR_MAX=.002;run.make_model=make_model;run.main()
if __name__=='__main__':main()
