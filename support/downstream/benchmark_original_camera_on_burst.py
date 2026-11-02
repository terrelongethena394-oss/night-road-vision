"""Compare the immutable original camera ELF on the SAME new bit, then restore old live app."""
from pathlib import Path
import json,subprocess,sys,time
ROOT=Path('E:/FPGA_Enhance_Work/road_hybrid_20261027_r1')
CAM=Path('E:/FPGA_Enhance_Work/road_camera_20261027')
def main():
    session=json.loads((ROOT/'full_session_r1.json').read_text());assert session['camera_restored']
    assert json.loads((ROOT/'physical_full_r1/validated.json').read_text())['status']=='FULL_NETWORK_PHYSICAL_NUMERICS_AND_CAMERA_PATH_PASS'
    folder=ROOT/'original_elf_same_bit';folder.mkdir(exist_ok=False)
    text=r'''source {E:/FPGA_Enhance_Work/road_camera_20261027/camera_common.tcl}
set candidate {E:/FPGA_Enhance_Work/road_hybrid_20261027_r1}
set out $candidate/original_elf_same_bit
proc word {a} {
 if {[catch {mrd -value $a} v]} {
  if {![string match {*Invalid context*} $v]} {error $v}
  targets -set -filter {name =~ "ARM*#0"} -timeout 10
  set v [mrd -value $a]
 }
 return [expr {[lindex $v 0]+0}]
}
if {[catch {
 connect -url tcp:127.0.0.1:3121
 targets -set -filter {name =~ "APU*"} -timeout 10
 rst -system
 after 1000
 fpga -file $candidate/display.bit
 targets -set -filter {name =~ "ARM*#0"} -timeout 10
 source $candidate/ps7_init.tcl
 ps7_init
 ps7_post_config
 loadhw -hw $candidate/display.xsa
 dow $root/road_camera.elf
 con
 set ready 0
 for {set i 0} {$i<400} {incr i} {
  after 100
  if {[word 0x13800000]==0x524F4144 && [word 0x13800004]==10} {
   rc_check
   if {[word 0x13800008]==1 && [word 0x138000a0]==0x5640 && [word 0x13800078]==0x7084} {set ready 1;break}
  }
 }
 if {!$ready} {error "Original ELF on new bit initialization failed"}
 dow -data $root/runtime/weights.f32 0x11000000
 catch {con}
 for {set j 0} {$j<4} {incr j} {
  rc_test 02e67bab-27594c1d 1 1378123903 0
  mrd -bin -file $out/timing$j.bin 0x13800000 72
  puts "ROAD_ORIGINAL_ELF_SAME_BIT_TIMING $j"
 }
 mrd -bin -file $out/decoded.f32 0x16300000 56700
 mrd -bin -file $out/head0.f32 0x16400000 44800
 mrd -bin -file $out/head1.f32 0x1642bc00 11200
 mrd -bin -file $out/head2.f32 0x16436b00 2800
 set n [word 0x138000d0]
 mrd -bin -file $out/boxes400.f32 0x16200000 [expr {$n*6}]
 disconnect
 puts "ROAD_ORIGINAL_ELF_SAME_BIT_READBACK_COMPLETE"
} why opts]} {
 puts stderr "ROAD_ORIGINAL_ELF_SAME_BIT_FAILED: $why"
 if {[dict exists $opts -errorinfo]} {puts stderr [dict get $opts -errorinfo]}
 catch {disconnect}
 exit 1
}
exit
'''
    # Derive the frozen input hash, never trust a hand-copied decimal constant.
    from validate_road_hybrid import fnv
    nn=Path('E:/FPGA_Enhance_Work/road_arm_prototype_20261026')
    text=text.replace('1378123903',str(fnv((nn/'cases/02e67bab-27594c1d/input400.u32').read_bytes())))
    script=folder/'benchmark.tcl';script.write_text(text,encoding='ascii');state=dict(started_epoch=time.time(),hardware_access=True,sd_written=False)
    try:
        with (folder/'console.log').open('w') as f:subprocess.run(['E:/Xilinx/Vitis/2020.2/bin/xsct.bat',str(script)],stdout=f,stderr=subprocess.STDOUT)
        log=(folder/'console.log').read_text(errors='replace');assert 'ROAD_ORIGINAL_ELF_SAME_BIT_READBACK_COMPLETE' in log and 'ROAD_ORIGINAL_ELF_SAME_BIT_FAILED' not in log
        import statistics,struct
        gold=nn/'host_r2/02e67bab-27594c1d'
        prior=nn/'board_batch_r2/02e67bab-27594c1d'
        for j,node in enumerate([83,84,85]):assert (folder/f'head{j}.f32').read_bytes()==(prior/f'head{j}.f32').read_bytes()
        for n in ['decoded.f32','boxes400.f32']:assert (folder/n).read_bytes()==(prior/n).read_bytes()
        entries=[]
        for j in range(4):
            m=struct.unpack('<72I',(folder/f'timing{j}.bin').read_bytes());assert m[1]==10 and m[6]==m[35]==m[41]==m[62]==0 and m[70]>0
            entries.append((m[19]+(m[20]<<32))/m[18])
        state.update(status='IMMUTABLE_OLD_ELF_ON_SAME_NEW_BIT_VALIDATED',warmup_seconds=entries[0],runs_seconds=entries[1:],median_seconds=statistics.median(entries[1:]),output_bytes_exact=True)
        (folder/'validated.json').write_text(json.dumps(state,indent=2),encoding='utf-8');print(json.dumps(state,indent=2),flush=True)
    finally:
        with (folder/'restore.log').open('w') as f:subprocess.run(['E:/Xilinx/Vitis/2020.2/bin/xsct.bat',str(CAM/'start_camera_live.tcl')],stdout=f,stderr=subprocess.STDOUT)
        state['camera_restored']='ROAD_CAMERA_LIVE_READY' in (folder/'restore.log').read_text(errors='replace');state['finished_epoch']=time.time()
        (folder/'session.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
        print('ORIGINAL_ELF_BASELINE_DONE_CAMERA_RESTORED',state['camera_restored'],flush=True)
    assert state.get('output_bytes_exact') and state['camera_restored']
if __name__=='__main__':main()
