"""Authorized file-level SD replacement, with PC backup and full-byte readback."""
from pathlib import Path
import json,struct,time,zlib,traceback
from PIL import Image
import numpy as np
from car_roi_delivery_common import read,write,sha
from build_photo_station_sd_20261031 import ROOT
from photo_station_core import APP,STAGING,device_lock,verify_return
from roi_delivery_board_tools import run,start

WRITER=ROOT/'writer'
def invoke(name,body,marker,timeout=600):
    script=WRITER/(name+'.tcl');log=WRITER/(name+'.log')
    script.write_text('set root '+WRITER.as_posix()+'\nsource $root/sd_common.tcl\nif {[catch {\n'+body+'\n} why opts]} {puts stderr "SD_OPERATION_FAILED $why";catch {disconnect};exit 1}\nexit 0\n',encoding='ascii')
    run(script,log,marker,timeout=timeout)
def get_words(name):return [int(s,0) for s in (WRITER/name).read_text().split()]
def exact_file(name,size):
    data=(WRITER/name).read_bytes();assert len(data)==(size+3)//4*4;return data[:size]
def connect():return f'''connect -url tcp:127.0.0.1:3121
targets -set -filter {{name =~ "ARM*#0"}} -timeout 10
loadhw -hw {ROOT.as_posix()}/firmware/display.xsa
'''
def stage(name):
    write(ROOT/'install_running.json',dict(stage=name,keep_board_powered=True,sd_cold_boot_verified=False));print('PHOTO_SD_INSTALL_STAGE',name,flush=True)

