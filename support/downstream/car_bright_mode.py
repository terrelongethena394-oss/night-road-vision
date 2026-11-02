"""Switch display page without re-running either detector; verify LCD bytes."""
import datetime,struct,subprocess
from car_pair_tools import *

def display_mode(out,mode,previous=None):
 assert mode in [0,1];out.mkdir(parents=True);d=out.as_posix();script=out/'mode.tcl';script.write_text(f'''source {APP.as_posix()}/camera_common.tcl
connect -url tcp:127.0.0.1:3121
if {{[catch {{
 targets -set -filter {{name =~ "ARM*#0"}} -timeout 10
 loadhw -hw $root/display.xsa
 rc_check
 set before [word 0x13800010]
 mwr 0x138002bc {mode}
 mwr 0x1380000c 6
 set ready 0
 for {{set i 0}} {{$i<100}} {{incr i}} {{after 100;rc_check;if {{[word 0x13800008]==5}} {{set ready 1;break}}}}
 if {{!$ready}} {{error "Display command timeout"}}
 mwr 0x1380000c 1
 set ready 0
 for {{set i 0}} {{$i<100}} {{incr i}} {{after 100;rc_check;if {{[word 0x13800008]==3 && [word 0x138000e4]==1}} {{set ready 1;break}}}}
 if {{!$ready || [word 0x13800010]!=$before}} {{error "Display command changed inference or failed pause"}}
 mrd -bin -file {d}/mail.bin 0x13800000 176
 mrd -bin -file {d}/ui.u32 0x16500000 17
 mrd -bin -file {d}/raw.u32 0x16700000 96000
 mrd -bin -file {d}/enhanced.u32 0x16100000 96000
 set n [word 0x138000d0]
 set bn [word 0x13800238]
 if {{$n>300 || $bn>300}} {{error "Invalid counts"}}
 if {{$n}} {{mrd -bin -file {d}/boxes.f32 0x16200000 [expr {{$n*6}}]}} else {{close [open {d}/boxes.f32 w]}}
 if {{$bn}} {{mrd -bin -file {d}/baseline.f32 0x1A200000 [expr {{$bn*6}}]}} else {{close [open {d}/baseline.f32 w]}}
 set frame [word 0x13800080]
 if {{$frame!=0x02000000 && $frame!=0x02119400}} {{error "Invalid framebuffer"}}
 mrd -bin -file {d}/frame.bgr $frame 288000
 disconnect
 puts "CAR_BRIGHT_MODE_READY"
}} why opts]}} {{puts stderr "CAR_BRIGHT_MODE_FAILED $why";catch {{disconnect}};exit 1}}
exit 0
''',encoding='ascii');run(script,out/'mode.log','CAR_BRIGHT_MODE_READY',90)
 m=struct.unpack('<176I',(out/'mail.bin').read_bytes());u=struct.unpack('<17I',(out/'ui.u32').read_bytes());assert m[1]==27 and m[175]==mode and (u[14]>>8)==mode
 if previous:
  for name in ['raw.u32','enhanced.u32','boxes.f32','baseline.f32']:assert (out/name).read_bytes()==(Path(previous)/name).read_bytes()
 p=subprocess.run([str(APP/'host/render.exe'),str(out/'raw.u32'),str(out/'enhanced.u32'),str(out/'boxes.f32'),str(out/'baseline.f32'),str(out/'ui.u32'),str(out/'expected.bgr')],capture_output=True,text=True);assert p.returncode==0 and 'GUARDS_PASS' in p.stdout and (out/'expected.bgr').read_bytes()==(out/'frame.bgr').read_bytes()
 Image.fromarray(np.fromfile(out/'frame.bgr',np.uint8).reshape(480,800,3)[:,:,::-1]).save(out/'lcd_readback.png');write(out/'verified.json',dict(status='DISPLAY_PAGE_SWITCH_C_FRAME_BYTE_EXACT',mode=mode,inference_not_rerun=True,images_and_boxes_unchanged=bool(previous),sd_written=False));print('CAR_BRIGHT_MODE_PASS',mode,flush=True)

def main():
 import sys
 assert len(sys.argv)==2;mode=int(sys.argv[1]);assert read(ROOT/'board_verified.json')['status']=='ABI27_CAR_BRIGHT_DISPLAY_BOARD_VERIFIED';out=ROOT/'user_modes'/datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f');display_mode(out,mode)
if __name__=='__main__':main()
