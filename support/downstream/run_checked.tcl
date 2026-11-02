# XSCT2020.2's Windows batch launcher may return0 even after Tcl exit1.
# Format errors explicitly; the CMD launcher additionally checks the unique
# successful firmware-start marker in its new log, never just process exitcode.
if {$argc != 1} {
 puts stderr "Usage: run_checked.tcl SCRIPT"
 exit 2
}
set selected_script [file normalize [lindex $argv 0]]
if {[catch {source $selected_script} failure failure_options]} {
 puts stderr "SCRIPT_FAILED: $failure"
 if {[dict exists $failure_options -errorinfo]} {puts stderr [dict get $failure_options -errorinfo]}
 exit 1
}
exit 0
