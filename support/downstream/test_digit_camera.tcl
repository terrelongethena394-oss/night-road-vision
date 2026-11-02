set root [file dirname [file normalize [info script]]]
set out $root/board_digit
if {[file exists $out]} {error "Preserve prior board classifier tests"}
file mkdir $out
source $root/digit_cases.tcl
connect -url tcp:127.0.0.1:3121
targets -set -filter {name =~ "ARM*#0"} -timeout 10
loadhw -hw $root/camera.xsa
set words [mrd -value 0x03000000 29]
if {[expr {[lindex $words 0]+0}]!=0x4D584334 || [expr {[lindex $words 1]+0}]!=6} {error "Wrong digit firmware"}
proc paused {} {
 for {set i 0} {$i<100} {incr i} {
  set words [mrd -value 0x03000000 29]
  if {[expr {[lindex $words 2]+0}]==4} {error "Camera error [lindex $words 15]"}
  if {[expr {[lindex $words 2]+0}]==3 && [expr {[lindex $words 4]+0}]==1} {return $words}
  after 100
 }
 error "Pause timed out"
}
mwr 0x0300000C 1
set words [paused]
foreach c $cases {
 set id [dict get $c id];set d $out/$id;file mkdir $d
 set seq [expr {[lindex $words 5]+0}]
 dow -data [dict get $c file] 0x04000000
 catch {con}
 mwr 0x030000B8 [dict get $c x]
 mwr 0x030000BC [dict get $c y]
 mwr 0x030000C0 [dict get $c size]
 mwr 0x0300000C 2
 set complete 0
 for {set i 0} {$i<100} {incr i} {
  after 100
  set words [mrd -value 0x03000000 29]
  if {[expr {[lindex $words 2]+0}]==4} {error "Injected photo error [lindex $words 15]"}
  if {[expr {[lindex $words 5]+0}]>$seq && [expr {[lindex $words 2]+0}]==3 && [expr {[lindex $words 4]+0}]==1} {set complete 1;break}
 }
 if {!$complete} {error "Photo did not complete"}
 if {[expr {[lindex $words 27]+0}]!=[dict get $c fnv]} {error "Wrong actual board input"}
 set f [open $d/mailbox.txt w];puts $f $words;close $f
 set f [open $d/quality.txt w];puts $f [mrd -value 0x03000088 4];close $f
 set f [open $d/profile.txt w];puts $f [mrd -value 0x03000074 5];close $f
 set f [open $d/digit_telemetry.txt w];puts $f [mrd -value 0x03000098 15];close $f
 mrd -bin -file $d/input32.bin 0x04000000 96000
 mrd -bin -file $d/output32.bin 0x04200000 96000
 mrd -bin -file $d/protected32.bin 0x04C00000 96000
 mrd -bin -file $d/digit_gray.bin 0x04E00000 588
 mrd -bin -file $d/digit_scores.i64 0x04E01000 66
 set display [expr {[lindex $words 23]+0}]
 mrd -bin -file $d/display.bgr24 [expr {0x02000000+$display*1152000}] 288000
 mwr 0x0300000C 0
 after 1000
 set resumed [mrd -value 0x03000000 29]
 set f [open $d/resumed.txt w];puts $f $resumed;close $f
 if {[expr {[lindex $resumed 5]+0}]<=[expr {[lindex $words 5]+0}]} {error "Live camera did not resume"}
 puts "DIGIT_PHOTO_CAPTURED $id"
 mwr 0x0300000C 1
 set words [paused]
}
mwr 0x0300000C 0
after 1000
disconnect
puts "DIGIT_PHOTO_TESTS_CAPTURED_LIVE_RESTORED"
exit
