# Read-only readiness check. No reset, programming or storage writes.
connect -url tcp:127.0.0.1:3121
puts [targets]
targets -set -filter {name =~ "ARM*#0"} -timeout 10
puts "CURRENT_MAILBOX [mrd -value 0x03000000 4]"
disconnect
puts "MULTINEX_JTAG_READINESS_CHECK_COMPLETE"
exit
