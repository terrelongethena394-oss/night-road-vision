"""Run the R4 acceptance controller after the prior board run has restored ABI15."""
from prepare_fp32_stem_reuse import ROOT
import run_fp32_cpu_pack_board as run
def main():
    prior=run.read(run.BASE/'road_fp32_microkernel_20261028_r3/session.json')
    assert prior['status']=='NOT_PROMOTED_PREVIOUS_ABI15_RESTORED',prior
    run.ROOT=ROOT;run.APP=ROOT/'firmware';run.main()
if __name__=='__main__':main()
