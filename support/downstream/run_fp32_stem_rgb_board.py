"""Serialize R5 after R4 and never replace a better validated candidate."""
from prepare_fp32_stem_rgb import ROOT
import run_fp32_cpu_pack_board as run
def main():
    prior=run.read(run.BASE/'road_fp32_stem_reuse_20261028_r4/session.json')
    assert prior['status']=='NOT_PROMOTED_PREVIOUS_ABI15_RESTORED',prior
    run.ROOT=ROOT;run.APP=ROOT/'firmware';run.main()
if __name__=='__main__':main()
