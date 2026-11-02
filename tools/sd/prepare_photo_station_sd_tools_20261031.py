"""Prepare auto-start validation and a bounded file-level SD updater."""
from pathlib import Path
import shutil,subprocess,zlib
from car_roi_delivery_common import BASE,read,write,sha
from photo_station_core import APP
from build_photo_station_sd_20261031 import ROOT

def main():
    proof=read(ROOT/'build_verified.json');app=ROOT/'firmware';writer=ROOT/'writer';writer.mkdir(exist_ok=False)
    original=Path(__file__).with_name('sd_jtag_writer.c').read_text()
    original=original.replace('#define LIMIT (16u*1024u*1024u)','#define LIMIT (32u*1024u*1024u)')
    original=original.replace('MB[0]=0x53445731u;MB[1]=1;','MB[0]=0x53445732u;MB[1]=2;')
    anchor='    if(cmd==8) { FRESULT fr=f_mount(0,"0:",0);MB[21]=fr==FR_OK;return fr; }'
    assert original.count(anchor)==1
    new=r'''    if(cmd==9) {
        if(!committed || MB[20]!=0x44454c31u || MB[24]) return 1700;
        r=read_file("0:/BOOT.BIN",READBACK,&n);if(r) return r;
        if(n!=new_size || crc32(READBACK,n)!=new_crc || memcmp(READBACK,UPLOAD,n)!=0) return 1701;
        if(old_present) {
            r=read_file(backup_name,OLD,&n);if(r) return r;
            if(n!=old_size || crc32(OLD,n)!=old_crc) return 1702;
            FRESULT fr=f_unlink(backup_name);if(fr!=FR_OK) return fr;
            FILINFO info;fr=f_stat(backup_name,&info);if(fr!=FR_NO_FILE) return 1703;
        }
        MB[24]=1;return 0;
    }
    if(cmd==10) {
        DIR directory;FILINFO info;FRESULT fr=f_opendir(&directory,"0:/");if(fr!=FR_OK)return fr;
        unsigned at=0,entries=0;
        for(;;){
            fr=f_readdir(&directory,&info);if(fr!=FR_OK){(void)f_closedir(&directory);return fr;}
            if(!info.fname[0])break;
            if(at+256u>=1048576u){(void)f_closedir(&directory);return 1801;}
            int count=snprintf((char *)READBACK+at,1048576u-at,"%s\t%c\t%lu\n",info.fname,(info.fattrib&AM_DIR)?'D':'F',(unsigned long)info.fsize);
            if(count<0 || (unsigned)count>=1048576u-at){(void)f_closedir(&directory);return 1802;}
            at+=(unsigned)count;entries++;
        }
        fr=f_closedir(&directory);MB[22]=at;MB[23]=entries;return fr;
    }
'''
    original=original.replace(anchor,new+anchor);(writer/'sd_writer.c').write_text(original,encoding='ascii')
    prior=BASE/'plate_sd_20261026/jtag_writer'
    for n in ['lscript.ld','Xilinx.spec']:shutil.copy2(prior/n,writer/n)
    bsp=BASE/'camera_nn_sd_20261018/vitis_ws/nn_sd_platform/export/nn_sd_platform/sw/nn_sd_platform/standalone_domain'
    cmd=['E:/Xilinx/Vitis/2020.2/gnu/aarch32/nt/gcc-arm-none-eabi/bin/arm-none-eabi-gcc.exe','-mcpu=cortex-a9','-mfpu=vfpv3','-mfloat-abi=hard','-O2','-g','-Wall','-Wextra','-Werror',
        '-I'+str(bsp/'bspinclude/include'),'-L'+str(bsp/'bsplib/lib'),'-specs='+str(writer/'Xilinx.spec'),'-Wl,-T,'+str(writer/'lscript.ld'),str(writer/'sd_writer.c'),'-o',str(writer/'sd_writer.elf'),'-Wl,--start-group','-lxilffs','-lxil','-lgcc','-lc','-Wl,--end-group']
    p=subprocess.run(cmd,capture_output=True,text=True);(writer/'build.log').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stderr
    common=(prior/'sd_common.tcl').read_text().replace('0x53445731','0x53445732').replace('[number $before 1]!=1','[number $before 1]!=2').replace('$i<600','$i<1800')
    (writer/'sd_common.tcl').write_text(common,encoding='ascii')
    boot=(ROOT/'BOOT.BIN').read_bytes();assert len(boot)<32*1024*1024
    write(writer/'writer.json',dict(status='BOUNDED32M_FILE_UPDATER_COMPILED_NOT_YET_RUN',elf_sha256=sha(writer/'sd_writer.elf'),source_sha256=sha(writer/'sd_writer.c'),
        boot_sha256=sha(ROOT/'BOOT.BIN'),boot_bytes=len(boot),boot_crc32=zlib.crc32(boot),limit=32*1024*1024,
        upload=0x10000000,readback=0x12000000,old_backup=0x14000000,mailbox=0x03000000,
        deletion_scope='Only updater-generated Bxxxxxxx.BIN that contains the replaced BOOT, after PC backup/full readback verification. No other files deleted.',
        command=cmd,formatting=False,flash_access=False))
    out=ROOT/'auto_ram_test';out.mkdir()
    a=app.as_posix();d=out.as_posix();oldapp=APP.as_posix()
    script=f'''source {oldapp}/camera_common.tcl
set sdroot {a}
if {{[catch {{
 connect -url tcp:127.0.0.1:3121
 targets -set -filter {{name =~ "APU*"}} -timeout 10
 rst -system
 after 1000
 fpga -file $sdroot/display.bit
 targets -set -filter {{name =~ "ARM*#0"}} -timeout 10
 source $sdroot/ps7_init.tcl
 ps7_init
 ps7_post_config
 loadhw -hw $sdroot/display.xsa
 dow $sdroot/road_detail.elf
 con
 set ready 0
 for {{set i 0}} {{$i<1800}} {{incr i}} {{
  after 100
  if {{[word 0x13800000]==0x524f4144 && [word 0x13800004]==30}} {{
   rc_check
   if {{[word 0x13800428]==0x53443330 && [word 0x1380042c]==1 && [word 0x13800270]==1 && [word 0x13800008]==5 && [word 0x13800010]==1}} {{set ready 1;break}}
  }}
 }}
 if {{!$ready}} {{error "Embedded auto-start timeout"}}
 rc_pause
 mrd -bin -file {d}/mail.bin 0x13800000 320
 mrd -bin -file {d}/ui.u32 0x16500000 17
 mrd -bin -file {d}/source800.bgr 0x1A300000 288000
 mrd -bin -file {d}/raw.u32 0x16700000 96000
 mrd -bin -file {d}/enhanced.u32 0x16100000 96000
 set n [word 0x138000d0]
 set b [word 0x13800238]
 if {{$n>300 || $b>300}} {{error "Invalid automatic box count"}}
 if {{$n>0}} {{mrd -bin -file {d}/boxes.f32 0x16200000 [expr {{$n*6}}]}} else {{close [open {d}/boxes.f32 w]}}
 if {{$b>0}} {{mrd -bin -file {d}/baseline.f32 0x1A200000 [expr {{$b*6}}]}} else {{close [open {d}/baseline.f32 w]}}
 set frame [word 0x13800080]
 if {{$frame!=0x02000000 && $frame!=0x02119400}} {{error "Invalid display frame"}}
 mrd -bin -file {d}/frame.bgr $frame 288000
 mrd -bin -file {d}/vdma.bin 0x43000000 16
 set f [open {d}/packet_origin.txt w];puts $f "actual_hardware_jtag_readback";close $f
 disconnect
 puts "PHOTO_RETURN_PACKET_READY"
 puts "SD_SELF_CONTAINED_AUTO_READY_NO_EXTRA_DATA_OR_COMMAND"
}} why opts]}} {{puts stderr "SD_AUTO_TEST_FAILED $why";catch {{disconnect}};exit 1}}
exit 0
'''
    assert 'dow -data' not in script and 'mwr' not in script
    (out/'request.tcl').write_text(script,encoding='ascii')
    print('SD_AUTO_TEST_AND_BOUNDED_WRITER_PREPARED',flush=True)

if __name__=='__main__':main()
