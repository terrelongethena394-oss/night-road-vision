"""Sequential pre-board acceptance; stop at failed gate, never consume fresh early."""
from pathlib import Path
import subprocess,time,sys
from train_allview_gamma_20261031 import ROOT
from road_enhanced_detection_common import read,write,sha
HERE=Path(__file__).resolve().parent
def main():
    state=ROOT/'pipeline_status.json';begin=time.monotonic()
    write(state,dict(status='WAITING_FOR_FIXED_TRAINING',hardware_access=False,sd_written=False))
    while not (ROOT/'training_complete.json').exists():
        assert time.monotonic()-begin<4000,'Training completion timeout; keep ABI29.'
        time.sleep(15)
    steps=[('evaluate_allview_gamma_20261031.py','selected.json'),('prove_gammafit_native_20261031.py','c_proof/complete.json'),('prepare_gammafit_fresh_20261031.py',None),('confirm_gammafit_native_20261031.py','confirmation/fresh_result.json')]
    for script,receipt in steps:
        write(state,dict(status='RUNNING',script=script,script_sha256=sha(HERE/script),hardware_access=False,sd_written=False));print('GAMMAFIT_PIPELINE_START',script,flush=True)
        p=subprocess.run([sys.executable,str(HERE/'launch_road_cuda.py'),str(HERE/script)])
        if p.returncode:
            write(state,dict(status='ERROR_KEEP_ABI29',script=script,returncode=p.returncode,hardware_access=False,sd_written=False));raise SystemExit(p.returncode)
        if receipt:
            result=read(ROOT/receipt);accepted=result.get('qualified',result.get('accepted',False))
            if not accepted:
                write(state,dict(status='REJECTED_KEEP_ABI29',stage=script,receipt=receipt,receipt_sha256=sha(ROOT/receipt),new_independent_test_used=(ROOT/'confirmation/fresh_result.json').exists(),hardware_access=False,sd_written=False));print('GAMMAFIT_PIPELINE_REJECTED',script,flush=True);return
    write(state,dict(status='READY_FOR_BOARD_VALIDATION',fresh_result_sha256=sha(ROOT/'confirmation/fresh_result.json'),hardware_access=False,sd_written=False));print('GAMMAFIT_PIPELINE_READY_FOR_BOARD',flush=True)
if __name__=='__main__':main()
