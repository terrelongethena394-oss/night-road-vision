import subprocess,sys,time
from pathlib import Path
from car_roi_delivery_common import *
def main():
    here=Path(__file__).resolve().parent;begin=time.monotonic();state=ROOT/'pipeline_status.json';write(state,dict(status='WAITING_FOR_C_PROOF',hardware_access=False,sd_written=False))
    while not (ROOT/'c_proof/complete.json').exists():
        assert time.monotonic()-begin<1500,'C proof did not complete; keepABI29';time.sleep(10)
    assert read(ROOT/'c_proof/complete.json')['qualified']
    for script in ['prepare_car_roi_delivery_fresh_20261031.py','confirm_car_roi_delivery_20261031.py']:
        write(state,dict(status='RUNNING',script=script,script_sha256=sha(here/script),hardware_access=False,sd_written=False));print('RAW_ROI_PIPELINE_START',script,flush=True);p=subprocess.run([sys.executable,str(here/script)]);assert p.returncode==0,(script,p.returncode)
    result=read(ROOT/'confirmation/fresh_result.json');write(state,dict(status='READY_FOR_BOARD_VALIDATION' if result['accepted'] else 'REJECTED_KEEP_ABI29',fresh_result_sha256=sha(ROOT/'confirmation/fresh_result.json'),hardware_access=False,sd_written=False));print('RAW_ROI_PIPELINE_CONFIRMATION_DONE',result['accepted'],flush=True)
if __name__=='__main__':main()
