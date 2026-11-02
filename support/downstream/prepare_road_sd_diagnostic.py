"""Instrument previous startup failure without changing known-good detector or SD card."""
import importlib.util,re,tkinter
from pathlib import Path
from road_arm_common import read,write,sha
from build_road_arm_probe import fnv
HERE=Path(__file__).resolve().parent
ROOT=Path('E:/FPGA_Enhance_Work/road_sd_diagnostic_r1_20261027')
OLD=Path('E:/FPGA_Enhance_Work/road_sd_20261027')

def main():
    builder=(HERE/'prepare_road_sd.py').read_text()
    builder=builder.replace("ROOT=Path('E:/FPGA_Enhance_Work/road_sd_20261027')",f"ROOT=Path('{ROOT.as_posix()}')")
    marker="    code=code.replace(needle,auto+needle);p.write_text(code,encoding='ascii')"
    replacement=r'''    code=code.replace(needle,auto+needle)
    stop='static void sd_diag_error(uint32_t n){mail[M_ERROR]=n;mail[M_STATE]=4;barrier();for(;;){mail[M_HEARTBEAT]++;usleep(1000);}}\n'
    code=code.replace('int main(void){',stop+'int main(void){')
    before="""  mail[45]=1;mail[46]=ROAD_EXPECTED_WEIGHT_FNV;mail[47]=0x%08xU;
  mail[40]=fnv(road_sd_weights_start,ROAD_WEIGHT_FLOATS*4U);
  mail[41]=fnv(road_sd_photo_start,400U*240U*4U);barrier();
  if(mail[40]!=ROAD_EXPECTED_WEIGHT_FNV)sd_diag_error(301);
  if(mail[41]!=mail[47])sd_diag_error(302);
  mail[45]=2;barrier();
""" % fnv(image.read_bytes())
    needlecopy='  memcpy((void *)WEIGHT_ADDR,road_sd_weights_start,ROAD_WEIGHT_FLOATS*4U);'
    assert code.count(needlecopy)==1;code=code.replace(needlecopy,before+needlecopy)
    needleflush='  Xil_DCacheFlushRange(WEIGHT_ADDR,ROAD_WEIGHT_FLOATS*4U);Xil_DCacheFlushRange(INPUT_ADDR,400U*240U*4U);'
    checks="""  mail[42]=fnv((const void *)WEIGHT_ADDR,ROAD_WEIGHT_FLOATS*4U);barrier();
  if(mail[42]!=ROAD_EXPECTED_WEIGHT_FNV)sd_diag_error(303);
"""
    after="""
  mail[45]=3;barrier();
  Xil_DCacheInvalidateRange(WEIGHT_ADDR,ROAD_WEIGHT_FLOATS*4U);Xil_DCacheInvalidateRange(INPUT_ADDR,400U*240U*4U);
  mail[43]=fnv((const void *)WEIGHT_ADDR,ROAD_WEIGHT_FLOATS*4U);
  mail[44]=fnv(road_sd_weights_start,ROAD_WEIGHT_FLOATS*4U);barrier();
  if(mail[43]!=ROAD_EXPECTED_WEIGHT_FNV)sd_diag_error(304);
  if(mail[44]!=ROAD_EXPECTED_WEIGHT_FNV)sd_diag_error(305);
  if(fnv((const void *)INPUT_ADDR,400U*240U*4U)!=mail[47])sd_diag_error(306);
  mail[45]=4;barrier();
"""
    assert code.count(needleflush)==1;code=code.replace(needleflush,checks+needleflush+after)
    p.write_text(code,encoding='ascii')'''
    assert builder.count(marker)==1;builder=builder.replace(marker,replacement)
    builder=builder.replace("if __name__=='__main__':main()",'')
    path=ROOT.parent/'road_sd_diagnostic_r1_builder_20261027.py';path.write_text(builder,encoding='utf-8')
    spec=importlib.util.spec_from_file_location('sd_diagnostic_builder',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.main()
    tcl=(OLD/'test_autostart.tcl').read_text();tcl=tcl.replace(OLD.as_posix(),ROOT.as_posix()).replace(read(OLD/'boot_image_validation.json')['elf_sha256'],sha(ROOT/'road_sd.elf'))
    reset=''' targets -set -filter {name =~ "APU*"} -timeout 10
 rst -system
 after 1000
 fpga -file $root/display.bit
 targets -set -filter {name =~ "ARM*#0"} -timeout 10
 source $root/ps7_init.tcl
 ps7_init
 ps7_post_config
 loadhw -hw $root/display.xsa'''
    old=' targets -set -filter {name =~ "ARM*#0"} -timeout 10\n stop\n rst -processor';assert tcl.count(old)==1;tcl=tcl.replace(old,reset)
    tcl=tcl.replace('if {[file exists $out]} {error "Preserve previous readback"}','if {[file exists $out]} {error "Preserve previous readback"}\nfile mkdir $out')
    tcl=tcl.replace('file mkdir $out\n mrd -bin','mrd -bin')
    tcl=tcl.replace('if {[word 0x13800008]==4} {error "Self-contained app error [word 0x13800018]"}','if {[word 0x13800008]==4} {mrd -bin -file $out/diagnostic_mailbox.bin 0x13800000 48;error "Self-contained app error [word 0x13800018]"}')
    needle=' mrd -bin -file $out/auto_flag.bin 0x1380009c 1';assert tcl.count(needle)==1;tcl=tcl.replace(needle,needle+'\n mrd -bin -file $out/diagnostic_mailbox.bin 0x13800000 48')
    assert 'dow -data' not in tcl and 'mwr ' not in tcl and 'rst -processor' not in tcl and int(tkinter.Tcl().call('info','complete',tcl))==1
    (ROOT/'test_autostart_clean_reset.tcl').write_text(tcl,encoding='ascii')
    # Host-only corruption controls on copies prove that full hashes cover later bytes too.
    b=(ROOT/'blobs/autoweights.bin').read_bytes();expected=fnv(b);checks=[]
    for offset in [0,1024,65536,len(b)//2,len(b)-1]:
        c=bytearray(b);c[offset]^=1;assert fnv(c)!=expected;checks.append(dict(offset=offset,full_hash_detects_corruption=True))
    write(ROOT/'diagnostic_protocol.json',dict(status='OFFLINE_DIAGNOSTIC_COMPILED_NOT_PHYSICALLY_TESTED',previous_failure='Embedded FP32 weights hash mismatch after processor-only JTAG reset; first1024bytes matched. Root cause unproven.',
       new_test='System reset, PS initialization and known bit before app. NO extra input/weight data or command upload; app must bootstrap itself.',
       mailbox={40:'embedded source weights FNV before copy',41:'embedded source photo FNV',42:'destination weights FNV before flush',43:'destination FNV afterflush/invalidate',44:'source FNV after cache operations',45:'stage1beforehash2beforecopy3afterflush4allguards passed',46:'expected weight FNV',47:'expected photo FNV'},
       errors={301:'source weights corrupt',302:'source photo corrupt',303:'copied weights corrupt beforeflush',304:'weights corrupt afterflush/invalidate',305:'source corrupt after cache ops',306:'photo destination corrupt'},
       host_corruption_controls=checks,boot_sha256=sha(ROOT/'BOOT.BIN'),test_script_sha256=sha(ROOT/'test_autostart_clean_reset.tcl'),
       sd_written=False,board_accessed=False,cold_boot_verified=False))
    print('SD_STARTUP_DIAGNOSTIC_OFFLINE_READY',sha(ROOT/'BOOT.BIN'),flush=True)
if __name__=='__main__':main()
