"""ABI31 adds explicit camera preview commands; same models, operators and PL."""
from pathlib import Path
import shutil,struct,subprocess
from car_roi_delivery_common import BASE,read,write,sha
from photo_station_core import APP

ROOT=BASE/'camera_station_abi31_20261031'
OLD=BASE/'photo_station_sd_20261031_r1'

def main():
    assert not ROOT.exists();ROOT.mkdir();shutil.copytree(OLD/'firmware',ROOT/'firmware');app=ROOT/'firmware';source=app/'source/road_camera_main.c'
    text=source.read_text(encoding='ascii');assert text.count('m[M_VERSION]=30;')==1
    text=text.replace('m[M_VERSION]=30;','m[M_VERSION]=31;').replace('m[266]=0x53443330U;','m[266]=0x53443331U;')
    text=text.replace('if(!busy&&!has_result&&','if(m[269]&&!busy&&!has_result&&')
    anchor='static void boxes(uint32_t address'
    assert text.count(anchor)==1
    helper='''/* Frozen small RGB preview. Only command8 writes this buffer. */
#define CAM_PREVIEW_ADDR 0x1E000000U
static void camera_preview_packet(void){
 uint32_t bank=0,x,y;uint8_t *out=(uint8_t *)CAM_PREVIEW_ADDR;
 if(rc_snapshot((uint32_t *)RC_LIVE,&bank))fatal(230);
 for(y=0;y<144U;y++)for(x=0;x<240U;x++){
  uint32_t ix=(5U*x+2U)/3U,iy=(5U*y+2U)/3U,q=((const uint32_t *)RC_LIVE)[iy*400U+ix],at=(y*240U+x)*3U;
  out[at]=(uint8_t)q;out[at+1]=(uint8_t)(q>>8);out[at+2]=(uint8_t)(q>>16);
 }
 Xil_DCacheFlushRange(CAM_PREVIEW_ADDR,240U*144U*3U);
 m[271]=CAM_PREVIEW_ADDR;m[272]=240U*144U*3U;m[273]=240;m[274]=144;m[275]=hash(out,240U*144U*3U);m[276]=bank;
 barrier();m[270]++;barrier();
}
'''
    text=text.replace(anchor,helper+anchor)
    anchor='m[46]=1;m[175]=0;m[72]=2;m[80]=2;m[94]=2;m[M_COMMAND]=5;barrier();'
    assert text.count(anchor)==1
    text=text.replace(anchor,'m[46]=1;m[175]=0;m[72]=2;m[80]=2;m[94]=2;m[268]=0x43414D31U;m[269]=1;m[M_COMMAND]=0;barrier();')
    anchor='  if(m[M_COMMAND]==2U||m[M_COMMAND]==4U||m[M_COMMAND]==5U){'
    assert text.count(anchor)==1
    text=text.replace(anchor,'''  if(m[M_COMMAND]==7U){
   m[M_COMMAND]=0;has_result=0;result_count=0;m[52]=0;m[269]=1;last_view=0;m[M_STATE]=1;service(0);barrier();
  }else if(m[M_COMMAND]==8U){
   m[M_COMMAND]=0;camera_preview_packet();barrier();
  }else if(m[M_COMMAND]==9U){
   m[M_COMMAND]=0;m[269]=0;present(0);m[M_STATE]=has_result?5U:1U;barrier();
  }else if(m[M_COMMAND]==2U||m[M_COMMAND]==4U||m[M_COMMAND]==5U){''')
    text=text.replace('unsigned kind=m[M_COMMAND];','unsigned kind=m[M_COMMAND];m[269]=0;')
    text=text.replace('ROAD_NATIVE_ROI_SD_READY V30','ROAD_CAMERA_STATION_READY V31');source.write_text(text,encoding='ascii')
    old=read(OLD/'build_verified.json');commands=[];logs=[]
    def run(cmd):
        p=subprocess.run(cmd,capture_output=True,text=True);commands.append(cmd);logs.append(p.stdout+p.stderr);(ROOT/'build.log').write_text('\n'.join(logs),encoding='utf-8');assert p.returncode==0,p.stderr
    relocate=lambda cmd:[s.replace(str(OLD),str(ROOT)).replace(OLD.as_posix(),ROOT.as_posix()) for s in cmd]
    c=next(c for c in old['arm_commands'] if '-c' in c and any(Path(s).name=='road_camera_main.c' for s in c));run(relocate(c))
    link=next(c for c in old['arm_commands'] if Path(c[0]).name=='arm-none-eabi-gcc.exe' and '-c' not in c);run(relocate(link))
    raw=(app/'road_detail.elf').read_bytes();ph=struct.unpack_from('<I',raw,28)[0];ent,n=struct.unpack_from('<HH',raw,42);loads=[]
    for i in range(n):
        typ,off,va,pa,fs,mem,flags,align=struct.unpack_from('<8I',raw,ph+i*ent)
        if typ==1 and mem:assert 0x100000<=pa<pa+mem<=0x02000000;loads.append([pa,pa+mem])
    for p in (app/'source').iterdir():
        if p.is_file() and p.name!='road_camera_main.c':assert sha(p)==sha(OLD/'firmware/source'/p.name)
    assert sha(app/'display.bit')==old['bit_sha256']
    a=app.as_posix();common=APP.as_posix()
    loader=f'''source {common}/camera_common.tcl
set camera_app {a}
if {{[catch {{
 connect -url tcp:127.0.0.1:3121
 targets -set -filter {{name =~ "APU*"}} -timeout 10
 rst -system
 targets -set -filter {{name =~ "ARM*#0"}} -timeout 10
 stop
 rst -processor -clear-registers
 stop
 fpga -file $camera_app/display.bit
 source $camera_app/ps7_init.tcl
 ps7_init
 ps7_post_config
 loadhw -hw $camera_app/display.xsa
 dow $camera_app/road_detail.elf
 con
 set ready 0
 for {{set i 0}} {{$i<1200}} {{incr i}} {{after 100;if {{[word 0x13800000]==0x524f4144 && [word 0x13800004]==31}} {{if {{[word 0x13800018]!=0 || [word 0x13800008]==4}} {{error "Camera app error [word 0x13800018]"}};if {{[word 0x13800430]==0x43414d31 && [word 0x13800008]==1}} {{set ready 1;break}}}}}}
 if {{!$ready}} {{error "Camera ready timeout"}}
 disconnect
 puts "CAMERA_STATION_ABI31_PREVIEW_READY"
}} why opts]}} {{puts stderr "CAMERA_STATION_START_FAILED $why";catch {{disconnect}};exit 1}}
exit 0
'''
    assert 'dow -data' not in loader;(ROOT/'start_camera.tcl').write_text(loader,encoding='ascii')
    write(ROOT/'build_verified.json',dict(status='ABI31_CAMERA_INTERFACE_BUILT_NOT_YET_BOARD_TESTED',version=31,elf_sha256=sha(app/'road_detail.elf'),
        baseline_sd_elf_sha256=old['elf_sha256'],bit_sha256=old['bit_sha256'],models_unchanged=True,only_main_interface_modified=True,
        commands=commands,elf_regions=loads,preview_address=0x1E000000,preview_size=[240,144],sd_written=False))
    print('CAMERA_STATION_ABI31_BUILT',sha(app/'road_detail.elf'),flush=True)

if __name__=='__main__':main()
