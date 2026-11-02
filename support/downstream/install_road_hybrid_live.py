"""Install gated hybrid RAM app, validate live data; restore original app on failure."""
from pathlib import Path
import hashlib,importlib.util,json,os,shutil,subprocess,sys,time
ROOT=Path('E:/FPGA_Enhance_Work/road_hybrid_20261027_r1')
CAM=Path('E:/FPGA_Enhance_Work/road_camera_20261027')
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    assert not (ROOT/'live_session_r1.json').exists()
    full=json.loads((ROOT/'physical_full_r1/validated.json').read_text());assert full['performance_gate_passed']
    old=json.loads((ROOT/'original_elf_same_bit/validated.json').read_text());assert old['output_bytes_exact']
    assert json.loads((ROOT/'original_elf_same_bit/session.json').read_text())['camera_restored']
    proof=json.loads((ROOT/'arm_complete.json').read_text());assert sha(ROOT/'road_hybrid.elf')==proof['elf_sha256']
    assert old['median_seconds']/full['timing']['hybrid']['median_total_seconds']>1.03
    start=(CAM/'start_camera_live.tcl').read_text().replace('==10','==11').replace('$root/road_camera.elf','$root/road_hybrid.elf').replace('ROAD_CAMERA_LIVE_READY','ROAD_HYBRID_CAMERA_LIVE_READY')
    start=start.replace('mwr 0x1380000c 3','mwr 0x13800120 1\n mwr 0x1380000c 3')
    extra=r''' set f [open $root/live_samples_times.txt w]
 for {set j 0} {$j<3} {incr j} {
  if {$j>0} {after 5000}
  puts $f "$j [clock milliseconds]"
  mrd -bin -file $root/live_sample$j.bin 0x13800000 80
 }
 close $f
 rc_pause
 set completed [word 0x138000cc]
 rc_packet $root/live_snapshot_01 live camera 0
 mrd -bin -file $root/live_snapshot_01/mailbox80.bin 0x13800000 80
 mwr 0x1380000c 3
 set resumed 0
 for {set i 0} {$i<600} {incr i} {
  after 100
  rc_check
  if {[word 0x138000cc]>$completed} {set resumed 1;break}
 }
 if {!$resumed} {error "Hybrid camera did not resume after readback"}
'''
    assert start.count('\n disconnect\n')==1;start=start.replace('\n disconnect\n','\n'+extra+' disconnect\n')
    (ROOT/'start_hybrid_live.tcl').write_text(start,encoding='ascii')
    validator=(HERE/'validate_road_camera.py').read_text()
    validator=validator.replace('from build_road_camera import ROOT,NN,read,write,sha','from road_arm_common import ROOT as NN,read,write,sha\nROOT=Path("E:/FPGA_Enhance_Work/road_hybrid_20261027_r1")')
    validator=validator.replace('m[1]==10','m[1]==11').replace("ROOT/'road_camera.elf'","ROOT/'road_hybrid.elf'")
    validator=validator.replace('ARM Cortex-A9; cooperativepreview is not detection acceleration','ARM Cortex-A9 plus measured selected 3x3 FPGA offload; preview Hz remains separate from detection Hz')
    (ROOT/'validate_live_v11.py').write_text(validator,encoding='utf-8')
    shutil.copy2(CAM/'host/render.exe',ROOT/'host/render.exe')
    offline=dict(status='FULL_FIXED_INPUT_NETWORK_PHYSICAL_GATES_PASSED_PENDING_LIVE',elf_sha256=proof['elf_sha256'],bit_sha256=proof['bit_sha256'],weights_sha256=sha(ROOT/'runtime/weights.f32'),selected_layers=proof['selected_layers'])
    (ROOT/'offline_complete.json').write_text(json.dumps(offline,indent=2),encoding='utf-8')
    files=[p for p in (ROOT/'runtime').rglob('*') if p.is_file()]+[ROOT/n for n in ['road_hybrid.elf','display.bit','display.xsa','ps7_init.tcl','camera_common.tcl','start_hybrid_live.tcl','validate_live_v11.py']]
    manifest={p.relative_to(ROOT).as_posix():sha(p) for p in files};(ROOT/'runtime_checksums.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    for name,digest in manifest.items():assert sha(ROOT/name)==digest
    state=dict(status='INSTALLING_AUTHORIZED_HYBRID_CAMERA_RAM_ONLY',started_epoch=time.time(),hardware_access=True,sd_written=False,flash_written=False,elf_sha256=proof['elf_sha256'],bit_sha256=proof['bit_sha256'])
    receipt=ROOT/'live_session_r1.json';receipt.write_text(json.dumps(state,indent=2),encoding='utf-8')
    success=False
    try:
        with (ROOT/'live_install_console.log').open('w') as f:subprocess.run(['E:/Xilinx/Vitis/2020.2/bin/xsct.bat',str(ROOT/'start_hybrid_live.tcl')],stdout=f,stderr=subprocess.STDOUT)
        log=(ROOT/'live_install_console.log').read_text(errors='replace');assert 'ROAD_HYBRID_CAMERA_LIVE_READY' in log and 'ROAD_CAMERA_FAILED' not in log
        spec=importlib.util.spec_from_file_location('hybrid_live_validator',ROOT/'validate_live_v11.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        verdict=module.validate(ROOT/'live_snapshot_01')
        assert verdict['neural_compute'].startswith('ARM Cortex-A9 plus')
        import struct
        samples=[struct.unpack('<80I',(ROOT/f'live_sample{j}.bin').read_bytes()) for j in range(3)]
        times=[int(line.split()[1]) for line in (ROOT/'live_samples_times.txt').read_text().splitlines()]
        assert all(m[0]==0x524F4144 and m[1]==11 and m[6]==m[35]==m[41]==m[74]==0 and m[72]==1 and m[77]==0x5041434B for m in samples)
        elapsed=(times[-1]-times[0])/1000;preview=(samples[-1][39]-samples[0][39])/elapsed;detect=(samples[-1][51]-samples[0][51])/elapsed
        assert preview>0 and detect>0
        state.update(status='HYBRID_CAMERA_LIVE_VALIDATED_AND_LEFT_RUNNING',preview_hz=preview,detection_updates_hz=detect,active_detection_seconds=verdict['active_detection_seconds'],live_packet=str(ROOT/'live_snapshot_01'),selected_layers=proof['selected_layers'],resumed_after_packet=True)
        success=True;print('ROAD_HYBRID_CAMERA_LIVE_PHYSICAL_PASS',json.dumps(state,indent=2),flush=True)
    except Exception as e:state['failure']=repr(e);raise
    finally:
        if not success:
            with (ROOT/'restore_after_live_failure.log').open('w') as f:subprocess.run(['E:/Xilinx/Vitis/2020.2/bin/xsct.bat',str(CAM/'start_camera_live.tcl')],stdout=f,stderr=subprocess.STDOUT)
            state['old_camera_restored']='ROAD_CAMERA_LIVE_READY' in (ROOT/'restore_after_live_failure.log').read_text(errors='replace');state['status']='LIVE_CANDIDATE_REJECTED_REVIEW_REQUIRED'
        state['finished_epoch']=time.time();receipt.write_text(json.dumps(state,indent=2),encoding='utf-8')
    assert success
if __name__=='__main__':main()
