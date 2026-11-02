# New volatile ARM image-input application, same FPGA candidate; no SD writes.
set root [file dirname [file normalize [info script]]]
set package $root/board
connect -url tcp:127.0.0.1:3121
puts [targets]
targets -set -filter {name =~ "xc7z020"} -timeout 10
targets -set -filter {name =~ "APU*"} -timeout 10
rst -system
after 1000
fpga -file $package/system_wrapper.bit
targets -set -filter {name =~ "ARM*#0"}
source $package/ps7_init.tcl
ps7_init
ps7_post_config
dow $root/image_test.elf
con
loadhw -hw $package/camera_digit.xsa
proc read32 {address} {return [expr {[lindex [mrd -value $address] 0]+0}]}
set ready 0
for {set i 0} {$i<20} {incr i} {
    after 500
    if {[read32 0x03000000]==0x494D4754 && [read32 0x03000008]==1} {set ready 1;break}
}
if {!$ready} {error "Image-input ARM application did not become ready"}
if {[read32 0x43000030]&1} {error "Camera DMA writer unexpectedly enabled"}
set cr [read32 0x43000000]
if {($cr&1)==0 || ($cr&0x0A)!=0} {error "MM2S must run in parking mode with genlock disabled"}
set first [expr {[read32 0x43C40070]>>4}]
after 1000
set second [expr {[read32 0x43C40070]>>4}]
if {$second<1 || $second<=$first} {error "Image processing frame counter is not advancing"}
puts "FIXED_IMAGE_JTAG_READY no_camera=1 s2mm_run=0 genlock=0 parking=1 frame_before=$first frame_after=$second"
disconnect
exit