def main():
    model=read(ROOT/'build_verified.json');writer=read(WRITER/'writer.json');boot=(ROOT/'BOOT.BIN').read_bytes()
    assert sha(ROOT/'BOOT.BIN')==model['boot_sha256']==writer['boot_sha256'] and sha(WRITER/'sd_writer.elf')==writer['elf_sha256']
    assert len(boot)==writer['boot_bytes']<writer['limit'] and zlib.crc32(boot)==writer['boot_crc32']
    card_written=False;committed=False;part='before_start'
    with device_lock(ROOT):
        try:
            stage('VERIFY_SELF_CONTAINED_RAM_AUTO_START');part='auto_test'
            auto=ROOT/'auto_ram_test';run(auto/'request.tcl',auto/'request.log','SD_SELF_CONTAINED_AUTO_READY_NO_EXTRA_DATA_OR_COMMAND',timeout=600)
            latest=read(STAGING/'actual_roundtrip_verified.json');prepared=Path(latest['packet_evidence']).parent/'prepared'
            v=verify_return(auto,prepared);m=struct.unpack('<320I',(auto/'mail.bin').read_bytes());assert m[266:268]==(0x53443330,1) and m[4]==1
            expected=Path(model['expected_packet'])
            for n in ['source800.bgr','raw.u32','enhanced.u32','boxes.f32']:assert (auto/n).read_bytes()==(expected/n).read_bytes(),n
            Image.fromarray(np.fromfile(auto/'frame.bgr',np.uint8).reshape(480,800,3)[:,:,::-1]).save(auto/'lcd_readback.png')
            write(ROOT/'auto_start_verified.json',dict(status='SELF_CONTAINED_ELF_AUTO_START_ACTUAL_BOARD_PASS',receipt=v,elf_sha256=sha(ROOT/'firmware/road_detail.elf'),
                  extra_weight_or_photo_upload=False,host_command_trigger=False,expected_payloads_exact=True,physical_sd_cold_boot=False,sd_written=False))
            stage('READ_CARD_AND_BACKUP_OLD_BOOT_TO_PC');part='backup'
            body=f'''connect -url tcp:127.0.0.1:3121
targets -set -filter {{name =~ "APU*"}} -timeout 10
rst -system
after 1000
fpga -file {ROOT.as_posix()}/firmware/display.bit
targets -set -filter {{name =~ "ARM*#0"}} -timeout 10
source {ROOT.as_posix()}/firmware/ps7_init.tcl
ps7_init
ps7_post_config
loadhw -hw {ROOT.as_posix()}/firmware/display.xsa
dow $root/sd_writer.elf
con
set ready 0
for {{set i 0}} {{$i<200}} {{incr i}} {{after 100;set w [sd_words];if {{[number $w 0]==0x53445732}} {{if {{[number $w 2]==4}} {{error "SD mount failed without file writes: $w"}};if {{[number $w 2]==1}} {{set ready 1;break}}}}}}
if {{!$ready}} {{error "SD helper mount timeout"}}
set w [sd_cmd 1]
save_words $root/probe_mail.txt $w
set w [sd_cmd 10]
dump_bytes $root/root_before_padded.txt 0x12000000 [number $w 22]
save_words $root/root_before_mail.txt $w
set w [sd_cmd 2]
save_words $root/backup_mail.txt $w
dump_bytes $root/old_boot_padded.bin 0x14000000 [number $w 7]
disconnect
puts "SD_OLD_BOOT_BACKUP_READY_NO_FILES_CHANGED"'''
            invoke('backup',body,'SD_OLD_BOOT_BACKUP_READY_NO_FILES_CHANGED')
            w=get_words('backup_mail.txt');assert w[0]==0x53445732 and w[1]==2 and w[5]==0 and w[6]==2 and w[11] in [1,2,3]
            old=exact_file('old_boot_padded.bin',w[7]);assert len(old)==w[10] and zlib.crc32(old)==w[8]
            backup=ROOT/'old_boot_backup';backup.mkdir();(backup/'BOOT.BIN.original').write_bytes(old)
            assert (backup/'BOOT.BIN.original').read_bytes()==old
            backup_name=f'B{w[19]:07d}.BIN'
            b=dict(present=bool(w[9]),bytes=len(old),sha256=sha(backup/'BOOT.BIN.original'),crc32=w[8],sd_transient_backup=backup_name,pc_backup=str(backup/'BOOT.BIN.original'),filesystem=w[11],partition_start_sector=w[12])
            write(backup/'verified.json',b);print('SD_OLD_BOOT_PC_BACKUP_VERIFIED',json.dumps(b),flush=True)
            directory=lambda n:exact_file('root_'+n+'_padded.txt',get_words('root_'+n+'_mail.txt')[22]).decode('utf-8',errors='replace')
            before=directory('before');print('SD_ROOT_BEFORE',before,flush=True)
            stage('STAGE_NEW_BOOT_AND_VERIFY_ALL_BYTES');part='stage';card_written=True
            body=connect()+f'''set w [sd_words]
if {{[number $w 0]!=0x53445732 || [number $w 6]!=2 || [number $w 7]!={len(old)} || [number $w 8]!={w[8]} || [number $w 19]!={w[19]}}} {{error "PC backup/session mismatch"}}
dow -data {ROOT.as_posix()}/BOOT.BIN 0x10000000
catch {{con}}
mwr 0x03000040 {len(boot)}
mwr 0x03000044 {zlib.crc32(boot)}
mwr 0x03000050 0x4241434b
set w [sd_cmd 3]
set w [sd_cmd 4]
save_words $root/staged_mail.txt $w
dump_bytes $root/staged_readback.bin 0x12000000 [number $w 7]
disconnect
puts "SD_NEW_BOOT_STAGED_FULL_READBACK_READY"'''
            invoke('stage',body,'SD_NEW_BOOT_STAGED_FULL_READBACK_READY',timeout=720)
            sw=get_words('staged_mail.txt');assert sw[5]==0 and sw[6]==4 and sw[7]==len(boot) and sw[8]==zlib.crc32(boot)
            assert exact_file('staged_readback.bin',sw[7])==boot
            write(WRITER/'stage_verified.json',dict(status='NEW_TEMP_FILE_ALL_BYTES_MATCH',sha256=sha(ROOT/'BOOT.BIN'),bytes=len(boot)))
            stage('COMMIT_NEW_BOOT_AND_READ_BACK_NEW_AND_OLD');part='commit'
            body=connect()+f'''set w [sd_words]
if {{[number $w 0]!=0x53445732 || [number $w 6]!=4 || [number $w 7]!={len(boot)} || [number $w 8]!={zlib.crc32(boot)}}} {{error "Staged verification/session mismatch"}}
mwr 0x03000050 0x434f4d54
set w [sd_cmd 5]
set w [sd_cmd 6]
save_words $root/final_mail.txt $w
dump_bytes $root/final_readback.bin 0x12000000 [number $w 7]
set w [sd_cmd 7]
save_words $root/old_renamed_mail.txt $w
dump_bytes $root/old_renamed_readback.bin 0x14000000 [number $w 7]
disconnect
puts "SD_NEW_BOOT_COMMITTED_AND_BOTH_FILES_READ_BACK"'''
            invoke('commit',body,'SD_NEW_BOOT_COMMITTED_AND_BOTH_FILES_READ_BACK',timeout=720);committed=True
            fw=get_words('final_mail.txt');ow=get_words('old_renamed_mail.txt');assert fw[5]==0 and fw[6]==6 and fw[7]==len(boot) and fw[8]==zlib.crc32(boot)
            assert exact_file('final_readback.bin',fw[7])==boot and exact_file('old_renamed_readback.bin',ow[7])==old
            stage('REMOVE_REPLACED_OLD_BOOT_FROM_CARD_AND_UNMOUNT');part='cleanup'
            body=connect()+'''set w [sd_words]
if {[number $w 0]!=0x53445732 || [number $w 6]!=7 || [number $w 5]!=0} {error "Old file verification/session mismatch"}
mwr 0x03000050 0x44454c31
set w [sd_cmd 9]
if {[number $w 24]!=1} {error "Old version removal not confirmed"}
save_words $root/deleted_mail.txt $w
set w [sd_cmd 10]
save_words $root/root_after_mail.txt $w
dump_bytes $root/root_after_padded.txt 0x12000000 [number $w 22]
set w [sd_cmd 8]
save_words $root/unmounted_mail.txt $w
disconnect
puts "SD_OLD_VERSION_REMOVED_NEW_BOOT_PRESENT_CARD_UNMOUNTED"'''
            invoke('cleanup',body,'SD_OLD_VERSION_REMOVED_NEW_BOOT_PRESENT_CARD_UNMOUNTED')
            uw=get_words('unmounted_mail.txt');assert uw[5]==0 and uw[6]==8 and uw[21]==1 and uw[24]==1
            after=directory('after');print('SD_ROOT_AFTER',after,flush=True)
            parse=lambda s:{line.split('\t')[0]:line.split('\t')[1:] for line in s.splitlines() if line}
            olddir,newdir=parse(before),parse(after)
            assert backup_name not in newdir and 'PLTNEW.BIN' not in newdir and newdir['BOOT.BIN']==['F',str(len(boot))]
            assert {k:v for k,v in olddir.items() if k!='BOOT.BIN'}=={k:v for k,v in newdir.items() if k!='BOOT.BIN'},'Unexpected root-file change'
            result=dict(status='NEW_SD_BOOT_WRITTEN_FULL_READBACK_OLD_VERSION_REMOVED',boot_sha256=sha(ROOT/'BOOT.BIN'),boot_bytes=len(boot),
                old_boot_backup=b,old_version_removed_from_sd=True,other_root_entries_names_and_sizes_unchanged=True,filesystem_unmounted=True,
                self_contained_RAM_auto_start_verified=True,physical_SD_cold_boot_verified=False,sd_written=True,flash_written=False,
                current_board_program='unmounted_SD_writer_waiting_for_power_off_SD_mode_cold_boot')
            write(ROOT/'sd_write_verified.json',result);write(ROOT/'install_running.json',result)
            print('PHOTO_STATION_SD_WRITE_AND_OLD_REMOVAL_VERIFIED',json.dumps(result),flush=True)
        except Exception as e:
            failure=dict(status='SD_INSTALL_NOT_COMPLETED',stage=part,error=str(e),traceback=traceback.format_exc(),sd_file_write_attempted=card_written,commit_script_completed=committed,
                do_not_power_off_during_unknown_active_write=card_written,old_pc_backup=str(ROOT/'old_boot_backup/BOOT.BIN.original'))
            if not card_written:
                try:start(ROOT);failure['RAM_restoration']='BASELINE_ABI30_CAMERA_IDLE_RESTORED'
                except Exception as restore_error:failure['RAM_restoration_error']=str(restore_error)
            write(ROOT/'install_failed.json',failure);write(ROOT/'install_running.json',failure);print('PHOTO_SD_INSTALL_FAILED',failure,flush=True);raise

if __name__=='__main__':main()
