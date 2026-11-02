from build_road_camera import ROOT,read,write,sha
import tkinter

def main():
    start=r'''source [file join [file dirname [file normalize [info script]]] camera_common.tcl]
if {[catch {
 connect -url tcp:127.0.0.1:3121
 targets -set -filter {name =~ "ARM*#0"} -timeout 10
 rc_check
 set before [word 0x138000cc]
 mwr 0x13800070 0
 mwr 0x1380006c 0
 mwr 0x1380000c 3
 set ready 0
 for {set i 0} {$i<600} {incr i} {
  after 100
  rc_check
  if {[word 0x138000cc]>=$before+2 && [word 0x138000e0]==0} {set ready 1;break}
 }
 if {!$ready} {error "Live results did not progress"}
 disconnect
 puts "ROAD_CAMERA_EXISTING_LIVE_STARTED"
} why opts]} {
 puts stderr "ROAD_CAMERA_FAILED $why"
 if {[dict exists $opts -errorinfo]} {puts stderr [dict get $opts -errorinfo]}
 catch {disconnect}
 exit 1
}
exit 0
'''
    cadence=r'''source [file join [file dirname [file normalize [info script]]] camera_common.tcl]
if {$argc!=1} {error "Pass new CSV path"}
set out [file normalize [lindex $argv 0]]
if {[file exists $out]} {error "Preserve earlier cadence"}
if {[catch {
 connect -url tcp:127.0.0.1:3121
 targets -set -filter {name =~ "ARM*#0"} -timeout 10
 rc_check
 if {[word 0x1380000c]!=3} {error "Live mode required"}
 set f [open $out w]
 puts $f "wall_ms,state,completed,preview,detect_lo,detect_hi,hz,service_calls,error,dma_read,dma_write,had_pause,result_id,active_id"
 for {set i 0} {$i<31} {incr i} {
  set a [mrd -value 0x13800000 72]
  set values [list [clock milliseconds]]
  foreach index {2 51 39 19 20 18 54 6 35 41 62 45 36} {lappend values [expr {[lindex $a $index]+0}]}
  puts $f [join $values ,]
  flush $f
  after 500
 }
 close $f
 disconnect
 puts "ROAD_CAMERA_CADENCE_READ_COMPLETE"
} why opts]} {
 puts stderr "ROAD_CAMERA_FAILED $why"
 catch {close $f}
 catch {disconnect}
 exit 1
}
exit 0
'''
    for name,text in [('start_existing_live.tcl',start),('measure_live.tcl',cadence)]:
        assert int(tkinter.Tcl().call('info','complete',text))==1;(ROOT/name).write_text(text,encoding='ascii')
    write(ROOT/'live_controls.json',dict(start_sha256=sha(ROOT/'start_existing_live.tcl'),measure_sha256=sha(ROOT/'measure_live.tcl'),measurement='Host-wall timestamps, read-only500ms cadence sampling, exclude paused rows for active inference time.',sd_write=False))
    print('CAMERA_LIVE_CONTROLS_READY',flush=True)
if __name__=='__main__':main()
