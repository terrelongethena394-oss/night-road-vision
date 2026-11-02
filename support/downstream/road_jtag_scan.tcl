# Read-only scan. No reset, download, SD or flash access.
if {[catch {
 connect -url tcp:127.0.0.1:3121
 puts "ROAD_READ_ONLY_TARGETS_BEGIN"
 puts [targets]
 puts "ROAD_READ_ONLY_TARGETS_END"
 disconnect
} why opts]} {
 puts stderr "ROAD_READ_ONLY_SCAN_FAILED: $why"
 exit 1
}
exit 0
