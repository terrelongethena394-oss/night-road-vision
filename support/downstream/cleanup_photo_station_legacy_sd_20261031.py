"""Remove the one preexisting old boot backup, after verified PC preservation."""
from pathlib import Path
import shutil,struct,subprocess,zlib,json
from car_roi_delivery_common import BASE,read,write,sha
from build_photo_station_sd_20261031 import ROOT
from photo_station_core import device_lock
from roi_delivery_board_tools import run

def main():
    receipt=read(ROOT/'sd_write_verified.json');assert receipt['filesystem_unmounted'] and receipt['old_version_removed_from_sd']
    oldroot=ROOT/'writer';before_mail=[int(s,0) for s in (oldroot/'root_before_mail.txt').read_text().split()]
    before=(oldroot/'root_before_padded.txt').read_bytes()[:before_mail[22]].decode('utf-8');assert 'B0000001.BIN\tF\t4231760\n' in before
    out=ROOT/'legacy_cleanup';out.mkdir(exist_ok=False);bsp=BASE/'camera_nn_sd_20261018/vitis_ws/nn_sd_platform/export/nn_sd_platform/sw/nn_sd_platform/standalone_domain'
    for name in ['Xilinx.spec','lscript.ld']:shutil.copy2(oldroot/name,out/name)
    shutil.copy2(Path(__file__).with_name('sd_legacy_backup_cleanup.c'),out/'cleanup.c')
    boot=(ROOT/'BOOT.BIN').read_bytes();(out/'legacy_config.h').write_text(f'#define EXPECTED_BOOT_BYTES {len(boot)}U\n#define EXPECTED_BOOT_CRC {zlib.crc32(boot)}U\n',encoding='ascii')
    cmd=['E:/Xilinx/Vitis/2020.2/gnu/aarch32/nt/gcc-arm-none-eabi/bin/arm-none-eabi-gcc.exe','-mcpu=cortex-a9','-mfpu=vfpv3','-mfloat-abi=hard','-O2','-std=c99','-Wall','-Wextra','-Werror',
        '-I'+str(bsp/'bspinclude/include'),'-I'+str(out),'-L'+str(bsp/'bsplib/lib'),'-specs='+str(out/'Xilinx.spec'),'-Wl,-T,'+str(out/'lscript.ld'),str(out/'cleanup.c'),'-o',str(out/'cleanup.elf'),'-Wl,--start-group','-lxilffs','-lxil','-lgcc','-lc','-Wl,--end-group']
    p=subprocess.run(cmd,capture_output=True,text=True);(out/'build.log').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stderr
    a=(ROOT/'firmware').as_posix();d=out.as_posix()
    script=f'''proc word {{a}} {{return [expr {{[lindex [mrd -value $a] 0]+0}}]}}
if {{[catch {{
 connect -url tcp:127.0.0.1:3121
 targets -set -filter {{name =~ "APU*"}} -timeout 10
 rst -system
 after 1000
 fpga -file {a}/display.bit
 targets -set -filter {{name =~ "ARM*#0"}} -timeout 10
 source {a}/ps7_init.tcl
 ps7_init
 ps7_post_config
 loadhw -hw {a}/display.xsa
 dow {d}/cleanup.elf
 con
 set ready 0
 for {{set i 0}} {{$i<600}} {{incr i}} {{after 100;if {{[word 0x03000000]==0x53444331}} {{if {{[word 0x03000008]==4}} {{error "Read-only legacy probe failed [word 0x03000014]"}};if {{[word 0x03000008]==1}} {{set ready 1;break}}}}}}
 if {{!$ready}} {{error "Read-only legacy probe timeout"}}
 mrd -bin -file {d}/probe_mail.bin 0x03000000 64
 set n [word 0x03000024]
 mrd -bin -file {d}/legacy_readback.bin 0x14000000 [expr {{($n+3)/4}}]
 set count [word 0x03000058]
 mrd -bin -file {d}/root_before.bin 0x16000000 [expr {{($count+3)/4}}]
 disconnect
 puts "LEGACY_BOOT_BACKED_UP_READ_ONLY"
}} why]}} {{puts stderr "LEGACY_PROBE_FAILED $why";catch {{disconnect}};exit 1}}
exit 0
'''
    with device_lock(out):
        (out/'probe.tcl').write_text(script,encoding='ascii');run(out/'probe.tcl',out/'probe.log','LEGACY_BOOT_BACKED_UP_READ_ONLY',timeout=300)
        m=struct.unpack('<64I',(out/'probe_mail.bin').read_bytes());assert m[0]==0x53444331 and m[2]==1 and m[5]==0 and m[7]==len(boot) and m[8]==zlib.crc32(boot)
        data=(out/'legacy_readback.bin').read_bytes()[:m[9]];assert len(data)==4231760 and zlib.crc32(data)==m[10]
        assert struct.unpack_from('<II',data,0x20)==(0xaa995566,0x584c4e58) and sum(struct.unpack_from('<11I',data,0x20))&0xffffffff==0xffffffff
        backup=ROOT/'old_boot_backup/B0000001.BIN.original';backup.write_bytes(data);assert backup.read_bytes()==data
        write(out/'pc_backup_verified.json',dict(filename='B0000001.BIN',bytes=len(data),sha256=sha(backup),crc32=m[10],pc_backup=str(backup),recognized_Zynq_boot_header=True))
        script=f'''proc word {{a}} {{return [expr {{[lindex [mrd -value $a] 0]+0}}]}}
if {{[catch {{
 connect -url tcp:127.0.0.1:3121
 targets -set -filter {{name =~ "ARM*#0"}} -timeout 10
 loadhw -hw {a}/display.xsa
 if {{[word 0x03000000]!=0x53444331 || [word 0x03000008]!=1 || [word 0x03000024]!={len(data)} || [word 0x03000028]!={m[10]}}} {{error "Legacy PC backup/session mismatch"}}
 mwr 0x03000064 {len(data)}
 mwr 0x03000068 {m[10]}
 mwr 0x03000050 0x4241434b
 mwr 0x0300000c 1
 set ready 0
 for {{set i 0}} {{$i<600}} {{incr i}} {{after 100;if {{[word 0x03000008]==4}} {{error "Legacy removal failed [word 0x03000014]"}};if {{[word 0x03000008]==3}} {{set ready 1;break}}}}
 if {{!$ready}} {{error "Legacy removal timeout"}}
 mrd -bin -file {d}/final_mail.bin 0x03000000 64
 set count [word 0x03000058]
 mrd -bin -file {d}/root_after.bin 0x16000000 [expr {{($count+3)/4}}]
 disconnect
 puts "LEGACY_BOOT_REMOVED_NEW_BOOT_CRC_MATCH_CARD_UNMOUNTED"
}} why]}} {{puts stderr "LEGACY_REMOVE_FAILED $why";catch {{disconnect}};exit 1}}
exit 0
'''
        (out/'remove.tcl').write_text(script,encoding='ascii');run(out/'remove.tcl',out/'remove.log','LEGACY_BOOT_REMOVED_NEW_BOOT_CRC_MATCH_CARD_UNMOUNTED',timeout=180)
        f=struct.unpack('<64I',(out/'final_mail.bin').read_bytes());assert f[2]==3 and f[5]==0 and f[21]==f[24]==1 and f[7]==len(boot) and f[8]==zlib.crc32(boot)
        after=(out/'root_after.bin').read_bytes()[:f[22]].decode('utf-8');assert 'B0000001.BIN' not in after and 'PLTNEW.BIN' not in after
        parse=lambda s:{line.split('\t')[0]:line.split('\t')[1:] for line in s.splitlines() if line}
        bb=parse((out/'root_before.bin').read_bytes()[:m[22]].decode('utf-8'));aa=parse(after)
        assert {k:v for k,v in bb.items() if k!='B0000001.BIN'}==aa
        result=dict(status='HISTORICAL_BOOT_BACKUP_REMOVED_AFTER_PC_BACKUP',deleted_file='B0000001.BIN',pc_backup=str(backup),sha256=sha(backup),bytes=len(data),
            new_BOOT_crc_still_matches=True,new_BOOT_size=len(boot),filesystem_unmounted=True,root_after=after,sd_written=True,flash_written=False)
        write(ROOT/'legacy_cleanup_verified.json',result);print('SD_LEGACY_CLEANUP_VERIFIED',json.dumps(result),flush=True)

if __name__=='__main__':main()
