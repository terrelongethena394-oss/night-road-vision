# New candidate only; no hardware connection, download, SD, or old-project edits.
set source_root E:/FPGA_Enhance_Work/official_7020/ZYNQ_Vitis_7020/27_ov5640_lcd
set old_root E:/FPGA_Enhance_Work/camera_nn8_20261023
set build_root E:/FPGA_Enhance_Work/camera_nn_digit_20261023
set nn_ip E:/FPGA_Enhance_Work/model_upgrade_20261023/hls8/full_network_project/solution_100mhz/impl/ip
set digit_ip E:/FPGA_Enhance_Work/digit_recognition_20261023/hls/digit_project/solution_100mhz/impl/ip
set project_dir $build_root/prj
if {[file exists $project_dir/camera_digit.xpr]} {error "Existing candidate project; inspect before resume"}
set_param general.maxThreads 4
create_project camera_digit $project_dir -part xc7z020clg400-2
set_property target_language Verilog [current_project]
set_property ip_repo_paths [list $source_root/ip_repo $nn_ip $digit_ip] [current_project]
update_ip_catalog
add_files -norecurse $build_root/rtl/axis_rgb_bridge.v
import_files -norecurse $old_root/prj/camera_nn.srcs/sources_1/bd/system/system.bd
set bd [get_files */system.bd]
open_bd_design $bd
foreach name {raw_digit_0 enhanced_digit_0} {
    create_bd_cell -type ip -vlnv xilinx.com:hls:digit_monitor:1.0 $name
}
delete_bd_objs [get_bd_intf_nets -of_objects [get_bd_intf_pins nn_input_bridge/M_AXIS]]
delete_bd_objs [get_bd_intf_nets -of_objects [get_bd_intf_pins nanodce8_full_0/output_r]]
connect_bd_intf_net [get_bd_intf_pins nn_input_bridge/M_AXIS] [get_bd_intf_pins raw_digit_0/input_r]
connect_bd_intf_net [get_bd_intf_pins raw_digit_0/output_r] [get_bd_intf_pins nanodce8_full_0/input_r]
connect_bd_intf_net [get_bd_intf_pins nanodce8_full_0/output_r] [get_bd_intf_pins enhanced_digit_0/input_r]
connect_bd_intf_net [get_bd_intf_pins enhanced_digit_0/output_r] [get_bd_intf_pins nn_output_bridge/S_AXIS]
set_property CONFIG.NUM_MI 7 [get_bd_cells ps7_0_axi_periph]
foreach {name port address} {raw_digit_0 M05 0x43C30000 enhanced_digit_0 M06 0x43C40000} {
    connect_bd_intf_net [get_bd_intf_pins ps7_0_axi_periph/${port}_AXI] [get_bd_intf_pins $name/s_axi_control]
    foreach pin [list $name/ap_clk ps7_0_axi_periph/${port}_ACLK] {
        connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK0] [get_bd_pins $pin]
    }
    foreach pin [list $name/ap_rst_n ps7_0_axi_periph/${port}_ARESETN] {
        connect_bd_net [get_bd_pins rst_ps7_0_100M/peripheral_aresetn] [get_bd_pins $pin]
    }
    assign_bd_address -offset $address -range 0x00010000 -target_address_space [get_bd_addr_spaces processing_system7_0/Data] [get_bd_addr_segs $name/s_axi_control/Reg] -force
}
validate_bd_design -force
save_bd_design
write_bd_tcl -force $build_root/system_digit_bd.tcl
report_ip_status -file $build_root/ip_status.rpt
generate_target all $bd
add_files -norecurse [make_wrapper -files $bd -top]
add_files -fileset constrs_1 $source_root/ov5640_lcd.srcs/constrs_1/new/pin.xdc
set_property top system_wrapper [current_fileset]
update_compile_order -fileset sources_1
launch_runs synth_1 -jobs 4
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "Digit board synthesis failed"}
launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1
set bit $project_dir/camera_digit.runs/impl_1/system_wrapper.bit
if {[get_property PROGRESS [get_runs impl_1]] ne "100%" || ![file exists $bit]} {error "Digit bitstream failed"}
open_run impl_1
report_timing_summary -file $build_root/timing_summary.rpt
report_bus_skew -file $build_root/bus_skew.rpt
report_utilization -file $build_root/utilization.rpt
report_utilization -hierarchical -file $build_root/utilization_hierarchy.rpt
report_drc -file $build_root/drc.rpt
set wns [get_property SLACK [get_timing_paths -delay_type max -max_paths 1]]
set whs [get_property SLACK [get_timing_paths -delay_type min -max_paths 1]]
if {$wns<0 || $whs<0} {error "Timing failed WNS=$wns WHS=$whs"}
foreach key {nanodce8_full_0 raw_digit_0 enhanced_digit_0} {
    set dsps [get_cells -hier -filter "REF_NAME == DSP48E1 && NAME =~ *${key}*"]
    if {[llength $dsps]==0} {error "Neural hierarchy missing for $key"}
    puts "NEURAL_CORE_DSP $key [llength $dsps]"
}
write_hw_platform -fixed -include_bit -force -file $build_root/camera_digit.xsa
file copy $bit $build_root/system_wrapper.bit
puts "DIGIT_BOARD_BUILD_PASS WNS=$wns WHS=$whs"
close_project
exit
