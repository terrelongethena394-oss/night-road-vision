"""ABI28 actual JTAG readback; SD/Flash are never written."""
from pathlib import Path
import ctypes as ct,json,os,struct,subprocess,time
import numpy as np
from PIL import Image
from build_balanced_car_arm import ROOT,APP,STUDY
from camera_snapshot_tools import fnv
from car_box_refine_common import read,write,sha
XSCT='E:/Xilinx/Vitis/2020.2/bin/xsct.bat'

def run(script,log,marker,timeout=360):
 with Path(log).open('w',encoding='utf-8') as f:p=subprocess.run([XSCT,str(script)],stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
 output=Path(log).read_text(encoding='utf-8',errors='replace');assert marker in output and p.returncode==0,output[-4000:]

def start(out):
 proof=read(APP/'arm_complete.json');assert sha(APP/'road_detail.elf')==proof['elf_sha256']
 assert sha(APP/'display.bit')==proof['bit_sha256'] and sha(APP/'runtime/weights.f32')==proof['detector_weights_sha256'] and sha(APP/'runtime/refiner_weights.f32')==proof['refiner_weights_sha256']
 for name,digest in proof['source_sha256'].items():assert sha(APP/'source'/name)==digest,name
 if (ROOT/'runtime_dependencies.json').exists():
  for name,digest in read(ROOT/'runtime_dependencies.json').items():assert sha(name)==digest,name
 run(APP/'start_idle.tcl',out/'start.log','ROAD_RETINEX_IDLE_READY')

def capture(out,kind=5,source=None,photo=1,view=1):
 assert kind in [4,5] and view in [0,1];out.mkdir(parents=True);d=out.as_posix();a=APP.as_posix();upload=''
 if kind==5:
  source=Path(source);assert source.stat().st_size==1152000
  upload=f'dow -data {source.as_posix()} 0x1A300000\n catch {{con}}\n mwr 0x13800274 {fnv(source.read_bytes())}'
 script=out/'request.tcl';script.write_text(f'''source {a}/camera_common.tcl
connect -url tcp:127.0.0.1:3121
if {{[catch {{
 targets -set -filter {{name =~ "ARM*#0"}} -timeout 10
 loadhw -hw $root/display.xsa
 rc_check
 if {{[word 0x13800008]==3 && [word 0x13800270]!=1}} {{error "Paused inside incomplete inference"}}
 mwr 0x1380000c 0
 set idle 0
 for {{set i 0}} {{$i<100}} {{incr i}} {{after 100;rc_check;if {{[word 0x13800008] in {{1 5}}}} {{set idle 1;break}}}}
 if {{!$idle}} {{error "No safe idle boundary"}}
 {upload}
 mwr 0x1380006c 0
 mwr 0x13800220 0
 mwr 0x13800224 0
 mwr 0x13800228 0
 mwr 0x138000b8 {photo}
 mwr 0x13800070 0
 mwr 0x13800120 2
 mwr 0x13800140 2
 mwr 0x13800144 48
 mwr 0x13800178 2
 mwr 0x138002bc {view}
 set wanted [expr {{[word 0x13800010]+1}}]
 mwr 0x1380000c {kind}
 set ready 0
 for {{set i 0}} {{$i<1800}} {{incr i}} {{after 100;rc_check;if {{[word 0x13800008]==5 && [word 0x13800010]==$wanted && [word 0x13800270]==1}} {{set ready 1;break}}}}
 if {{!$ready}} {{error "Inference timeout"}}
 rc_pause
 mrd -bin -file {d}/mail.bin 0x13800000 208
 mrd -bin -file {d}/ui.u32 0x16500000 17
 mrd -bin -file {d}/source800.bgr 0x1A300000 288000
 if {{{kind}==4}} {{
  set bank [word 0x13800248]
  if {{$bank>1}} {{error "Invalid camera source bank"}}
  mrd -bin -file {d}/camera_bank.bgr [expr {{0x06000000+$bank*1152000}}] 288000
 }}
 mrd -bin -file {d}/raw.u32 0x16700000 96000
 mrd -bin -file {d}/enhanced.u32 0x16100000 96000
 for {{set j 0}} {{$j<4}} {{incr j}} {{mrd -bin -file {d}/decoded_base$j.f32 [expr {{0x1B800000+$j*0x40000}}] 56700}}
 for {{set j 0}} {{$j<3}} {{incr j}} {{mrd -bin -file {d}/raw_tile$j.u32 [expr {{0x1A000000+$j*0x60000}}] 96000}}
 if {{[word 0x138002f4]==1}} {{
  for {{set j 0}} {{$j<3}} {{incr j}} {{
   mrd -bin -file {d}/zoom$j.u32 [expr {{0x1C000000+$j*0x60000}}] 96000
   mrd -bin -file {d}/decoded_zoom$j.f32 [expr {{0x1C120000+$j*0x40000}}] 56700
  }}
 }}
 mrd -bin -file {d}/refiner_outputs.f32 0x1C240000 4500
 set n [word 0x138000d0]
 set bn [word 0x13800238]
 if {{$n>300 || $bn>300}} {{error "Invalid car count"}}
 if {{$n>0}} {{mrd -bin -file {d}/boxes.f32 0x16200000 [expr {{$n*6}}]}} else {{close [open {d}/boxes.f32 w]}}
 if {{$bn>0}} {{mrd -bin -file {d}/baseline.f32 0x1A200000 [expr {{$bn*6}}]}} else {{close [open {d}/baseline.f32 w]}}
 set frame [word 0x13800080]
 if {{$frame!=0x02000000 && $frame!=0x02119400}} {{error "Invalid display frame"}}
 mrd -bin -file {d}/frame.bgr $frame 288000
 mrd -bin -file {d}/vdma.bin 0x43000000 16
 set f [open {d}/packet_origin.txt w];puts $f "actual_hardware_jtag_readback";close $f
 disconnect
 puts "BALANCED_BOARD_PACKET_READY"
}} why opts]}} {{puts stderr "BALANCED_BOARD_PACKET_FAILED $why";catch {{disconnect}};exit 1}}
exit 0
''',encoding='ascii')
 run(script,out/'request.log','BALANCED_BOARD_PACKET_READY')
 from validate_balanced_board import validate
 return validate(out,kind,physical=True)

def restore_previous(out):
 old=Path('E:/FPGA_Enhance_Work/road_car_bright_20261030_r1/firmware')
 run(old/'start_idle.tcl',out/'restore_ABI27.log','ROAD_RETINEX_IDLE_READY')
 return dict(status='PREVIOUS_ABI27_RELOADED_CAMERA_PREVIEW_IDLE',sd_written=False)
