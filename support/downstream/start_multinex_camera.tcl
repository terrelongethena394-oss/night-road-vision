set root [file dirname [file normalize [info script]]]
if {![file exists $root/offline_camera.json]} {error "Compile/validate camera candidate first"}
connect -url tcp:127.0.0.1:3121
puts [targets]
targets -set -filter {name =~ "APU*"} -timeout 10
rst -system
after 1000
fpga -file $root/camera.bit
targets -set -filter {name =~ "ARM*#0"} -timeout 10
source $root/ps7_init.tcl
ps7_init
ps7_post_config
dow $root/camera.elf
con
loadhw -hw $root/camera.xsa
proc word {a} {return [expr {[lindex [mrd -value $a] 0]+0}]}
set ready 0
for {set i 0} {$i<60} {incr i} {
 after 500
 set w [mrd -value 0x03000000 29]
 if {[expr {[lindex $w 0]+0}]==0x4D584334} {
  if {[expr {[lindex $w 2]+0}]==4} {error "Camera error code [lindex $w 15], cameraID=[lindex $w 25], DMA=[lindex $w 13]/[lindex $w 14]"}
  if {[expr {[lindex $w 5]+0}]>=5} {set ready 1;break}
 }
}
if {!$ready} {error "Camera has not produced five enhanced frames"}
puts "MULTINEX_CAMERA_STARTED [mrd -value 0x03000000 29]"
disconnect
exit
