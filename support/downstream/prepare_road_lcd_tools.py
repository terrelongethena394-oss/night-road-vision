from pathlib import Path
import tkinter
from road_arm_common import ROOT as NN,read,write,sha
from prepare_road_lcd_static import ROOT
from build_road_arm_probe import fnv
def main():
    offline=read(ROOT/'offline_complete.json');assert sha(ROOT/'road_lcd.elf')==offline['elf_sha256']
    cases=read(NN/'export_complete.json')['fixtures'];inputs=' '.join(f'{r["name"]} {fnv((NN/"cases"/r["name"]/"input400.u32").read_bytes())}' for r in cases)
    head=[];graph=read(NN/'graph.json')
    for j,i in enumerate(graph['heads']):
        t=graph['tensors'][i];head.append(f'mrd -bin -file $out/head{j}.f32 {0x12000000+4*t["offset"]} {t["elements"]}')
    template=r'''# Fixed image LCD display. JTAG RAM configuration only, no SD/flash writes.
set root {@ROOT@}
set nn {@NN@}
set id {@FIRST@}
set photo 1
if {$argc>=1} {set id [lindex $argv 0]}
if {$argc>=2} {set photo [lindex $argv 1]}
set out $root/board_$id
if {$argc>=3} {set out [file normalize [lindex $argv 2]]}
if {[file exists $out]} {error "Readback directory exists; choose a new one"}
set input_hashes [dict create @HASHES@]
if {![dict exists $input_hashes $id]} {error "Unknown frozen input"}
proc word {a} {return [expr {[lindex [mrd -value $a] 0]+0}]}
proc waitseq {wanted} {
 for {set i 0} {$i<1200} {incr i} {
  after 250
  if {[word 0x13800008]==4} {error "LCD application error [word 0x13800018]"}
  if {[word 0x13800008]==3 && [word 0x13800010]==$wanted} {return}
 }
 error "LCD application timeout"
}
if {[catch {
 connect -url tcp:127.0.0.1:3121
 puts [targets]
 targets -set -filter {name =~ "APU*"} -timeout 10
 rst -system
 after 1000
 puts "ROAD_LCD_STAGE configuring_known_display_bit"
 fpga -file $root/display.bit
 targets -set -filter {name =~ "ARM*#0"} -timeout 10
 source $root/ps7_init.tcl
 ps7_init
 ps7_post_config
 loadhw -hw $root/display.xsa
 dow $root/road_lcd.elf
 con
 set ready 0
 for {set i 0} {$i<160} {incr i} {
  after 250
  if {[word 0x13800000]==0x524F4144 && [word 0x13800004]==2} {
   if {[word 0x13800008]==4} {error "LCD initialization error [word 0x13800018], LCDid=[word 0x13800078]"}
   if {[word 0x13800008]==1 && [word 0x13800098]==1} {set ready 1;break}
  }
 }
 if {!$ready} {error "LCD application did not become ready"}
 puts "ROAD_LCD_STAGE waiting_for_image lcd=[word 0x13800078]"
 file mkdir $out
 dow -data $nn/cases/$id/input400.u32 0x10000000
 catch {con}
 mwr 0x1380006c [dict get $input_hashes $id]
 mwr 0x13800070 0
 mwr 0x13800090 $photo
 mwr 0x1380000c 1
 # The new application verifies any retained DDR weights before it uses them.
 if {[catch {waitseq 1} failure]} {
  if {[word 0x13800018]!=10} {error $failure}
  puts "ROAD_LCD_STAGE refreshing_weights"
  dow -data $nn/weights.f32 0x11000000
  catch {con}
  mwr 0x1380000c 1
  waitseq 1
 }
 if {[word 0x13800040]!=[dict get $input_hashes $id] || [word 0x13800044]!=@WFNV@} {error "Input/weight checksum mismatch"}
 if {[word 0x13800098]!=2 || [word 0x1380008c]!=0 || [word 0x13800078]!=0x7084} {error "Invalid LCD completion or DMA error"}
 set count [word 0x1380003c]
 set frame [word 0x13800080]
 if {$count<0 || $count>300 || ($frame!=0x02000000 && $frame!=0x02119400)} {error "Invalid count/frame pointer"}
 puts "ROAD_LCD_STAGE picture_presented boxes=$count frame=$frame"
 mrd -bin -file $out/mailbox.bin 0x13800000 39
 mrd -bin -file $out/decoded.f32 0x13000000 56700
 mrd -bin -file $out/input320.rgb 0x13200000 76800
 @HEAD_READS@
 if {$count>0} {
  mrd -bin -file $out/boxes320.f32 0x13610000 [expr {$count*6}]
  mrd -bin -file $out/boxes400.f32 0x13600000 [expr {$count*6}]
 } else {
  close [open $out/boxes320.f32 w]
  close [open $out/boxes400.f32 w]
 }
 mrd -bin -file $out/frame.bgr $frame 288000
 mrd -bin -file $out/vdma_regs.bin 0x43000000 12
 set f [open $out/context.txt w]
 puts $f "fixture=$id"
 puts $f "source=physical_lcd_framebuffer_jtag_readback"
 puts $f "elf_sha256=@ELF_SHA@"
 puts $f "bit_sha256=@BIT_SHA@"
 puts $f "weights_sha256=@WEIGHT_SHA@"
 close $f
 disconnect
 puts "ROAD_LCD_PHYSICAL_READBACK_COMPLETE $out"
} failure options]} {
 puts stderr "ROAD_LCD_FAILED: $failure"
 if {[dict exists $options -errorinfo]} {puts stderr [dict get $options -errorinfo]}
 catch {disconnect}
 exit 1
}
exit 0
'''
    values=dict(ROOT=ROOT.as_posix(),NN=NN.as_posix(),FIRST=cases[0]['name'],HASHES=inputs,WFNV=str(read(NN/'arm_compile_complete_r2.json')['weight_fnv32']),
         HEAD_READS='\n '.join(head),ELF_SHA=offline['elf_sha256'],BIT_SHA=offline['bit_sha256'],WEIGHT_SHA=offline['weights_sha256'])
    for key,value in values.items():template=template.replace('@'+key+'@',value)
    assert '@' not in template and int(tkinter.Tcl().call('info','complete',template))==1
    script=ROOT/'download_lcd.tcl';script.write_text(template,encoding='ascii')
    write(ROOT/'download_tools.json',dict(script=str(script),script_sha256=sha(script),input_fnv={r['name']:fnv((NN/'cases'/r['name']/'input400.u32').read_bytes()) for r in cases},
         bit_sha256=offline['bit_sha256'],elf_sha256=offline['elf_sha256'],sd_written=False))
    print('ROAD_STATIC_LCD_DOWNLOAD_READY',flush=True)
if __name__=='__main__':main()
