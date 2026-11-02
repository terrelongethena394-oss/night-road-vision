# Manual numerical/timing test. Host supplies only input pixels and dimensions.
set root [file dirname [file normalize [info script]]]
if {$argc<1 || $argc>2} {error "Usage: run_multinex_static.tcl output-directory ?case-count-or-id?"}
set outdir [file normalize [lindex $argv 0]]
file mkdir $outdir
source $root/cases.tcl
if {$argc==2} {
    set n [lindex $argv 1]
    if {[string is integer -strict $n]} {
        if {$n<1} {error "Positive case count required"}
        set test_cases [lrange $test_cases 0 [expr {$n-1}]]
    } else {
        set selected [list]
        foreach c $test_cases {if {[dict get $c id] eq $n} {lappend selected $c}}
        if {[llength $selected]!=1} {error "Expected one matching case ID"}
        set test_cases $selected
    }
}
connect -url tcp:127.0.0.1:3121
targets -set -filter {name =~ "ARM*#0"} -timeout 10
loadhw -hw $root/multinex_static.xsa
proc read32 {a} {return [expr {[lindex [mrd -value $a] 0]+0}]}
if {[read32 0x03000000]!=0x4D584633 || [read32 0x03000004]!=3} {error "Wrong ARM image/protocol"}
if {[read32 0x43000030]&1} {error "Camera writer must be stopped"}
set seq [read32 0x0300000C]
set f [open $outdir/runtime.csv w]
puts $f "id,height,width,ticks,timer_hz,kernel_wall_seconds,input_fnv,output_fnv,dma_errors,host_elapsed_ms"
foreach c $test_cases {
    set id [dict get $c id];set h [dict get $c h];set w [dict get $c w]
    set file $root/inputs/$id.rgba32
    if {[file size $file]!=$h*$w*4} {error "Bad input size: $id"}
    if {[read32 0x03000008]==2} {error "Previous accelerator job is busy"}
    set started [clock milliseconds]
    dow -data $file 0x04000000
    catch {con}
    mwr 0x03000014 $h
    mwr 0x03000018 $w
    set seq [expr {($seq+1)&0xffffffff}];if {!$seq} {set seq 1}
    mwr 0x0300000C $seq
    set done 0
    for {set i 0} {$i<360} {incr i} {
        after 500
        set words [mrd -value 0x03000000 27]
        if {[expr {[lindex $words 4]+0}]==$seq} {set done 1;break}
    }
    if {!$done} {error "Job timeout; do not overwrite input, inspect heartbeat"}
    if {[expr {[lindex $words 2]+0}]!=3} {error "ARM error [lindex $words 14]"}
    set ticks [expr {([lindex $words 8]+0)*4294967296+([lindex $words 7]+0)}]
    set hz [expr {[lindex $words 9]+0}]
    if {$hz<=0} {error "Invalid hardware timer frequency"}
    set input_fnv [expr {[lindex $words 11]+0}]
    if {$input_fnv!=[dict get $c input_fnv]} {error "Input DDR checksum mismatch: $id"}
    set output_fnv [expr {[lindex $words 12]+0}]
    set dma [expr {[lindex $words 13]+0}]
    if {$dma} {error "Display DMA errors: $dma"}
    mrd -bin -file $outdir/$id.output32 0x04200000 [expr {$h*$w}]
    mrd -bin -file $outdir/$id.diag64 0x04B00000 24
    if {[dict get $c scratch_check]} {
        mrd -bin -file $outdir/$id.scratch32 0x04400000 [expr {$h*$w*4}]
    }
    puts $f "$id,$h,$w,$ticks,$hz,[expr {double($ticks)/$hz}],$input_fnv,$output_fnv,$dma,[expr {[clock milliseconds]-$started}]"
    flush $f
    puts "STATIC_CASE_COMPLETE id=$id kernel_wall_seconds=[expr {double($ticks)/$hz}] (not host transfer time)"
}
close $f
disconnect
puts "STATIC_BATCH_COMPLETE: run validate_multinex_readback.py before interpreting results"
exit
