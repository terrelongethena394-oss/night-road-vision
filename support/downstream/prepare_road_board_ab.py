"""Freeze physical A/B protocol and generate serial RAM-only test scripts."""
from pathlib import Path
import tkinter
from road_integer_common import FLOAT,read,write,sha
from build_road_arm_probe import fnv
ROOT=Path('E:/FPGA_Enhance_Work/road_ab_board_20261027')
Q=Path('E:/FPGA_Enhance_Work/road_q8_board_candidate_20261027')
FP=Path('E:/FPGA_Enhance_Work/road_lcd_static_20261027')

def main():
    fixtures=read(FLOAT/'export_complete.json')['fixtures'];q=read(Q/'offline_complete.json');fp=read(FP/'offline_complete.json')
    configs={'q8':dict(root=str(Q),version=3,weight_fnv=q['weight_fnv32'],model_sha=q['model_sha256'],elf_sha=q['elf_sha256'],source='physical_q8_lcd_framebuffer_jtag_readback'),
       'fp32':dict(root=str(FP),version=2,weight_fnv=1483844061,model_sha=sha(FLOAT/'weights.f32'),elf_sha=fp['elf_sha256'],source='physical_lcd_framebuffer_jtag_readback')}
    write(ROOT/'protocol.json',dict(status='PHYSICAL_AB_PROTOCOL_FROZEN_BEFORE_BATCH_TESTS',configs=configs,fixtures=fixtures,
       numerical='All8 fixed fixtures withheads/decode/NMS/LCD checks. Q8 additionally all86 tensors.',timing='Same6 real photos; each one warmup plus3 timed repetitions, trace disabled. No JTAG photo/weight transfer in measured ARM timer. Report total and network separately.',
       model_order='Q8 first then originalFP32. Leave recommended originalFP32 on display. No claim of randomized thermal control.',
       quality='Use frozen independent480 offline evaluation; these6 board photos are correctness fixtures, not a new accuracy dataset. Never rank quality bynumber ofboxes.',sd_write=False,flash_write=False))
    template=r'''# RAM-only A/B batch. Requires installed matching idle app. No SD/Flash.
set root {@ROOT@}
set app {@APP@}
set version @VERSION@
set weight_fnv @WFNV@
set model {@MODEL@}
set mode {full}
if {$argc>=1} {set mode [lindex $argv 0]}
if {$mode ni {full timing}} {error "mode must be full or timing"}
set out $root/@TAG@_$mode
if {[file exists $out]} {error "Preserve earlier batch results"}
set cases [list @CASES@]
proc word {a} {return [expr {[lindex [mrd -value $a] 0]+0}]}
proc waitseq {wanted} {
 for {set j 0} {$j<3000} {incr j} {
  after 100
  if {[word 0x13800008]==4} {error "Application error [word 0x13800018]"}
  if {[word 0x13800008]==3 && [word 0x13800010]==$wanted} {return}
 }
 error "Application timed out; no next input sent"
}
if {[catch {
 connect -url tcp:127.0.0.1:3121
 targets -set -filter {name =~ "ARM*#0"} -timeout 10
 if {[word 0x13800000]!=0x524F4144 || [word 0x13800004]!=$version || [word 0x13800008]!=3 || [word 0x13800044]!=$weight_fnv} {error "Matching idle app must be installed first"}
 if {$mode eq "full"} {loadhw -hw $app/display.xsa}
 file mkdir $out
 foreach case $cases {
  lassign $case id hash photo kind
  if {$mode eq "timing" && $kind ne "validation"} {continue}
  set caseout $out/$id
  file mkdir $caseout
  dow -data @INPUTS@/$id/input400.u32 0x10000000
  catch {con}
  mwr 0x1380006c $hash
  mwr 0x13800090 $photo
  set repeats [expr {$mode eq "timing" ? 4 : 1}]
  for {set run 0} {$run<$repeats} {incr run} {
   set wanted [expr {[word 0x13800010]+1}]
   set trace [expr {$mode eq "full" && $version==3}]
   mwr 0x13800070 $trace
   mwr 0x1380000c 1
   waitseq $wanted
   if {[word 0x13800040]!=$hash || [word 0x13800044]!=$weight_fnv || [word 0x13800098]!=2 || [word 0x1380008c]!=0} {error "Checksum/display/DMA failure"}
   set n [word 0x1380003c]
   set frame [word 0x13800080]
   if {$n<0 || $n>300 || ($frame!=0x02000000 && $frame!=0x02119400)} {error "Invalid count/frame address"}
   if {$mode eq "timing"} {
    if {[word 0x13800038]!=0 || [word 0x13800070]!=0} {error "Trace must be disabled for timing"}
    mrd -bin -file $caseout/run${run}_mailbox.bin 0x13800000 39
   } else {
    mrd -bin -file $caseout/mailbox.bin 0x13800000 39
    if {$trace} {
     set bytes [word 0x13800038]
     if {$bytes<=0 || $bytes>20000000 || $bytes%4!=0} {error "Invalid trace byte count"}
     mrd -bin -file $caseout/trace.bin 0x14000000 [expr {$bytes/4}]
    }
    mrd -bin -file $caseout/input320.rgb 0x13200000 76800
    mrd -bin -file $caseout/decoded.f32 0x13000000 56700
    @HEADS@
    foreach b {boxes320 boxes400} addr {0x13610000 0x13600000} {
     if {$n>0} {mrd -bin -file $caseout/$b.f32 $addr [expr {$n*6}]} else {close [open $caseout/$b.f32 w]}
    }
    mrd -bin -file $caseout/frame.bgr $frame 288000
    mrd -bin -file $caseout/vdma_regs.bin 0x43000000 12
    set f [open $caseout/context.txt w]
    puts $f "fixture=$id"
    puts $f "source=@SOURCE@"
    puts $f "elf_sha256=@ELF@"
    puts $f "bit_sha256=@BIT@"
    puts $f "weights_sha256=@MODEL@"
    close $f
    set f [open $caseout/job.json w]
    puts $f "\{\"sequence\":$wanted,\"fixture\":\"$id\",\"trace\":$trace\}"
    close $f
   }
   puts "ROAD_AB_JOB @TAG@ $mode $id run=$run sequence=$wanted boxes=$n"
  }
 }
 disconnect
 puts "ROAD_AB_BATCH_COMPLETE @TAG@ $mode"
} why opts]} {
 puts stderr "ROAD_AB_BATCH_FAILED @TAG@ $mode $why"
 if {[dict exists $opts -errorinfo]} {puts stderr [dict get $opts -errorinfo]}
 catch {disconnect}
 exit 1
}
exit 0
'''
    graph=read(FLOAT/'graph.json');heads=[]
    for j,i in enumerate(graph['heads']):
        t=graph['tensors'][i];heads.append(f'mrd -bin -file $caseout/head{j}.f32 {0x12000000+4*t["offset"]} {t["elements"]}')
    cases=' '.join('{'+f'{f["name"]} {fnv((FLOAT/"cases"/f["name"]/"input400.u32").read_bytes())} {at+1} {f["kind"]}'+'}' for at,f in enumerate(fixtures))
    for tag,c in configs.items():
        values=dict(ROOT=ROOT.as_posix(),APP=Path(c['root']).as_posix(),VERSION=str(c['version']),WFNV=str(c['weight_fnv']),MODEL=c['model_sha'],TAG=tag,CASES=cases,
           INPUTS=(Q/'runtime/cases').as_posix(),HEADS='\n    '.join(heads),SOURCE=c['source'],ELF=c['elf_sha'],BIT=q['bit_sha256'])
        script=template
        for k,v in values.items():script=script.replace('@'+k+'@',v)
        assert '@' not in script and int(tkinter.Tcl().call('info','complete',script))==1
        (ROOT/(tag+'_batch.tcl')).write_text(script,encoding='ascii')
    validator=(Q/'validate_readback.py').read_text();validator=validator.replace('ROOT=Path(__file__).resolve().parent',f"ROOT=Path('{Q.as_posix()}')")
    validator=validator.replace('m[4]==1',"m[4]==read(out/'job.json')['sequence']")
    compile(validator,str(ROOT/'validate_q8_ab.py'),'exec');(ROOT/'validate_q8_ab.py').write_text(validator,encoding='utf-8')
    print('ROAD_AB_PROTOCOL_AND_SERIAL_SCRIPTS_READY',flush=True)
if __name__=='__main__':main()
