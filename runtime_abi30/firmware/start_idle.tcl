set selectedMode 2
if {$argc>0} {set selectedMode [lindex $argv 0]}
if {$selectedMode ni {1 2}} {error "Expected PL mode1 or2"}
source [file join [file dirname [file normalize [info script]]] camera_common.tcl]
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
 dow $root/road_detail.elf
 con
 set ready 0
 for {set i 0} {$i<400} {incr i} {
  after 100
  if {[word 0x13800000]==0x524F4144 && [word 0x13800004]==30} {
   rc_check
   if {[word 0x13800008]==1 && [word 0x138000a0]==0x5640 && [word 0x13800078]==0x7084} {set ready 1;break}
  }
 }
 if {!$ready} {error "Camera/LCD init timed out"}
 puts "ROAD_CAMERA_STAGE sensor_and_preview_ready"
 dow -data $root/runtime/weights.f32 0x11000000
 dow -data $root/runtime/refiner_weights.f32 0x1C200000
 dow -data $root/runtime/roi_weights.f32 0x1B000000
 catch {con}
 mwr 0x13800070 0
 mwr 0x1380006c 0
 mwr 0x13800120 $selectedMode
 mwr 0x1380000c 0
 mwr 0x1380000c 0
 disconnect
 puts "ROAD_RETINEX_IDLE_READY"
} why opts]} {
 puts stderr "ROAD_CAMERA_FAILED $why"
 if {[dict exists $opts -errorinfo]} {puts stderr [dict get $opts -errorinfo]}
 catch {disconnect}
 exit 1
}
exit 0
