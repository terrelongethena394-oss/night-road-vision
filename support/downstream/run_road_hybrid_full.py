"""Run the authorized full-network RAM test, always restore the verified old camera."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys,time
from validate_road_hybrid import validate
ROOT=Path('E:/FPGA_Enhance_Work/road_hybrid_20261027_r1')
CAM=Path('E:/FPGA_Enhance_Work/road_camera_20261027')
NN=Path('E:/FPGA_Enhance_Work/road_arm_prototype_20261026')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    assert not (ROOT/'full_session_r1.json').exists()
    # Complete exactly the eight frozen inputs, checking any already-present file.
    for f in json.loads((NN/'export_complete.json').read_text())['fixtures']:
        p=ROOT/'runtime/cases'/f['name']/'input400.u32';gold=NN/'cases'/f['name']/'input400.u32'
        if p.exists():assert sha(p)==sha(gold)
        else:p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(gold,p)
    for name,digest in json.loads((ROOT/'runtime_checksums.json').read_text()).items():assert sha(ROOT/name)==digest,name
    assert sha(ROOT/'road_hybrid.elf')==json.loads((ROOT/'arm_complete.json').read_text())['elf_sha256']
    p=subprocess.run([sys.executable,str(CAM/'verify_runtime.py')],capture_output=True,text=True);assert p.returncode==0 and 'ROAD_CAMERA_RUNTIME_HASHES_PASS' in p.stdout
    state=dict(status='AUTHORIZED_RAM_ONLY_FULL_NETWORK_TEST_RUNNING',started_epoch=time.time(),hardware_access=True,sd_written=False,flash_written=False)
    receipt=ROOT/'full_session_r1.json';receipt.write_text(json.dumps(state,indent=2),encoding='utf-8')
    try:
        with (ROOT/'full_test_console.log').open('w') as f:p=subprocess.run(['E:/Xilinx/Vitis/2020.2/bin/xsct.bat',str(ROOT/'test_full_ram.tcl')],stdout=f,stderr=subprocess.STDOUT)
        log=(ROOT/'full_test_console.log').read_text(errors='replace');assert 'ROAD_HYBRID_FULL_TEST_READBACK_COMPLETE' in log and 'ROAD_HYBRID_FULL_TEST_FAILED' not in log
        shutil.copy2(ROOT/'test_context.json',ROOT/'physical_full_r1/context.json')
        result=validate(ROOT/'physical_full_r1');state['numerical_validation']=result['status'];state['first_photo_end_to_end_speedup']=result['first_photo_end_to_end_speedup'];state['performance_gate_passed']=result['performance_gate_passed']
        print('ROAD_HYBRID_FULL_PHYSICAL_VALIDATED',state['first_photo_end_to_end_speedup'],flush=True)
    except Exception as e:
        state['failure']=repr(e);raise
    finally:
        print('ROAD_HYBRID_RESTORING_VERIFIED_OLD_CAMERA',flush=True)
        with (ROOT/'restore_after_full.log').open('w') as f:p=subprocess.run(['E:/Xilinx/Vitis/2020.2/bin/xsct.bat',str(CAM/'start_camera_live.tcl')],stdout=f,stderr=subprocess.STDOUT)
        state['camera_restored']='ROAD_CAMERA_LIVE_READY' in (ROOT/'restore_after_full.log').read_text(errors='replace')
        state['status']='FULL_NUMERICS_VALIDATED_OLD_CAMERA_RESTORED' if state.get('numerical_validation') and state['camera_restored'] else 'NEEDS_REVIEW'
        state['finished_epoch']=time.time();receipt.write_text(json.dumps(state,indent=2),encoding='utf-8');print(json.dumps(state,indent=2),flush=True)
    assert state['camera_restored']
if __name__=='__main__':main()
