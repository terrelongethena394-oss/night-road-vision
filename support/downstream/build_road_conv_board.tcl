# Isolated offline candidate. No hardware/JTAG/SD/Flash operations.
set root E:/FPGA_Enhance_Work/road_conv_board_20261027
set old E:/FPGA_Enhance_Work/camera_nn8_20261023
set official E:/FPGA_Enhance_Work/official_7020/ZYNQ_Vitis_7020/27_ov5640_lcd
set ip E:/FPGA_Enhance_Work/road_conv_hls_20261027/p8/conv_project/solution_100mhz/impl/ip
set old_ip E:/FPGA_Enhance_Work/model_upgrade_20261023/hls8/full_network_project/solution_100mhz/impl/ip
if {[file exists $root/prj/road_conv.xpr]} {error "Preserve existing candidate project"}
if {![file exists $ip/component.xml]} {error "Checked roadconv IP missing"}
set_param general.maxThreads 2
create_project road_conv $root/prj -part xc7z020clg400-2
set_property target_language Verilog [current_project]
set_property ip_repo_paths [list $official/ip_repo $old_ip $ip] [current_project]
update_ip_catalog
add_files -norecurse $old/rtl/axis_rgb_bridge.v
import_files -norecurse $old/prj/camera_nn.srcs/sources_1/bd/system/system.bd
set bd [get_files */system.bd]
if {[llength $bd]!=1 || ![string match "$root/*" [file normalize $bd]]} {error "BD must belong to isolated project"}
open_bd_design $bd
foreach pin {axi_vdma_0/M_AXIS_MM2S v_axi4s_vid_out_0/video_in ps7_0_axi_periph/M04_AXI} {
 set n [get_bd_intf_nets -quiet -of_objects [get_bd_intf_pins $pin]]
 if {[llength $n]} {delete_bd_objs $n}
}
foreach cell {nanodce8_full_0 nn_input_bridge nn_output_bridge} {
 if {[llength [get_bd_cells -quiet $cell]]!=1} {error "Expected known base cell $cell"}
 delete_bd_objs [get_bd_cells $cell]
}
connect_bd_intf_net [get_bd_intf_pins axi_vdma_0/M_AXIS_MM2S] [get_bd_intf_pins v_axi4s_vid_out_0/video_in]
create_bd_cell -type ip -vlnv fpga.user:hls:road_conv3_p8:1.0 road_conv_0
connect_bd_intf_net [get_bd_intf_pins ps7_0_axi_periph/M04_AXI] [get_bd_intf_pins road_conv_0/s_axi_control]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK0] [get_bd_pins road_conv_0/ap_clk]
connect_bd_net [get_bd_pins rst_ps7_0_100M/peripheral_aresetn] [get_bd_pins road_conv_0/ap_rst_n]
set_property CONFIG.NUM_SI 5 [get_bd_cells axi_mem_intercon]
foreach {port name} {S02 gmem_in S03 gmem_w S04 gmem_out} {
 connect_bd_intf_net [get_bd_intf_pins road_conv_0/m_axi_$name] [get_bd_intf_pins axi_mem_intercon/${port}_AXI]
 connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK0] [get_bd_pins axi_mem_intercon/${port}_ACLK]
 connect_bd_net [get_bd_pins rst_ps7_0_100M/peripheral_aresetn] [get_bd_pins axi_mem_intercon/${port}_ARESETN]
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
