"""Verify new display and prove all road neural outputs unchanged from ABI26."""
import datetime,subprocess,sys
from car_pair_tools import *
from car_bright_mode import display_mode
OLDROOT=BASE/'road_car_pair_20261030_r1'
LAB=BASE/'road_shadowlift_20261030_r1'
PY='E:/FPGA_Enhance_Work/nn_env312/Scripts/python.exe'

def road_gold(packet):
 gold=Path(read(OLDROOT/'board_verified.json')['last_packet'])
 for prefix in ['stable_decoded','decoded']:
  for i in range(4):assert (packet/(prefix+str(i)+'.f32')).read_bytes()==(gold/(prefix+str(i)+'.f32')).read_bytes()
 for name in ['raw.u32','boxes.f32','baseline.f32']:assert (packet/name).read_bytes()==(gold/name).read_bytes()

def main():
 assert all(sha(APP/n)==h for n,h in read(APP/'runtime_checksums.json').items());out=ROOT/('board_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'));out.mkdir();write(out/'protocol.json',dict(status='FROZEN_BEFORE_ABI27_DOWNLOAD',fixed=['road','dark_traffic','gray96','black'],camera=1,road_revisits=2,display_mode_checks=[1,0],neural='Every road packet8 decoded arrays/boxes/raw must equal actual ABI26 byte for byte; all packets vs C max.001/mean.00002',new_enhancement='C reference max1LSB,mean<=.01,SSIM>=.99999; no new255 saturation relative to frozen baseline, raw input/model/PL unchanged',restore='Verified ABI26 fixed-road car comparison',sd_written=False))
 scan=out/'scan.tcl';scan.write_text('connect -url tcp:127.0.0.1:3121\nputs [targets]\ntargets -set -filter {name =~ "ARM*#0"} -timeout 10\nputs "CAR_BRIGHT_ARM_FOUND"\ndisconnect\nexit 0\n',encoding='ascii')
 try:run(scan,out/'scan.log','CAR_BRIGHT_ARM_FOUND',45)
 except Exception as e:write(ROOT/'board_session.json',dict(status='ABI27_NOT_DOWNLOADED_NO_TARGET',error=str(e),evidence=str(out),sd_written=False));raise
 try:
  start(out);results=[]
  for i,name in enumerate(['road','dark_traffic','gray96','black']):
   source=ROOT/'fixtures/road/source800.bgr' if i==0 else out/(name+'.bgr')
   if i==1:
    p=BASE/'road_accuracy_20261030_r1/firmware/runtime/cases/babf991d-b4102dd2/sensor800.png';im=np.asarray(Image.open(p).convert('RGB'));source.write_bytes(im[:,:,::-1].tobytes())
   elif i>1:source.write_bytes(np.full((480,800,3),96 if i==2 else 0,np.uint8).tobytes())
   packet=out/('photo_'+str(i));r=capture(packet,5,source,i+1)
   if i==0:road_gold(packet)
   results.append(r)
  cam=capture(out/'camera_1',4);r1=capture(out/'road_revisit_1',5,ROOT/'fixtures/road/source800.bgr',1);road_gold(out/'road_revisit_1')
  display_mode(out/'mode_models',1,out/'road_revisit_1');display_mode(out/'mode_enhancement',0,out/'road_revisit_1')
  final=capture(out/'road_revisit_2',5,ROOT/'fixtures/road/source800.bgr',1);road_gold(out/'road_revisit_2')
  receipt=dict(status='ABI27_CAR_BRIGHT_DISPLAY_BOARD_VERIFIED',evidence=str(out),photo_results=results,camera_results=[cam],road_revisits=[r1,final],old_ABI26_all_road_8_decodes_and_boxes_byte_exact=True,display_modes_c_frame_byte_exact=[1,0],new_inference_after_mode_switch_pass=True,elf_sha256=sha(APP/'road_detail.elf'),bit_sha256=sha(APP/'display.bit'),weights_sha256=read(APP/'arm_complete.json')['weights_sha256'],last_packet=str(out/'road_revisit_2'),physical_screen_check='Prior ABI26 normal; ABI27 digital framebuffer inspected separately',sd_written=False);write(ROOT/'board_verified.json',receipt);write(ROOT/'board_session.json',receipt);write(out/'complete.json',receipt);print('CAR_BRIGHT_BOARD_ACCEPTANCE_COMPLETE',receipt,flush=True)
 except Exception as e:
  write(out/'failure.json',dict(error=str(e),restore='ABI26',sd_written=False));restore=out/'restore26.py';restore.write_text('import sys\nfrom pathlib import Path\nsys.path.insert(0,"E:/FPGA_Enhance_Work/road_car_pair_20261030_r1/tools")\nfrom car_pair_tools import *\nout=Path(sys.argv[1]);out.mkdir()\nstart(out)\ncapture(out/"shot",5,ROOT/"fixtures/road/source800.bgr",1)\nprint("RESTORE_ABI26_FIXED_ROAD_READY",flush=True)\n',encoding='ascii');log=out/'restore26.log'
  with log.open('w',encoding='utf-8') as f:p=subprocess.run([PY,str(restore),str(out/'restored26')],stdout=f,stderr=subprocess.STDOUT,timeout=600)
  restored=p.returncode==0 and 'RESTORE_ABI26_FIXED_ROAD_READY' in log.read_text();write(ROOT/'board_session.json',dict(status='ABI27_REJECTED_ABI26_RESTORED' if restored else 'ABI27_FAILED_RESTORE_NEEDS_CONNECTION',error=str(e),evidence=str(out),sd_written=False));raise
if __name__=='__main__':main()
