set root [file dirname [file normalize [info script]]]
connect -url tcp:127.0.0.1:3121
targets -set -filter {name =~ "ARM*#0"} -timeout 10
loadhw -hw $root/camera.xsa
set f [open $root/live_cadence.csv w]
puts $f "elapsed_ms,sequence,state,kernel_ticks,loop_ticks,read_error,write_error,error"
set t0 [clock milliseconds]
for {set i 0} {$i<11} {incr i} {
 set w [mrd -value 0x03000000 34]
 if {[expr {[lindex $w 0]+0}]!=0x4D584334 || [expr {[lindex $w 33]+0}]!=1} {error "Wrong live/cache application"}
 set t [expr {[clock milliseconds]-$t0}]
 set seq [expr {[lindex $w 5]+0}];set state [expr {[lindex $w 2]+0}]
 set kernel [expr {([lindex $w 10]+0)*4294967296+([lindex $w 9]+0)}]
 set loop [expr {([lindex $w 12]+0)*4294967296+([lindex $w 11]+0)}]
 set r [expr {[lindex $w 13]+0}];set wr [expr {[lindex $w 14]+0}];set e [expr {[lindex $w 15]+0}]
 puts $f "$t,$seq,$state,$kernel,$loop,$r,$wr,$e";flush $f
 if {$r || $wr || $e || $state==4} {error "Live camera error $e DMA=$r/$wr"}
 if {$i<10} {after 1000}
}
close $f
disconnect
puts "CONTINUOUS_CAMERA_CADENCE_MEASURED"
exit
