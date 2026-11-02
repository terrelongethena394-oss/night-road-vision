connect -url tcp:127.0.0.1:3121
puts [targets]
targets -set -filter {name =~ "ARM*#0"} -timeout 10
loadhw -hw E:/FPGA_Enhance_Work/road_hybrid_20261027_r1/display.xsa
puts "RECONNECT_MAILBOX"
puts [mrd 0x13800000 96]
puts "RECONNECT_VDMA"
puts [mrd 0x43000000 32]
disconnect
exit
