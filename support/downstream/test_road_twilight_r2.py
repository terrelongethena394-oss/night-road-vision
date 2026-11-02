from road_twilight_r2_common import ROOT
import test_road_twilight as run
run.ROOT=ROOT
if __name__=='__main__':
 import time
 started=time.monotonic()
 while not (ROOT/'prepare_complete.json').exists():
  if time.monotonic()-started>1800:raise TimeoutError('R2 data not ready')
  time.sleep(2)
 run.main()
