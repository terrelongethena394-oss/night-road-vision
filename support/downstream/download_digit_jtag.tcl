# FUTURE manual use only. This file was prepared without contacting hardware.
# Volatile JTAG programming; does not write SD/QSPI/eMMC.
set root [file dirname [file normalize [info script]]]
foreach artifact {system_wrapper.bit camera_app.elf ps7_init.tcl camera_digit.xsa} {
    if {![file exists $root/$artifact]} {error "Missing $root/$artifact"}
}
connect -url tcp:127.0.0.1:3121
puts [targets]
targets -set -filter {name =~ "xc7z020"} -timeout 10
targets -set -filter {name =~ "APU*"} -timeout 10
rst -system
after 1000
fpga -file $root/system_wrapper.bit
targets -set -filter {name =~ "ARM*#0"}
source $root/ps7_init.tcl
ps7_init
ps7_post_config
dow $root/camera_app.elf
con
loadhw -hw $root/camera_digit.xsa
set configured 0
for {set attempt 0} {$attempt<20} {incr attempt} {
    after 500
    if {[catch {
        set good 1
        foreach {base which} {0x43C30000 0 0x43C40000 1} {
            foreach {offset expected} [list 0x10 480 0x18 800 0x20 480 0x28 112 0x30 $which] {
                set value [lindex [mrd -value [expr {$base+$offset}]] 0]
                if {$value!=$expected} {set good 0}
            }
            set control [lindex [mrd -value $base] 0]
            if {($control&0x80)==0} {set good 0}
        }
        foreach {address expected} {0x43C20010 480 0x43C20018 800 0x43C20020 1} {
            if {[lindex [mrd -value $address] 0]!=$expected} {set good 0}
        }
    } why]} {
        puts "Waiting for ARM/AXI startup: $why"
    } elseif {$good} {
        set configured 1
        puts "DIGIT_ALL_THREE_CORES_CONFIGURED"
        break
    }
}
if {!$configured} {error "Expected neural-core configuration was not observed; inspect UART"}
set prior_raw 0
set prior_enh 0
for {set i 0} {$i<2} {incr i} {
    after 1000
    set raw [lindex [mrd -value 0x43C30070] 0]
    set enh [lindex [mrd -value 0x43C40070] 0]
    set rf [expr {($raw>>4)&0x0fffffff}]
    set ef [expr {($enh>>4)&0x0fffffff}]
    if {$rf<1||$ef<1||($i>0&&($rf<=$prior_raw||$ef<=$prior_enh))} {
        error "Digit frame counters did not advance; inspect camera/VDMA/video flow"
    }
    puts "DIGIT_COUNTERS raw_frame=$rf raw_label=[expr {$raw&15}] enhanced_frame=$ef enhanced_label=[expr {$enh&15}]"
    set prior_raw $rf
    set prior_enh $ef
}
puts "DIGIT_JTAG_START_PASS; physical LCD, color, accuracy and stability still require observation"
disconnect
exit
