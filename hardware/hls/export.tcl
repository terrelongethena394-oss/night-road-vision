set root [file dirname [file normalize [info script]]]
cd $root
open_project conv_project
open_solution solution_100mhz
export_design -format ip_catalog -rtl verilog -vendor fpga.user -library hls -version 1.0 -ipname road_conv13_p16
puts "ROAD_CONV3_EXPORT_COMPLETE_P16"
exit
