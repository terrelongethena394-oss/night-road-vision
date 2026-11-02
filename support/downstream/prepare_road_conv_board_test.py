"""Prepare a future JTAG RAM test, NEVER execute it. Current camera stays untouched."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path('E:/FPGA_Enhance_Work/road_conv_board_20261027')
HLS=Path('E:/FPGA_Enhance_Work/road_conv_hls_20261027')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def fnv(b):
    h=2166136261
    for v in b:h=((h^v)*16777619)&0xffffffff
    return h
def main():
    proof=json.loads((ROOT/'arm_probe/compile_complete.json').read_text());assert sha(proof['elf'])==proof['elf_sha256']
    out=ROOT/'future_board_test';out.mkdir(exist_ok=False)
    fixtures=[];entries=[]
    for case in json.loads((HLS/'fixtures.json').read_text()):
        folder=HLS/'fixtures'/case['name']
        r={k:case[k] for k in ['name','h','w','ic4','oc4','stride']}
        r.update(input=str(folder/'input.f32'),packed=str(folder/'packed_p8.f32'),expected=str(folder/'expected.f32'))
        r.update(input_fnv32=fnv(Path(r['input']).read_bytes()),packed_fnv32=fnv(Path(r['packed']).read_bytes()),files_sha256={k:sha(r[k]) for k in ['input','packed','expected']})
        r['output_words']=((r['h']+r['stride']-1)//r['stride'])*((r['w']+r['stride']-1)//r['stride'])*r['oc4']
        fixtures.append(r)
        entries.append('{%s} {%d %d %d %d %d %d %d %d}'%(r['name'],r['h'],r['w'],r['ic4'],r['oc4'],r['stride'],r['input_fnv32'],r['packed_fnv32'],r['output_words']))
    (out/'fixtures.json').write_text(json.dumps(fixtures,indent=2),encoding='utf-8')
    template=r'''# FUTURE TEST ONLY. This resets the board and replaces the running camera in RAM.
# No SD/flash writes. Do not run before offline_acceptance.json exists and hashes pass.
set root {@ROOT@}
set source_root {@HLS@}
if {![info exists ::env(ROAD_CONV_PREFLIGHT_OK)] || $::env(ROAD_CONV_PREFLIGHT_OK) ne "1"} {error "Use road_conv_preflight.py --execute after preparing the board; artifact hashes must be verified first"}
set cases [dict create @CASES@]
if {$argc!=1} {error "Specify a NEW absolute readback directory"}
set out [file normalize [lindex $argv 0]]
if {[file exists $out]} {error "Readback directory already exists"}
foreach f {offline_acceptance.json road_conv.bit road_conv.xsa future_board_test/ps7_init.tcl arm_probe/road_conv_probe.elf} {
 if {![file exists $root/$f]} {error "Missing accepted artifact: $f"}
}
proc word {a} {return [expr {[lindex [mrd -value $a] 0]+0}]}
if {[catch {
 connect -url tcp:127.0.0.1:3121
 puts [targets]
 targets -set -filter {name =~ "APU*"} -timeout 10
 rst -system
 after 1000
 targets -set -filter {name =~ "ARM*#0"} -timeout 10
 catch {stop}
 # Program the matching test bit BEFORE any driver access at 0x43C30000.
 fpga -file $root/road_conv.bit
 source $root/future_board_test/ps7_init.tcl
 ps7_init
 ps7_post_config
 dow $root/arm_probe/road_conv_probe.elf
 con
 set ready 0
 for {set i 0} {$i<100} {incr i} {
  after 100
  if {[word 0x1F000000]==0x52435033 && [word 0x1F000004]==1 && [word 0x1F000008]==1} {set ready 1;break}
 }
 if {!$ready} {error "Convolution probe did not reach ready state"}
 file mkdir $out
 set sequence 0
 dict for {name shape} $cases {
  lassign $shape h w ic oc stride input_hash packed_hash output_words
  set folder $out/$name
  file mkdir $folder
  # Stop only this isolated test app while replacing fixture buffers.
  stop
  dow -data $source_root/fixtures/$name/input.f32 0x10000000
  dow -data $source_root/fixtures/$name/packed_p8.f32 0x18000000
  foreach {offset value} [list 28 $h 32 $w 36 $ic 40 $oc 44 $stride 48 $input_hash 52 $packed_hash] {
   mwr [expr {0x1F000000+$offset}] $value
  }
  mwr 0x1F000008 1
  mwr 0x1F00000C 1
  con
  set done 0
  for {set i 0} {$i<600} {incr i} {
   after 100
   set state [word 0x1F000008]
   if {$state==4} {error "Convolution fixture $name failed, error=[word 0x1F000014]"}
   if {$state==3} {set done 1;break}
  }
  if {!$done} {error "Convolution fixture $name timeout"}
  incr sequence
  if {[word 0x1F000010]!=$sequence || [word 0x1F000044]!=$output_words} {error "Wrong fixture sequence/output length"}
  stop
  mrd -bin -file $folder/mailbox.bin 0x1F000000 64
  mrd -bin -file $folder/cpu.f32 0x1A000000 $output_words
  mrd -bin -file $folder/pl.f32 0x19000000 $output_words
  mrd -bin -file $folder/input.f32 0x10000000 [expr {$h*$w*$ic}]
  mrd -bin -file $folder/packed.f32 0x18000000 [expr {$oc*(9*$ic+1)}]
  con
  puts "ROAD_CONV_FIXTURE_READBACK $name sequence=$sequence"
 }
 set f [open $out/context.txt w]
 puts $f "source=physical_jtag_readback"
 puts $f "elf_sha256=@ELF@"
 puts $f "timings=one_warmup_then_three_runs; no_camera_or_vdma_traffic"
 puts $f "sd_written=false"
 close $f
 disconnect
 puts "ROAD_CONV_BOARD_READBACK_COMPLETE $out"
} failure options]} {
 puts stderr "ROAD_CONV_BOARD_TEST_FAILED: $failure"
 if {[dict exists $options -errorinfo]} {puts stderr [dict get $options -errorinfo]}
 catch {disconnect}
 exit 1
}
'''
    for a,b in {'@ROOT@':ROOT.as_posix(),'@HLS@':HLS.as_posix(),'@CASES@':' '.join(entries),'@ELF@':proof['elf_sha256']}.items():template=template.replace(a,b)
    (out/'run_future_ram_test.tcl').write_text(template,encoding='ascii')
    shutil.copy2(Path(__file__).resolve().parent/'validate_road_conv_board.py',out/'validate_road_conv_board.py')
    shutil.copy2(Path(__file__).resolve().parent/'road_conv_preflight.py',out/'road_conv_preflight.py')
    (out/'prepared.json').write_text(json.dumps(dict(status='PREPARED_NOT_EXECUTED',fixtures=len(fixtures),hardware_access=False,sd_written=False,elf_sha256=proof['elf_sha256']),indent=2),encoding='utf-8')
    print('ROAD_CONV_FUTURE_TEST_PREPARED_NOT_EXECUTED',len(fixtures))
if __name__=='__main__':main()
