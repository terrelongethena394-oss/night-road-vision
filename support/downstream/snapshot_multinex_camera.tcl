set root [file dirname [file normalize [info script]]]
if {$argc!=1} {error "Usage: snapshot_multinex_camera.tcl NEW_OUTPUT_DIRECTORY"}
set out [file normalize [lindex $argv 0]]
if {[file exists $out]} {error "Preserve existing snapshot directory"}
file mkdir $out
connect -url tcp:127.0.0.1:3121
targets -set -filter {name =~ "ARM*#0"} -timeout 10
loadhw -hw $root/camera.xsa
set words [mrd -value 0x03000000 29]
if {[expr {[lindex $words 0]+0}]!=0x4D584334} {error "Wrong application"}
mwr 0x0300000C 1
set paused 0
for {set i 0} {$i<40} {incr i} {
 after 100
 set words [mrd -value 0x03000000 29]
 if {[expr {[lindex $words 2]+0}]==4} {error "Camera runtime error [lindex $words 15]"}
 if {[expr {[lindex $words 2]+0}]==3 && [expr {[lindex $words 4]+0}]==1} {set paused 1;break}
}
if {!$paused} {error "Pause did not complete"}
set h [expr {[lindex $words 6]+0}];set w [expr {[lindex $words 7]+0}]
if {$h!=240 || $w!=400} {error "Unexpected input dimensions"}
set f [open $out/mailbox.txt w];puts $f $words;close $f
set f [open $out/profile.txt w];puts $f [mrd -value 0x03000074 5];close $f
mrd -bin -file $out/input32.bin 0x04000000 [expr {$h*$w}]
mrd -bin -file $out/output32.bin 0x04200000 [expr {$h*$w}]
if {[expr {[lindex $words 1]+0}]>=5} {
 set f [open $out/quality.txt w];puts $f [mrd -value 0x03000088 4];close $f
 mrd -bin -file $out/protected32.bin 0x04C00000 [expr {$h*$w}]
}
if {[expr {[lindex $words 1]+0}]>=6} {
 set f [open $out/digit_telemetry.txt w];puts $f [mrd -value 0x03000098 15];close $f
 mrd -bin -file $out/digit_gray.bin 0x04E00000 588
 mrd -bin -file $out/digit_scores.i64 0x04E01000 66
}
mrd -bin -file $out/diag64.bin 0x04B00000 24
mrd -bin -file $out/scratch32.bin 0x04400000 [expr {$h*$w*4}]
set capture [expr {[lindex $words 24]+0}]
mrd -bin -file $out/capture.bgr24 [expr {0x06000000+$capture*1152000}] 288000
set display [expr {[lindex $words 23]+0}]
mrd -bin -file $out/display.bgr24 [expr {0x02000000+$display*1152000}] 288000
mwr 0x0300000C 0
after 1000
set next [mrd -value 0x03000000 29]
set f [open $out/resumed.txt w];puts $f $next;close $f
if {[expr {[lindex $next 2]+0}]==4 || [expr {[lindex $next 5]+0}]<=[expr {[lindex $words 5]+0}]} {error "Camera did not resume"}
disconnect
puts "CAMERA_SNAPSHOT_CAPTURED_AND_RESUMED"
exit
