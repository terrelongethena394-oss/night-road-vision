"""Prepare a concrete, checksummed fixed-image JTAG probe and readback contract."""
from pathlib import Path
import shutil,sys
from road_arm_common import ROOT,read,write,sha
from build_road_arm_probe import fnv
def main():
    revision='r2' if 'r2' in sys.argv else 'r1'
    arm=read(ROOT/('arm_compile_complete_'+revision+'.json'));folder=Path(arm['elf']).parent
    assert sha(arm['elf'])==arm['elf_sha256']
    shutil.copy2('E:/FPGA_Enhance_Work/multinex_fast_static_r4d_20261026/ps7_init.tcl',folder/'ps7_init.tcl')
    fixtures=read(ROOT/'export_complete.json')['fixtures'];hashes={r['name']:fnv((ROOT/'cases'/r['name']/'input400.u32').read_bytes()) for r in fixtures}
    template=r'''# Fixed-image probe: resets the ARM application, writes RAM only; NO SD/flash access.
# Output is NOT evidence until validate_road_arm_probe.py accepts it.
set root {@ROOT@}
set arm {@ARM@}
set id {@FIRST@}
if {$argc>=1} {set id [lindex $argv 0]}
set input_hashes [dict create @HASHES@]
if {![dict exists $input_hashes $id]} {error "Unknown frozen fixture $id"}
set out $root/board_readback@REV_SUFFIX@_$id
if {$argc>=2} {set out [file normalize [lindex $argv 1]]}
if {[file exists $out]} {error "Readback directory already exists; choose a new output directory"}
proc word {address} {return [expr {[lindex [mrd -value $address] 0]+0}]}
proc wait_done {} {
 set began [clock milliseconds]
 for {set i 0} {$i<1200} {incr i} {
  after 250
  set state [word 0x13800008]
  if {$state==4} {error "ARM probe error [word 0x13800018]"}
  if {$state==3} {return}
 }
 error "ARM probe timeout; do not overwrite inputs while a job is running"
}
if {[catch {
 connect -url tcp:127.0.0.1:3121
 puts [targets]
 targets -set -filter {name =~ "APU*"} -timeout 10
 rst -system
 after 1000
 targets -set -filter {name =~ "ARM*#0"} -timeout 10
 catch {stop}
 source $arm/ps7_init.tcl
 ps7_init
 ps7_post_config
 dow $arm/road_probe.elf
 con
 set ready 0
 for {set i 0} {$i<120} {incr i} {
  after 250
  if {[word 0x13800000]==0x524F4144 && [word 0x13800004]==1 && [word 0x13800008]==1} {set ready 1;break}
 }
 if {!$ready} {error "Wrong probe mailbox or ARM did not start"}
 file mkdir $out
 puts "ROAD_PROBE_STAGE ready_loading_weights"
 dow -data $root/weights.f32 0x11000000
 dow -data $root/cases/$id/input400.u32 0x10000000
 catch {con}
 mwr 0x1380006c [dict get $input_hashes $id]
 mwr 0x13800070 1
 mwr 0x1380000c 1
 wait_done
 if {[word 0x13800040]!=[dict get $input_hashes $id] || [word 0x13800044]!=@WFNV@} {error "Input/weight checksum mismatch"}
 if {[word 0x13800038]!=@TRACE_BYTES@} {error "Unexpected full-layer trace size"}
 set count [word 0x1380003c]
 if {$count<0 || $count>300} {error "Invalid detector count"}
 puts "ROAD_PROBE_STAGE inference_done_reading_all_layers boxes=$count"
 mrd -bin -file $out/mailbox.bin 0x13800000 30
 mrd -bin -file $out/input320.rgb 0x13200000 76800
 mrd -bin -file $out/decoded.f32 0x13000000 56700
 if {$count>0} {
  mrd -bin -file $out/boxes320.f32 0x13610000 [expr {$count*6}]
  mrd -bin -file $out/boxes400.f32 0x13600000 [expr {$count*6}]
 } else {
  close [open $out/boxes320.f32 w]
  close [open $out/boxes400.f32 w]
 }
 mrd -bin -file $out/all_layers.f32 0x14000000 @TRACE_WORDS@
 # Repeat without trace copies. Times exclude JTAG transfers and camera/display.
 mwr 0x13800070 0
 for {set j 1} {$j<=3} {incr j} {
  mwr 0x1380000c 1
  wait_done
  mrd -bin -file $out/timing$j.bin 0x13800000 30
  puts "ROAD_PROBE_TIMING_DONE $j"
 }
 set f [open $out/context.txt w]
 puts $f "fixture=$id"
 puts $f "elf_sha256=@ELF_SHA@"
 puts $f "weights_sha256=@WEIGHT_SHA@"
 puts $f "source=physical_jtag_readback"
 puts $f "revision=@REVISION@"
 close $f
 disconnect
 puts "ROAD_FIXED_PROBE_READBACK_COMPLETE $out"
} failure options]} {
 puts stderr "ROAD_FIXED_PROBE_FAILED: $failure"
 if {[dict exists $options -errorinfo]} {puts stderr [dict get $options -errorinfo]}
 catch {disconnect}
 exit 1
}
exit 0
'''
    substitutions={'ROOT':ROOT.as_posix(),'ARM':folder.as_posix(),'FIRST':fixtures[0]['name'],
          'HASHES':' '.join(f'{k} 0x{v:08x}' for k,v in hashes.items()),'WFNV':str(arm['weight_fnv32']),
          'TRACE_BYTES':str(arm['trace_bytes']),'TRACE_WORDS':str(arm['trace_bytes']//4),
          'ELF_SHA':arm['elf_sha256'],'WEIGHT_SHA':sha(ROOT/'weights.f32'),'REVISION':revision,'REV_SUFFIX':'_r2' if revision=='r2' else ''}
    for k,v in substitutions.items():template=template.replace('@'+k+'@',v)
    assert '@' not in template
    script=folder/'download_probe.tcl';script.write_text(template,encoding='ascii')
    import tkinter
    assert int(tkinter.Tcl().call('info','complete',template))==1
    write(ROOT/('probe_tools_r2.json' if revision=='r2' else 'probe_tools.json'),dict(status='JTAG_SCRIPT_PREPARED_AND_TCL_SYNTAX_COMPLETE_NOT_HARDWARE_EXECUTED',script=str(script),script_sha256=sha(script),
         elf_sha256=arm['elf_sha256'],weights_sha256=sha(ROOT/'weights.f32'),fixture_input_fnv=hashes,trace_bytes=arm['trace_bytes'],
         resets_arm_application=True,writes_only_ddr=True,sd_written=False))
    print('ROAD_PROBE_DOWNLOAD_TOOLS_READY',script,flush=True)
if __name__=='__main__':main()
