"""Temporary authorized RAM test. Restore current FP32 hybrid even on failed validation."""
from pathlib import Path
import hashlib,json,subprocess,sys,time
ROOT=Path('E:/FPGA_Enhance_Work/road_qconv_app_20261027')
OLD=Path('E:/FPGA_Enhance_Work/road_hybrid_20261027_r1')
XSCT='E:/Xilinx/Vitis/2020.2/bin/xsct.bat'
def main():
    checks=json.loads((ROOT/'experiment_checksums.json').read_text())
    for n,h in checks.items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,n
    p=subprocess.run([sys.executable,str(OLD/'start_hybrid_ram.py'),'--verify-only'],capture_output=True,text=True);assert p.returncode==0 and 'ROAD_HYBRID_RUNTIME_HASHES_PASS' in p.stdout
    scan=subprocess.run([XSCT,str(ROOT/'scan_only.tcl')],capture_output=True,text=True,timeout=50);(ROOT/'scan_only.log').write_text(scan.stdout+scan.stderr)
    assert scan.returncode==0 and 'ROAD_QCONV_SCAN_READY' in scan.stdout,'No confirmed JTAG target: current running program not changed'
    receipt=ROOT/'experiment_session_r1.json';assert not receipt.exists()
    state=dict(status='TEMPORARY_RAM_EXPERIMENT_RUNNING',started_epoch=time.time(),default_promotion_allowed=False,sd_written=False,flash_written=False)
    receipt.write_text(json.dumps(state,indent=2));failure=None
    try:
        with (ROOT/'test_console.log').open('w') as f:p=subprocess.run([XSCT,str(ROOT/'test_ram.tcl')],stdout=f,stderr=subprocess.STDOUT,timeout=1200)
        text=(ROOT/'test_console.log').read_text(errors='replace');assert p.returncode==0 and 'ROAD_QCONV_FULL_TEST_READBACK_COMPLETE' in text and 'ROAD_QCONV_FULL_TEST_FAILED' not in text
        p=subprocess.run([sys.executable,str(ROOT/'validate_physical.py')],capture_output=True,text=True);(ROOT/'physical_validation.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
        state['numerics_validated']=True
    except Exception as e:failure=e;state['failure']=repr(e)
    finally:
        print('ROAD_QCONV_RESTORING_CURRENT_FP32_HYBRID',flush=True)
        with (ROOT/'restore_hybrid.log').open('w') as f:p=subprocess.run([sys.executable,str(OLD/'start_hybrid_ram.py')],stdout=f,stderr=subprocess.STDOUT,timeout=180)
        state['fp32_hybrid_restored']=p.returncode==0 and 'ROAD_HYBRID_CAMERA_LIVE_READY' in (ROOT/'restore_hybrid.log').read_text(errors='replace')
        state['finished_epoch']=time.time();state['status']='EXPERIMENT_COMPLETE_FP32_HYBRID_RESTORED' if state.get('numerics_validated') and state['fp32_hybrid_restored'] else 'EXPERIMENT_REQUIRES_REVIEW'
        receipt.write_text(json.dumps(state,indent=2));print(json.dumps(state,indent=2),flush=True)
    assert state['fp32_hybrid_restored'],'Restore must be repaired before any further experiment'
    if failure:raise failure
if __name__=='__main__':main()
