"""Deployment-view adaptation experiment, isolated from accepted ABI24."""
from pathlib import Path
from road_accuracy_common import BASE,DATA,WEIGHTS,read,write,sha,sensor400,truth,preprocess400,TILES,metrics,fuse,map_tile,NAMES
ROOT=BASE/'road_viewadapt_20261030_r1'
SEED=2026103091
EPOCHS=6
CHECKPOINTS=[2,4,6]

