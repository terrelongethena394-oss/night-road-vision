set root [file dirname [file normalize [info script]]]
cd $root
open_project conv_project
open_solution solution_100mhz
cosim_design -rtl verilog -tool xsim -trace_level none -argv "rtl E:/FPGA_Enhance_Work/road_conv13_p16_hls_20261028_r1"
puts "ROAD_CONV3_COSIM_COMPLETE_P16"
exit
