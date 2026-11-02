source E:/FPGA_Enhance_Work/road_car_roi_delivery_20261031_r1/board_candidate/firmware/camera_common.tcl
set camera_app E:/FPGA_Enhance_Work/natural_exposure_guard_20261101_r1/firmware
if {[catch {
 connect -url tcp:127.0.0.1:3121
 targets -set -filter {name =~ "APU*"} -timeout 10
 rst -system
 targets -set -filter {name =~ "ARM*#0"} -timeout 10
 stop
 rst -processor -clear-registers
 stop
 fpga -file $camera_app/display.bit
 source $camera_app/ps7_init.tcl
 ps7_init
 ps7_post_config
 loadhw -hw $camera_app/display.xsa
 dow $camera_app/road_detail.elf
 con
 set ready 0
 for {set i 0} {$i<1200} {incr i} {after 100;if {[word 0x13800000]==0x524f4144 && [word 0x13800004]==32} {if {[word 0x13800018]!=0 || [word 0x13800008]==4} {error "Camera app error [word 0x13800018]"};if {[word 0x13800430]==0x43414d31 && [word 0x13800008]==1} {set ready 1;break}}}
 if {!$ready} {error "Camera ready timeout"}
 disconnect
 puts "CAMERA_STATION_ABI32_PREVIEW_READY"
} why opts]} {puts stderr "CAMERA_STATION_START_FAILED $why";catch {disconnect};exit 1}
exit 0
