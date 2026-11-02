from pathlib import Path
import shutil,json,zlib,tkinter
from road_arm_common import read,write,sha
from prepare_road_sd import ROOT
def main():
    o=read(ROOT/'boot_image_validation.json');first=o['first_fixture'];out=ROOT/'auto_app_readback'
    script=r'''# Test only the self-contained app, using already configured known PL.
# No dow-data of weights/input and no command trigger are permitted here.
set root {@ROOT@}
set out $root/auto_app_readback
if {[file exists $out]} {error "Preserve previous readback"}
proc word {a} {return [expr {[lindex [mrd -value $a] 0]+0}]}
if {[catch {
 connect -url tcp:127.0.0.1:3121
 targets -set -filter {name =~ "ARM*#0"} -timeout 10
 stop
 rst -processor
 dow $root/road_sd.elf
 con
 loadhw -hw $root/display.xsa
 set ready 0
 for {set i 0} {$i<1200} {incr i} {
  after 250
  if {[word 0x13800000]==0x524F4144 && [word 0x13800004]==2} {
   if {[word 0x13800008]==4} {error "Self-contained app error [word 0x13800018]"}
   if {[word 0x13800008]==3 && [word 0x13800098]==2 && [word 0x1380009c]==0x53444231 && [word 0x13800010]==1} {set ready 1;break}
  }
 }
 if {!$ready} {error "Embedded data auto-start timeout"}
 set n [word 0x1380003c]
 set frame [word 0x13800080]
 if {$n<0 || $n>300 || ($frame!=0x02000000 && $frame!=0x02119400)} {error "Invalid frame/count"}
 file mkdir $out
 mrd -bin -file $out/mailbox.bin 0x13800000 39
 mrd -bin -file $out/auto_flag.bin 0x1380009c 1
 mrd -bin -file $out/input320.rgb 0x13200000 76800
 mrd -bin -file $out/decoded.f32 0x13000000 56700
 @HEADS@
 if {$n>0} {
  mrd -bin -file $out/boxes320.f32 0x13610000 [expr {$n*6}]
  mrd -bin -file $out/boxes400.f32 0x13600000 [expr {$n*6}]
 } else {
  close [open $out/boxes320.f32 w]
  close [open $out/boxes400.f32 w]
 }
 mrd -bin -file $out/frame.bgr $frame 288000
 mrd -bin -file $out/vdma_regs.bin 0x43000000 12
 set f [open $out/context.txt w]
 puts $f "fixture=@FIRST@"
 puts $f "source=physical_lcd_framebuffer_jtag_readback"
 puts $f "elf_sha256=@ELF@"
 puts $f "bit_sha256=@BIT@"
 puts $f "weights_sha256=@WEIGHTS@"
 close $f
 disconnect
 puts "ROAD_EMBEDDED_APP_AUTOSTART_PHYSICAL_READBACK_COMPLETE boxes=$n NO_EXTRA_WEIGHT_INPUT_OR_COMMAND_UPLOAD"
} why opts]} {
 puts stderr "ROAD_EMBEDDED_AUTOSTART_FAILED $why"
 if {[dict exists $opts -errorinfo]} {puts stderr [dict get $opts -errorinfo]}
 catch {disconnect}
 exit 1
}
exit 0
'''
    nn=Path('E:/FPGA_Enhance_Work/road_arm_prototype_20261026');g=read(nn/'graph.json');heads=[]
    for j,i in enumerate(g['heads']):
        t=g['tensors'][i];heads.append(f'mrd -bin -file $out/head{j}.f32 {0x12000000+4*t["offset"]} {t["elements"]}')
    for k,v in dict(ROOT=ROOT.as_posix(),HEADS='\n '.join(heads),FIRST=first,ELF=o['elf_sha256'],BIT=o['bit_sha256'],WEIGHTS=o['weights_sha256']).items():script=script.replace('@'+k+'@',v)
    assert '@' not in script and 'dow -data' not in script and int(tkinter.Tcl().call('info','complete',script))==1
    (ROOT/'test_autostart.tcl').write_text(script,encoding='ascii')
    # Reuse the exact already board-tested FatFs helper. Its16MiB limit covers this image.
    previous=Path('E:/FPGA_Enhance_Work/plate_sd_20261026/jtag_writer');writer=ROOT/'jtag_writer';writer.mkdir(exist_ok=False)
    old=read(previous/'writer.json');assert sha(previous/'sd_jtag_writer.elf')==old['elf_sha256']
    for name in ['sd_jtag_writer.elf','sd_jtag_writer.c','lscript.ld','Xilinx.spec','build.log','sd_common.tcl']:shutil.copy2(previous/name,writer/name)
    boot=(ROOT/'BOOT.BIN').read_bytes();assert len(boot)<=old['limit']
    metadata=dict(old);metadata.update(status='REUSED_BYTE_IDENTICAL_PREVIOUSLY_PHYSICAL_HELPER',boot_sha256=sha(ROOT/'BOOT.BIN'),boot_bytes=len(boot),boot_crc32=zlib.crc32(boot));write(writer/'writer.json',metadata)
    (writer/'boot_transfer.tcl').write_text(f'set boot_bytes {len(boot)}\nset boot_crc {zlib.crc32(boot)}\n',encoding='ascii')
    for name in ['probe_card.tcl','stage_card.tcl','commit_card.tcl']:
        code=(previous/name).read_text();code=code.replace('$root/../../camera_plate_guarded_20261026/camera.bit','$root/../display.bit').replace('$root/../../camera_plate_guarded_20261026/camera.xsa','$root/../display.xsa').replace('$root/../../camera_plate_guarded_20261026/ps7_init.tcl','$root/../ps7_init.tcl')
        # Preserve unique positive markers. Wrap errors because XSCT may return0.
        lines=code.splitlines();assert lines[-1]=='exit';body='\n'.join(lines[:-1])
        wrapped='if {[catch {\n'+body+'\n} why opts]} {\n puts stderr "ROAD_SD_OPERATION_FAILED: $why"\n if {[dict exists $opts -errorinfo]} {puts stderr [dict get $opts -errorinfo]}\n catch {disconnect}\n exit 1\n}\nexit 0\n'
        assert int(tkinter.Tcl().call('info','complete',wrapped))==1;(writer/name).write_text(wrapped,encoding='ascii')
    verifier=Path(__file__).with_name('verify_sd_jtag_transfer.py').read_text();verifier=verifier.replace('plate_sd_20261026/jtag_writer','road_sd_20261027/jtag_writer');(writer/'verify_transfer.py').write_text(verifier,encoding='utf-8')
    write(ROOT/'tools.json',dict(auto_test_script_sha256=sha(ROOT/'test_autostart.tcl'),writer_elf_sha256=sha(writer/'sd_jtag_writer.elf'),
           existing_helper_unchanged=True,backup_before_write=True,staging_before_rename=True,formatting=False,flash_write=False))
    print('ROAD_SD_AUTOSTART_AND_SAFE_CARD_TOOLS_READY',flush=True)
if __name__=='__main__':main()
