set ::env(TCL_LIBRARY) [info library]
set root E:/FPGA_Enhance_Work/road_conv13_p16_board_20261028_r1
set official E:/FPGA_Enhance_Work/official_7020/ZYNQ_Vitis_7020/27_ov5640_lcd
set_param general.maxThreads 2
create_project road_conv $root/prj -part xc7z020clg400-2
config_ip_cache -use_cache_location $root/ipcache
set_property target_language Verilog [current_project]
set_property ip_repo_paths [list $official/ip_repo E:/FPGA_Enhance_Work/road_conv_burst_hls_20261027/conv_project/solution_100mhz/impl/ip E:/FPGA_Enhance_Work/road_conv13_p16_package_20261028_r1/conv_project/solution_100mhz/impl/ip] [current_project]
update_ip_catalog
import_files -norecurse E:/FPGA_Enhance_Work/road_conv_burst_board_20261027/prj/road_conv.srcs/sources_1/bd/system/system.bd
set bd [get_files */system.bd]
if {[llength $bd]!=1 || ![string match "$root/*" [file normalize $bd]]} {error "Isolated BD required"}
open_bd_design $bd
if {[llength [get_bd_cells -quiet road_conv_0]]!=1} {error "Expected original shared core"}
if {[get_property CONFIG.NUM_SI [get_bd_cells axi_mem_intercon]]!=5} {error "DDR topology changed"}
delete_bd_objs [get_bd_cells road_conv_0]
create_bd_cell -type ip -vlnv fpga.user:hls:road_conv13_p16:1.0 road_conv_0
connect_bd_intf_net [get_bd_intf_pins ps7_0_axi_periph/M04_AXI] [get_bd_intf_pins road_conv_0/s_axi_control]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK0] [get_bd_pins road_conv_0/ap_clk]
connect_bd_net [get_bd_pins rst_ps7_0_100M/peripheral_aresetn] [get_bd_pins road_conv_0/ap_rst_n]
foreach {conv_port conv_bundle} {S02 gmem_in S03 gmem_w S04 gmem_out} {
 connect_bd_intf_net [get_bd_intf_pins road_conv_0/m_axi_$conv_bundle] [get_bd_intf_pins axi_mem_intercon/${conv_port}_AXI]
}
assign_bd_address
assign_bd_address -offset 0x43C30000 -range 0x00010000 -target_address_space [get_bd_addr_spaces processing_system7_0/Data] [get_bd_addr_segs road_conv_0/s_axi_control/Reg] -force
validate_bd_design -force
save_bd_design
write_bd_tcl -force $root/system_road_conv_bd.tcl
report_ip_status -file $root/ip_status.rpt
generate_target all $bd
add_files -norecurse [make_wrapper -files $bd -top]
add_files -fileset constrs_1 $official/ov5640_lcd.srcs/constrs_1/new/pin.xdc
set_property top system_wrapper [current_fileset]
update_compile_order -fileset sources_1
launch_runs synth_1 -jobs 2
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "Synthesis failed"}
launch_runs impl_1 -to_step write_bitstream -jobs 2
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {error "Implementation failed"}
open_run impl_1
report_utilization -file $root/utilization.rpt
report_utilization -hierarchical -file $root/utilization_hierarchy.rpt
report_timing_summary -file $root/timing_summary.rpt
report_drc -file $root/drc.rpt
report_clock_interaction -file $root/clock_interaction.rpt
report_bus_skew -file $root/bus_skew.rpt
set wns [get_property SLACK [get_timing_paths -delay_type max -max_paths 1]]
set whs [get_property SLACK [get_timing_paths -delay_type min -max_paths 1]]
set dsps [get_cells -hier -filter {REF_NAME == DSP48E1 && NAME =~ *road_conv_0*}]
if {![llength $dsps]} {error "Roadconv DSP hierarchy missing"}
write_hw_platform -fixed -include_bit -force -file $root/road_conv.xsa
file copy $root/prj/road_conv.runs/impl_1/system_wrapper.bit $root/road_conv.bit
puts "ROAD_CONV_BOARD_FILES_CREATED WNS=$wns WHS=$whs DSP=[llength $dsps]"
if {$wns<0 || $whs<0} {error "Timing failure; no board acceptance"}
set f [open $root/timing_acceptance.txt w]
puts $f "WNS=$wns"
puts $f "WHS=$whs"
puts $f "ROAD_CONV_DSP=[llength $dsps]"
puts $f "hardware_downloaded=false"
close $f
puts "ROAD_CONV_BOARD_OFFLINE_BUILD_PASS"
close_project
exit
