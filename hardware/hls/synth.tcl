set root [file dirname [file normalize [info script]]]
cd $root
open_project conv_project
set_top road_conv3_fp32
add_files road_conv3_hls.cpp -cflags "-std=c++14 -DRC_PE=16 -ffp-contract=off -fno-fast-math"
add_files road_conv3_hls.h
add_files -tb tb_road_conv3.cpp -cflags "-std=c++14 -DRC_PE=16 -ffp-contract=off -fno-fast-math"
open_solution solution_100mhz -flow_target vivado
set_part {xc7z020clg400-2}
create_clock -period 10 -name default
csynth_design
puts "ROAD_CONV3_SYNTH_COMPLETE_P16"
exit
