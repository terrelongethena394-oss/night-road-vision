set root E:/FPGA_Enhance_Work/multinex_static_20261025
open_checkpoint $root/prj/multinex_static.runs/impl_1/system_wrapper_routed.dcp
report_bus_skew -file $root/bus_skew.rpt
# check_timing details are already included in timing_summary.rpt.
report_clock_interaction -file $root/clock_interaction.rpt
set clockpins [get_pins -hier -quiet -filter {NAME =~ *multinex_0* && REF_PIN_NAME == ap_clk}]
set clocks [get_clocks -quiet -of_objects $clockpins]
if {![llength $clocks]} {error "Neural clock pin/clock not found"}
set f [open $root/physical_audit.txt w]
foreach c $clocks {
    set period [get_property PERIOD $c]
    puts $f "NEURAL_CLOCK $c PERIOD_NS $period"
    if {abs($period-10.0)>0.001} {error "Unexpected neural clock"}
}
foreach ref {DSP48E1 RAMB36E1 RAMB18E1} {
    puts $f "NEURAL_RESOURCE $ref [llength [get_cells -hier -filter "REF_NAME == $ref && NAME =~ *multinex_0*"]]"
}
puts $f "GLOBAL_SETUP_SLACK [get_property SLACK [get_timing_paths -delay_type max -max_paths 1]]"
puts $f "GLOBAL_HOLD_SLACK [get_property SLACK [get_timing_paths -delay_type min -max_paths 1]]"
close $f
puts "MULTINEX_STATIC_PHYSICAL_AUDIT_COMPLETE"
close_design
exit
