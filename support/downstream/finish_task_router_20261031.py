import time,subprocess,sys
from pathlib import Path
from road_task_router_common import ROOT,write,sha
def main():
    begin=time.monotonic();p=ROOT/'router_pipeline_status.json';write(p,dict(status='WAITING_FOR_ORIGINAL_TRAIN_COUNTERFACTUALS',hardware_access=False,sd_written=False))
    while not (ROOT/'prepared.json').exists():
        assert time.monotonic()-begin<1400;time.sleep(15)
    script=Path(__file__).with_name('train_evaluate_task_router_20261031.py');write(p,dict(status='RUNNING_TRAIN_AND_DEVELOPMENT',script_sha256=sha(script),hardware_access=False,sd_written=False));r=subprocess.run([sys.executable,str(script)]);assert r.returncode==0
    from road_task_router_common import read
    s=read(ROOT/'selected.json');write(p,dict(status='REQUIRES_C_AND_UNUSED_CONFIRMATION' if s['qualified'] else 'REJECTED_KEEP_ABI29',selection_sha256=sha(ROOT/'selected.json'),hardware_access=False,sd_written=False))
if __name__=='__main__':main()
