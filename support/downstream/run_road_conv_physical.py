"""Authorized RAM-only single-layer test, then restore the verified camera app."""
from pathlib import Path
import json,subprocess,sys,time
ROOT=Path('E:/FPGA_Enhance_Work/road_conv_board_20261027')
CAM=Path('E:/FPGA_Enhance_Work/road_camera_20261027')
def main():
    readback=ROOT/'physical_readback_r1';assert not readback.exists()
    receipt=ROOT/'physical_session_r1.json';assert not receipt.exists()
    # Validate rollback assets before touching the current hardware state.
    p=subprocess.run([sys.executable,str(CAM/'verify_runtime.py')],capture_output=True,text=True)
    assert p.returncode==0 and 'ROAD_CAMERA_RUNTIME_HASHES_PASS' in p.stdout,p.stdout+p.stderr
    state=dict(status='RUNNING_AUTHORIZED_RAM_ONLY_TEST',started_epoch=time.time(),hardware_access=True,sd_written=False,flash_written=False,readback=str(readback))
    receipt.write_text(json.dumps(state,indent=2),encoding='utf-8')
    benchmark=None;restore=None
    try:
        with (ROOT/'physical_session_r1_benchmark.log').open('w',encoding='utf-8') as f:
            benchmark=subprocess.run([sys.executable,str(ROOT/'future_board_test/road_conv_preflight.py'),'--execute','--readback',str(readback)],stdout=f,stderr=subprocess.STDOUT)
        state['benchmark_returncode']=benchmark.returncode
        state['validated']=(readback/'validated.json').exists()
        print('ROAD_CONV_PHYSICAL_BENCHMARK_FINISHED',benchmark.returncode,'validated',state['validated'],flush=True)
    finally:
        print('ROAD_CONV_RESTORING_VERIFIED_CAMERA_RAM_APP',flush=True)
        with (ROOT/'physical_session_r1_restore.log').open('w',encoding='utf-8') as f:
            restore=subprocess.run(['E:/Xilinx/Vitis/2020.2/bin/xsct.bat',str(CAM/'start_camera_live.tcl')],stdout=f,stderr=subprocess.STDOUT)
        log=(ROOT/'physical_session_r1_restore.log').read_text(errors='replace')
        state['camera_restore_returncode']=restore.returncode
        state['camera_restored']='ROAD_CAMERA_LIVE_READY' in log and restore.returncode==0
        state['finished_epoch']=time.time()
        state['status']='BENCHMARK_VALIDATED_CAMERA_RESTORED' if state.get('validated') and state['camera_restored'] else 'NEEDS_REVIEW'
        receipt.write_text(json.dumps(state,indent=2),encoding='utf-8')
        print(json.dumps(state,indent=2),flush=True)
    assert state.get('validated') and benchmark.returncode==0 and state['camera_restored'],'Review benchmark/restore logs'
if __name__=='__main__':main()
