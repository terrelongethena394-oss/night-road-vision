from pathlib import Path
import shutil,tkinter
from build_road_camera import ROOT,NN,read,write,sha
from build_road_arm_probe import fnv

def main():
    o=read(ROOT/'offline_complete.json');assert sha(ROOT/'road_camera.elf')==o['elf_sha256']
    runtime=ROOT/'runtime';runtime.mkdir();shutil.copy2(NN/'weights.f32',runtime/'weights.f32');shutil.copy2(NN/'YOLOv5_LICENSE',ROOT/'YOLOv5_LICENSE')
    cases=read(NN/'export_complete.json')['fixtures'];selected=[cases[0],cases[3],cases[6]];hashes={}
    for f in selected:
        d=runtime/'cases'/f['name'];d.mkdir(parents=True);p=NN/'cases'/f['name']/'input400.u32';shutil.copy2(p,d/'input400.u32');hashes[f['name']]=fnv(p.read_bytes())
    common=r'''set root [file dirname [file normalize [info script]]]
proc word {a} {return [expr {[lindex [mrd -value $a] 0]+0}]}
proc rc_check {} {
 if {[word 0x13800000]!=0x524F4144 || [word 0x13800004]!=10} {error "Wrong camera app ABI"}
 if {[word 0x13800008]==4 || [word 0x13800018]!=0} {error "Camera app error [word 0x13800018]"}
}
proc rc_pause {} {
 mwr 0x1380000c 1
 for {set i 0} {$i<300} {incr i} {
  after 100
  rc_check
  if {[word 0x13800008]==3 && [word 0x138000e4]==1} {return}
 }
 error "Pause timeout"
}
proc rc_test {id photo expected trace} {
 global root
 set state [word 0x13800008]
 if {$state==3} {
  # Only injected-test idle pauses may be resumed for another injected input.
  if {[word 0x138000e0]!=1} {error "Do not overwrite an in-flight camera inference input"}
  mwr 0x1380000c 0
  after 300
 }
 if {[word 0x13800008] ni {1 5}} {error "Injected test requires idle app"}
 set wanted [expr {[word 0x13800010]+1}]
 dow -data $root/runtime/cases/$id/input400.u32 0x10000000
 catch {con}
 mwr 0x1380006c $expected
 mwr 0x138000b8 $photo
 mwr 0x13800070 $trace
 mwr 0x1380000c 2
 for {set i 0} {$i<3000} {incr i} {
  after 100
  rc_check
  if {[word 0x13800008]==5 && [word 0x13800010]==$wanted} {rc_pause;return}
 }
 error "Injected inference timeout"
}
proc rc_packet {out kind fixture trace} {
 global root
 rc_check
 if {[word 0x13800008]!=3 || [word 0x138000e4]!=1} {error "Readback requires acknowledged pause"}
 if {[file exists $out]} {error "Preserve earlier camera packet"}
 set n [word 0x138000d0]
 set frame [word 0x13800080]
 set capture [word 0x138000f4]
 if {$n<0 || $n>300 || $capture<0 || $capture>1 || ($frame!=0x02000000 && $frame!=0x02119400)} {error "Invalid packet metadata"}
 file mkdir $out
 mrd -bin -file $out/mailbox.bin 0x13800000 72
 mrd -bin -file $out/ui.u32 0x16500000 11
 mrd -bin -file $out/live400.u32 0x16000000 96000
 mrd -bin -file $out/result400.u32 0x16100000 96000
 mrd -bin -file $out/capture_source.bgr [expr {0x06000000+$capture*1152000}] 288000
 mrd -bin -file $out/decoded.f32 0x16300000 56700
 mrd -bin -file $out/head0.f32 0x16400000 44800
 mrd -bin -file $out/head1.f32 0x1642bc00 11200
 mrd -bin -file $out/head2.f32 0x16436b00 2800
 if {$n>0} {mrd -bin -file $out/boxes400.f32 0x16200000 [expr {$n*6}]} else {close [open $out/boxes400.f32 w]}
 mrd -bin -file $out/frame.bgr $frame 288000
 mrd -bin -file $out/vdma_regs.bin 0x43000000 12
 if {$trace} {
  set bytes [word 0x13800038]
  if {$bytes!=19844800} {error "Unexpected FP32 all-layer trace length"}
  mrd -bin -file $out/all_layers.f32 0x14000000 [expr {$bytes/4}]
 }
 set f [open $out/context.txt w]
 puts $f "source=physical_camera_cooperative_paused_readback"
 puts $f "kind=$kind"
 puts $f "fixture=$fixture"
 puts $f "elf_sha256=@ELF@"
 puts $f "weights_sha256=@WEIGHT@"
 puts $f "bit_sha256=@BIT@"
 close $f
 puts "ROAD_CAMERA_PACKET_COMPLETE $out result_boxes=$n"
}
'''
    for k,v in dict(ELF=o['elf_sha256'],WEIGHT=o['weights_sha256'],BIT=o['bit_sha256']).items():common=common.replace('@'+k+'@',v)
    install=r'''source [file join [file dirname [file normalize [info script]]] camera_common.tcl]
set out $root/board_fixed_first
if {$argc>=1} {set out [file normalize [lindex $argv 0]]}
if {[file exists $out]} {error "Preserve first readback"}
if {[catch {
 connect -url tcp:127.0.0.1:3121
 puts [targets]
 targets -set -filter {name =~ "APU*"} -timeout 10
 rst -system
 after 1000
 fpga -file $root/display.bit
 targets -set -filter {name =~ "ARM*#0"} -timeout 10
 source $root/ps7_init.tcl
 ps7_init
 ps7_post_config
 loadhw -hw $root/display.xsa
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
 if {!$ready} {error "Camera/LCD init timed out"}
 puts "ROAD_CAMERA_STAGE sensor_and_preview_ready"
 dow -data $root/runtime/weights.f32 0x11000000
 catch {con}
 rc_test {@FIRST@} 1 @HASH@ 1
 rc_packet $out fixed {@FIRST@} 1
 disconnect
 puts "ROAD_CAMERA_FIRST_FIXED_READBACK_COMPLETE"
} why opts]} {
 puts stderr "ROAD_CAMERA_FAILED $why"
 if {[dict exists $opts -errorinfo]} {puts stderr [dict get $opts -errorinfo]}
 catch {disconnect}
 exit 1
}
exit 0
'''.replace('@FIRST@',selected[0]['name']).replace('@HASH@',str(hashes[selected[0]['name']]))
    tests=r'''source [file join [file dirname [file normalize [info script]]] camera_common.tcl]
if {[catch {
 connect -url tcp:127.0.0.1:3121
 targets -set -filter {name =~ "ARM*#0"} -timeout 10
 loadhw -hw $root/display.xsa
 @TESTS@
 mwr 0x13800070 0
 mwr 0x1380006c 0
 mwr 0x1380000c 3
 set before [word 0x138000cc]
 for {set i 0} {$i<600} {incr i} {
  after 100
  rc_check
  if {[word 0x138000cc]>=$before+2 && [word 0x138000e0]==0} {break}
 }
 if {[word 0x138000cc]<$before+2} {error "Live camera detections did not advance"}
 disconnect
 puts "ROAD_CAMERA_EXTRA_TESTS_AND_LIVE_STARTED"
} why opts]} {
 puts stderr "ROAD_CAMERA_FAILED $why"
 if {[dict exists $opts -errorinfo]} {puts stderr [dict get $opts -errorinfo]}
 catch {disconnect}
 exit 1
}
exit 0
'''
    jobs=[]
    for at,f in enumerate(selected[1:],2):jobs.append(f'rc_test {{{f["name"]}}} {at} {hashes[f["name"]]} 0\n rc_packet $root/board_fixed_{at:02d} fixed {{{f["name"]}}} 0')
    tests=tests.replace('@TESTS@','\n '.join(jobs))
    snapshot=r'''source [file join [file dirname [file normalize [info script]]] camera_common.tcl]
if {$argc!=1} {error "Pass new readback directory"}
set out [file normalize [lindex $argv 0]]
if {[file exists $out]} {error "Preserve readback"}
if {[catch {
 connect -url tcp:127.0.0.1:3121
 targets -set -filter {name =~ "ARM*#0"} -timeout 10
 loadhw -hw $root/display.xsa
 rc_pause
 if {[word 0x138000e0]!=0 || [word 0x138000cc]<1} {error "A completed live result is required"}
 rc_packet $out live live 0
 mwr 0x1380000c 3
 disconnect
 puts "ROAD_CAMERA_LIVE_READBACK_COMPLETE_AND_RESUMED"
} why opts]} {
 puts stderr "ROAD_CAMERA_FAILED $why"
 if {[dict exists $opts -errorinfo]} {puts stderr [dict get $opts -errorinfo]}
 catch {disconnect}
 exit 1
}
exit 0
'''
    for name,code in [('camera_common.tcl',common),('install_camera_test.tcl',install),('extra_tests_live.tcl',tests),('snapshot_live.tcl',snapshot)]:
        assert int(tkinter.Tcl().call('info','complete',code))==1;(ROOT/name).write_text(code,encoding='ascii')
    write(ROOT/'tools.json',dict(status='RAM_ONLY_CAMERA_TEST_SCRIPTS_READY',fixed_fixtures=selected,input_fnv=hashes,elf_sha256=o['elf_sha256'],model_sha256=o['weights_sha256'],sd_write=False))
    print('ROAD_CAMERA_RAM_TEST_TOOLS_READY',flush=True)
if __name__=='__main__':main()
