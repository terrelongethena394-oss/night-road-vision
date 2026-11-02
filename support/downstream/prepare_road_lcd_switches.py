from pathlib import Path
import shutil,tkinter
from road_arm_common import ROOT as NN,read,write,sha
from prepare_road_lcd_static import ROOT
from build_road_arm_probe import fnv
def main():
    cases=[r for r in read(NN/'export_complete.json')['fixtures'] if r['kind']=='validation']
    inputs=ROOT/'inputs';inputs.mkdir(exist_ok=False);metadata=[]
    for index,r in enumerate(cases,1):
        source=NN/'cases'/r['name']/'input400.u32';dest=inputs/f'photo{index:02d}.u32';shutil.copy2(source,dest)
        metadata.append(dict(index=index,fixture=r['name'],source_name=r['source'],timeofday=r['timeofday'],input_file=dest.name,sha256=sha(dest),fnv32=fnv(dest.read_bytes())))
    data=' '.join(str(r['index'])+' {'+r['fixture']+' '+str(r['fnv32'])+'}' for r in metadata)
    interp=tkinter.Tcl();case_dict=interp.eval('dict create '+data)
    assert int(interp.call('dict','size',case_dict))==6
    assert str(interp.call('dict','get',case_dict,'4')).startswith(metadata[3]['fixture'])
    script=r'''# Switch input in the existing LCD app. No CPU/FPGA reset and no SD access.
set root [file dirname [file normalize [info script]]]
if {$argc<1 || $argc>2} {error "Usage: switch_photo.tcl PHOTO_INDEX ?READBACK_DIRECTORY?"}
set photo [lindex $argv 0]
set cases [dict create @CASES@]
if {![dict exists $cases $photo]} {error "PHOTO_INDEX must be1..6"}
lassign [dict get $cases $photo] id expected
set verify [expr {$argc==2}]
if {$verify} {
 set out [file normalize [lindex $argv 1]]
 if {[file exists $out]} {error "Readback directory exists; choose a new one"}
}
proc word {a} {return [expr {[lindex [mrd -value $a] 0]+0}]}
if {[catch {
 connect -url tcp:127.0.0.1:3121
 targets -set -filter {name =~ "ARM*#0"} -timeout 10
 if {[word 0x13800000]!=0x524F4144 || [word 0x13800004]!=2 || [word 0x13800008]!=3 || [word 0x13800044]!=@WFNV@} {error "LCD app is not idle/ready; load its RAM installer first"}
 if {$verify} {loadhw -hw $root/display.xsa}
 set wanted [expr {[word 0x13800010]+1}]
 dow -data $root/inputs/photo[format %02d $photo].u32 0x10000000
 catch {con}
 mwr 0x1380006c $expected
 mwr 0x13800090 $photo
 mwr 0x13800070 0
 mwr 0x1380000c 1
 set done 0
 for {set i 0} {$i<1200} {incr i} {
  after 250
  if {[word 0x13800008]==4} {error "LCD app error [word 0x13800018]"}
  if {[word 0x13800008]==3 && [word 0x13800010]==$wanted} {set done 1;break}
 }
 if {!$done} {error "New photo timed out; do not overwrite busy inputs"}
 if {[word 0x13800040]!=$expected || [word 0x13800044]!=@WFNV@ || [word 0x13800098]!=2 || [word 0x1380008c]!=0} {error "Hash, display or DMA check failed"}
 set count [word 0x1380003c]
 set frame [word 0x13800080]
 if {$count<0 || $count>300 || ($frame!=0x02000000 && $frame!=0x02119400)} {error "Invalid count or frame address"}
 if {$verify} {
  file mkdir $out
  mrd -bin -file $out/mailbox.bin 0x13800000 39
  mrd -bin -file $out/decoded.f32 0x13000000 56700
  mrd -bin -file $out/input320.rgb 0x13200000 76800
  @HEADS@
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
  puts $f "elf_sha256=@ELF@"
  puts $f "bit_sha256=@BIT@"
  puts $f "weights_sha256=@WEIGHTS@"
  close $f
 }
 disconnect
 puts "ROAD_LCD_PHOTO_SWITCH_COMPLETE photo=$photo boxes=$count"
} failure opts]} {
 puts stderr "ROAD_LCD_PHOTO_SWITCH_FAILED: $failure"
 if {[dict exists $opts -errorinfo]} {puts stderr [dict get $opts -errorinfo]}
 catch {disconnect}
 exit 1
}
exit 0
'''
    g=read(NN/'graph.json');head=[]
    for j,i in enumerate(g['heads']):
        t=g['tensors'][i];head.append(f'mrd -bin -file $out/head{j}.f32 {0x12000000+4*t["offset"]} {t["elements"]}')
    o=read(ROOT/'offline_complete.json')
    for k,v in dict(CASES=data,WFNV=str(read(NN/'arm_compile_complete_r2.json')['weight_fnv32']),HEADS='\n  '.join(head),ELF=o['elf_sha256'],BIT=o['bit_sha256'],WEIGHTS=o['weights_sha256']).items():script=script.replace('@'+k+'@',v)
    assert '@' not in script and int(tkinter.Tcl().call('info','complete',script))==1
    (ROOT/'switch_photo.tcl').write_text(script,encoding='ascii')
    xsct=r'E:\Xilinx\Vitis\2020.2\bin\xsct.bat'
    for r in metadata:
        n=r['index'];s='@echo off\r\ncall "'+xsct+'" "%~dp0switch_photo.tcl" '+str(n)+' > "%~dp0switch_'+str(n)+'.log" 2>&1\r\ntype "%~dp0switch_'+str(n)+'.log"\r\nfindstr /C:"ROAD_LCD_PHOTO_SWITCH_COMPLETE" "%~dp0switch_'+str(n)+'.log" >nul\r\nif errorlevel 1 echo FAILED: See the log above. No SD card files were changed.\r\npause\r\n'
        (ROOT/f'{n:02d}_photo.cmd').write_bytes(s.encode('ascii'))
    write(ROOT/'photos.json',metadata)
    # A portable RAM installer bundle; the current working installer is preserved.
    bundle=ROOT/'runtime';(bundle/'cases').mkdir(parents=True)
    shutil.copy2(NN/'weights.f32',bundle/'weights.f32')
    for r in read(NN/'export_complete.json')['fixtures']:
        (bundle/'cases'/r['name']).mkdir();shutil.copy2(NN/'cases'/r['name']/'input400.u32',bundle/'cases'/r['name']/'input400.u32')
    installer=(ROOT/'download_lcd.tcl').read_text(encoding='ascii')
    installer=installer.replace('set root {'+ROOT.as_posix()+'}','set root [file dirname [file normalize [info script]]]')
    installer=installer.replace('set nn {'+NN.as_posix()+'}','set nn $root/runtime')
    installer=installer.replace('set out $root/board_$id','set out $root/install_readback_${id}_[clock milliseconds]')
    assert int(tkinter.Tcl().call('info','complete',installer))==1
    (ROOT/'install_ram.tcl').write_text(installer,encoding='ascii')
    s='@echo off\r\ncall "'+xsct+'" "%~dp0install_ram.tcl" > "%~dp0install_ram.log" 2>&1\r\ntype "%~dp0install_ram.log"\r\nfindstr /C:"ROAD_LCD_PHYSICAL_READBACK_COMPLETE" "%~dp0install_ram.log" >nul\r\nif errorlevel 1 echo FAILED: See the log above. No SD card files were changed.\r\npause\r\n'
    (ROOT/'00_install_ram.cmd').write_bytes(s.encode('ascii'))
    write(ROOT/'switch_tools.json',dict(status='SIX_FROZEN_REAL_PHOTO_SWITCH_TOOLS_PREPARED',switch_sha256=sha(ROOT/'switch_photo.tcl'),installer_sha256=sha(ROOT/'install_ram.tcl'),sd_written=False))
    print('ROAD_LCD_SIX_PHOTO_SWITCHES_READY',flush=True)
if __name__=='__main__':main()
