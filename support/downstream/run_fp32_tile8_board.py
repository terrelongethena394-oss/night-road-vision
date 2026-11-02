"""Serialize hardware experiments; R2 can start only after R1 restored ABI15."""
import time
from pathlib import Path
from prepare_fp32_tile8 import ROOT,BASE
import run_fp32_cpu_pack_board as run

def main():
 previous=BASE/'road_fp32_cpu_pack_20261028_r1/session.json';start=time.monotonic()
 while not previous.exists():
  if time.monotonic()-start>2400:raise TimeoutError('Previous experiment has not safely completed')
  time.sleep(2)
 s=run.read(previous);assert s['status']=='NOT_PROMOTED_PREVIOUS_ABI15_RESTORED' and s['restored'],'Do not replace an un-restored or successfully promoted previous run'
 run.ROOT=ROOT;run.APP=ROOT/'firmware';run.main()
if __name__=='__main__':main()
