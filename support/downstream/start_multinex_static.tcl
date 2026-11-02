# Explicit manual JTAG launch only; this file is not called during offline builds.
set root [file dirname [file normalize [info script]]]
if {![file exists $root/ACCEPTED_FOR_JTAG.txt]} {error "Candidate has not passed the offline acceptance checks"}
connect -url tcp:127.0.0.1:3121
puts [targets]
targets -set -filter {name =~ "APU*"} -timeout 10
rst -system
after 1000
fpga -file $root/multinex_static.bit
targets -set -filter {name =~ "ARM*#0"} -timeout 10
source $root/ps7_init.tcl
ps7_init
ps7_post_config
dow $root/multinex_static.elf
con
loadhw -hw $root/multinex_static.xsa
proc read32 {a} {return [expr {[lindex [mrd -value $a] 0]+0}]}
set ready 0
for {set i 0} {$i<30} {incr i} {
    after 500
    if {[read32 0x03000000]==0x4D584633 && [read32 0x03000008]==1} {set ready 1;break}
}
if {!$ready} {error "Static ARM application not ready; inspect UART and mailbox"}
if {[read32 0x43000030]&1} {error "Camera writer unexpectedly enabled"}
set cr [read32 0x43000000]
if {($cr&1)==0 || ($cr&0x0A)!=0} {error "Display must use parking, no genlock"}
puts "MULTINEX_STATIC_JTAG_READY no_camera=1 sd_unchanged=1"
disconnect
exit
