# Upload host images to the INACTIVE DDR slot, park at a frame boundary,
# then read ARM-latched same-frame PL predictions. No expected label is sent.
set root [file dirname [file normalize [info script]]]
if {$argc<1 || $argc>2} {error "Usage: run_fixed_image.tcl output-directory ?case-count-or-id?"}
set outdir [file normalize [lindex $argv 0]]
file mkdir $outdir
source $root/cases.tcl
if {$argc==2} {
    set selector [lindex $argv 1]
    if {[string is integer -strict $selector]} {
        if {$selector<1} {error "Case count must be positive"}
        set image_cases [lrange $image_cases 0 [expr {$selector-1}]]
    } else {
        set selected [list]
        foreach entry $image_cases {if {[dict get $entry id] eq $selector} {lappend selected $entry}}
        if {[llength $selected]!=1} {error "Expected one case with ID $selector"}
        set image_cases $selected
    }
}
connect -url tcp:127.0.0.1:3121
targets -set -filter {name =~ "ARM*#0"} -timeout 10
loadhw -hw $root/board/camera_digit.xsa
proc read32 {address} {return [expr {[lindex [mrd -value $address] 0]+0}]}
if {[read32 0x03000000]!=0x494D4754 || [read32 0x03000004]!=1} {error "Wrong application/protocol; start image test first"}
if {[read32 0x43000030]&1} {error "Camera DMA writer must be disabled"}
set seq [read32 0x03000014]
set file [open $outdir/board_results.csv w]
puts $file "id,truth,raw_expected,enh_expected,raw_board,enh_board,frame,raw_margin,enh_margin,fnv_expected,fnv_board,dma_errors,host_elapsed_ms"
set count 0
set mismatch 0
foreach entry $image_cases {
    set image $root/inputs/[file tail [dict get $entry file]]
    if {[file size $image]!=1152000} {error "Wrong frame byte count"}
    set slot [expr {1-[read32 0x03000038]}]
    if {$slot!=0 && $slot!=1} {error "Invalid inactive slot"}
    set address [expr {0x02000000+$slot*1152000}]
    set t0 [clock milliseconds]
    dow -data $image $address
    # Some debugger paths stop a CPU during data transfer. Resume if needed;
    # if it was running, 'con' simply reports that state and is harmless.
    catch {con} resume_detail
    mwr 0x03000010 $slot
    incr seq
    mwr 0x0300000C $seq
    set done 0
    for {set attempt 0} {$attempt<100} {incr attempt} {
        after 100
        set words [mrd -value 0x03000000 20]
        if {[expr {[lindex $words 5]+0}]==$seq} {set done 1;break}
    }
    if {!$done} {error "Image request timed out; inspect mailbox and ARM heartbeat"}
    if {[expr {[lindex $words 2]+0}]!=3} {error "ARM image-test error code [lindex $words 13]"}
    set raw [expr {[lindex $words 6]+0}]
    set enh [expr {[lindex $words 7]+0}]
    set frame [expr {[lindex $words 8]+0}]
    set rm [expr {[lindex $words 9]+0}]
    set em [expr {[lindex $words 10]+0}]
    set fnv [expr {[lindex $words 11]+0}]
    set dma [expr {[lindex $words 12]+0}]
    set wanted_fnv [dict get $entry fnv]
    if {$fnv!=$wanted_fnv} {error "DDR input checksum mismatch; do not interpret predictions"}
    if {$dma!=0} {error "VDMA reported errors"}
    set rp [dict get $entry raw_expected]
    set ep [dict get $entry enh_expected]
    if {$raw!=$rp || $enh!=$ep || $rm!=[dict get $entry raw_margin] || $em!=[dict get $entry enh_margin]} {incr mismatch}
    puts $file "[dict get $entry id],[dict get $entry truth],$rp,$ep,$raw,$enh,$frame,$rm,$em,$wanted_fnv,$fnv,$dma,[expr {[clock milliseconds]-$t0}]"
    flush $file
    puts "FIXED_IMAGE_RESULT id=[dict get $entry id] truth=[dict get $entry truth] raw=$raw expected_raw=$rp enhanced=$enh expected_enhanced=$ep frame=$frame fnv_ok=1"
    if {$count==0} {
        mrd -bin -file $outdir/first_input_readback.bin $address 288000
    }
    incr count
}
close $file
puts "FIXED_IMAGE_BATCH_FINISHED cases=$count software_integer_mismatch_cases=$mismatch"
puts "Host transfer time is NOT accelerator latency; predictions are not a camera accuracy measurement."
disconnect
exit
