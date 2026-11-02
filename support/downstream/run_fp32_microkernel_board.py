"""Repair interrupted download with validated ABI15, then test R3 serially."""
import subprocess,sys
from prepare_fp32_microkernel import ROOT
import run_fp32_cpu_pack_board as run
def main():
 assert not (ROOT/'session.json').exists()
 repaired=False
 for attempt in range(2):
  p=subprocess.run([sys.executable,str(run.CURRENT/'experiment.py'),'start'],capture_output=True,text=True,timeout=500);text=p.stdout+p.stderr;(ROOT/f'pretest_repair{attempt}.log').write_text(text,encoding='utf-8')
  if p.returncode==0 and 'ROAD_DETAIL_EXPERIMENT_LIVE_READY' in text:repaired=True;break
  if 'Camera app error 220' not in text:break
 assert repaired,'Do not continue until interrupted board has been restored'
 run.ROOT=ROOT;run.APP=ROOT/'firmware';run.main()
if __name__=='__main__':main()
