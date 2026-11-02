"""Reuse verified loaded r2 firmware; vary only frozen input photographs."""
from pathlib import Path
import tkinter
from road_arm_common import ROOT,read,write,sha
from build_road_arm_probe import fnv
def main():
    arm=read(ROOT/'arm_compile_complete_r2.json');g=read(ROOT/'graph.json');fixtures=read(ROOT/'export_complete.json')['fixtures']
    folder=Path(arm['elf']).parent;inputs=' '.join('{'+r['name']+' '+str(fnv((ROOT/'cases'/r['name']/'input400.u32').read_bytes()))+'}' for r in fixtures)
    script=r'''# No CPU reset or firmware download. Requires the already validated r2 probe.
set root {@ROOT@}
set out $root/board_batch_r2
if {[file exists $out]} {error "Batch directory already exists; preserve it"}
proc word {a} {return [expr {[lindex [mrd -value $a] 0]+0}]}
proc waitseq {wanted} {
 for {set i 0} {$i<1200} {incr i} {
  after 250
  if {[word 0x13800008]==4} {error "ARM error [word 0x13800018]"}
  if {[word 0x13800008]==3 && [word 0x13800010]==$wanted} {return}
 }
 error "Probe sequence timeout"
}
if {[catch {
 connect -url tcp:127.0.0.1:3121
 targets -set -filter {name =~ "ARM*#0"} -timeout 10
 if {[word 0x13800000]!=0x524F4144 || [word 0x13800004]!=1 || [word 0x13800008]!=3 || [word 0x13800044]!=@WFNV@} {error "Expected loaded idle road probe"}
 file mkdir $out
 foreach item {@INPUTS@} {
  lassign $item id expected
  set d $out/$id
  file mkdir $d
  set wanted [expr {[word 0x13800010]+1}]
  dow -data $root/cases/$id/input400.u32 0x10000000
  catch {con}
  mwr 0x1380006c $expected
  mwr 0x13800070 0
  mwr 0x1380000c 1
  waitseq $wanted
  if {[word 0x13800040]!=$expected || [word 0x13800044]!=@WFNV@} {error "Fixture input/weight hash mismatch"}
  set n [word 0x1380003c]
  if {$n<0 || $n>300} {error "Invalid detection count"}
  mrd -bin -file $d/mailbox.bin 0x13800000 30
  mrd -bin -file $d/input320.rgb 0x13200000 76800
  mrd -bin -file $d/decoded.f32 0x13000000 56700
  @HEAD_READS@
  if {$n>0} {
   mrd -bin -file $d/boxes320.f32 0x13610000 [expr {$n*6}]
   mrd -bin -file $d/boxes400.f32 0x13600000 [expr {$n*6}]
  } else {
   close [open $d/boxes320.f32 w]
   close [open $d/boxes400.f32 w]
  }
  set f [open $d/context.txt w]
  puts $f "fixture=$id"
  puts $f "elf_sha256=@ELF_SHA@"
  puts $f "weights_sha256=@WEIGHT_SHA@"
  puts $f "source=physical_jtag_batch_readback"
  close $f
  puts "ROAD_PHYSICAL_BATCH_CASE_COMPLETE $id boxes=$n"
 }
 disconnect
 puts "ROAD_PHYSICAL_BATCH_READBACK_COMPLETE $out"
} failure opts]} {
 puts stderr "ROAD_PHYSICAL_BATCH_FAILED: $failure"
 if {[dict exists $opts -errorinfo]} {puts stderr [dict get $opts -errorinfo]}
 catch {disconnect}
 exit 1
}
exit 0
'''
    heads=[]
    for j,i in enumerate(g['heads']):
        t=g['tensors'][i];heads.append(f'mrd -bin -file $d/head{j}.f32 {0x12000000+t["offset"]*4} {t["elements"]}')
    for key,value in dict(ROOT=ROOT.as_posix(),INPUTS=inputs,WFNV=str(arm['weight_fnv32']),ELF_SHA=arm['elf_sha256'],WEIGHT_SHA=sha(ROOT/'weights.f32'),HEAD_READS='\n  '.join(heads)).items():script=script.replace('@'+key+'@',value)
    assert '@' not in script and int(tkinter.Tcl().call('info','complete',script))==1
    path=folder/'batch_probe.tcl';path.write_text(script,encoding='ascii');write(ROOT/'batch_tools.json',dict(script=str(path),sha256=sha(path),fixtures=fixtures,
         elf_sha256=arm['elf_sha256'],note='Will use existing r2 firmware after the single-case full-layer validation. No SD writes.'))
    print('ROAD_PHYSICAL_BATCH_TOOLS_READY',flush=True)
if __name__=='__main__':main()
