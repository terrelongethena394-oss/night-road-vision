set root [file dirname [file normalize [info script]]]
proc word {a} {
 if {[catch {mrd -value $a} v]} {
  if {![string match {*Invalid context*} $v]} {error $v}
  targets -set -filter {name =~ "ARM*#0"} -timeout 10
  set v [mrd -value $a]
 }
 return [expr {[lindex $v 0]+0}]
}
proc rc_check {} {
 if {[word 0x13800000]!=0x524F4144 || [word 0x13800004]!=30} {error "Wrong camera app ABI"}
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
