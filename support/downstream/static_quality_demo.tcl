# Fixed image inference on the verified ABI18; never writes SD or Flash.
if {$argc!=7} {error "app fixture detail photo input_fnv roi_fnv output_directory"}
lassign $argv app id detail photo expected roi_expected out
source [file join $app camera_common.tcl]
if {$detail ni {0 1} || [file exists $out]} {error "Invalid mode or existing evidence directory"}
if {[catch {
 connect -url tcp:127.0.0.1:3121
 targets -set -filter {name =~ "ARM*#0"} -timeout 10
 rc_check
 if {[word 0x13800120]!=2} {error "Expected verified PL mode2"}
 mwr 0x1380000c 0
 set idle 0
 for {set i 0} {$i<400} {incr i} {
  after 100
  rc_check
  if {[word 0x13800008] in {1 5}} {set idle 1;break}
 }
 if {!$idle} {error "Cannot reach safe inference boundary"}
 mwr 0x13800140 2
 mwr 0x13800144 32
 mwr 0x13800178 $detail
 mwr 0x13800188 $roi_expected
 dow -data $root/runtime/cases/$id/roi400.u32 0x16900000
 catch {con}
 rc_test $id $photo $expected 0
 file mkdir $out
 mrd -bin -file $out/mail.bin 0x13800000 144
 mrd -bin -file $out/ui.u32 0x16500000 16
 mrd -bin -file $out/raw.u32 0x16700000 96000
 mrd -bin -file $out/enhanced.u32 0x16100000 96000
 set n [word 0x138000d0]
 if {$n>300} {error "Invalid box count"}
 if {$n>0} {mrd -bin -file $out/boxes.f32 0x16200000 [expr {$n*6}]} else {close [open $out/boxes.f32 w]}
 set frame [word 0x13800080]
 if {$frame!=0x02000000 && $frame!=0x02119400} {error "Invalid LCD frame address"}
 mrd -bin -file $out/frame.bgr $frame 288000
 disconnect
 puts "STATIC_QUALITY_DEMO_COMPLETE $id detail=$detail"
} why opts]} {
 puts stderr "STATIC_QUALITY_DEMO_FAILED $why"
 catch {disconnect}
 exit 1
}
exit 0
