"""One safe entry: probe, program RAM, verify, and restore ABI27 on failure."""
from pathlib import Path
import subprocess,time,traceback
from balanced_board_tools import ROOT,APP,STUDY,XSCT,start,capture,restore_previous
from car_box_refine_common import read,write,sha

def main():
 assert read(STUDY/'confirmation/fresh_result.json')['accepted'] and read(ROOT/'reader_smoke.json')['physical_readback'] is False
 out=ROOT/('board_20261030_'+time.strftime('%H%M%S'));out.mkdir()
 with (out/'probe.log').open('w',encoding='utf-8') as f:p=subprocess.run([XSCT,str(STUDY/'readonly_jtag.tcl')],stdout=f,stderr=subprocess.STDOUT,timeout=50)
 log=(out/'probe.log').read_text(encoding='utf-8',errors='replace')
 if 'READONLY_JTAG_TARGET_OK' not in log:
  write(ROOT/'board_waiting.json',dict(status='ABI28_READY_BUT_JTAG_CHIP_NOT_DETECTED_NO_DOWNLOAD',probe=str(out/'probe.log'),offline_accepted=True,firmware_sha256=sha(APP/'road_detail.elf'),hardware_programmed=False,sd_written=False))
  print('BALANCED_BOARD_WAITING_NO_DOWNLOAD',log[-1500:],flush=True);return
 started=False
 try:
  started=True;start(out);packets=[]
  for i,name in enumerate(['road0','road1','gray96','black']):packets.append(capture(out/('photo_'+str(i)),5,ROOT/'fixtures'/(name+'.bgr'),i+1,1))
  packets.append(capture(out/'camera_1',4,view=1))
  packets.append(capture(out/'road_revisit',5,ROOT/'fixtures/road0.bgr',6,0))
  # Deterministic source, same inputs/boxes even after live camera branch.
  first=out/'photo_0';last=out/'road_revisit'
  for name in ['raw.u32','enhanced.u32','baseline.f32','boxes.f32','refiner_outputs.f32']:
   assert (first/name).read_bytes()==(last/name).read_bytes(),name
  assert all(p['physical_readback'] and p['status']=='ABI28_ACTUAL_BOARD_PACKET_PASS' for p in packets)
  proof=read(APP/'arm_complete.json');result=dict(status='ABI28_BALANCED_CAR_ACTUAL_BOARD_VERIFIED',evidence=str(out),packets=len(packets),
   detector_neural_comparisons=sum(len(p['detector_native_comparisons']) for p in packets),actual_refiner_calls=sum(p['refiner_calls'] for p in packets),
   source_and_all_views_verified=True,frame_exact_all=True,repeated_fixed_input_deterministic=True,
   processing_seconds=[p['processing_seconds'] for p in packets],last_frame=str(last/'lcd_readback.png'),
   elf_sha256=proof['elf_sha256'],offline_confirmation_sha256=sha(STUDY/'confirmation/fresh_result.json'),
   hardware_accuracy_scope='Sample-wise board/C implementation equivalence;304-image accuracy was measured in portable C on PC, not all on physical board.',
   sd_written=False)
  write(ROOT/'board_verified.json',result);print('BALANCED_ACTUAL_BOARD_VERIFIED',result,flush=True)
 except Exception as exc:
  failure=dict(status='ABI28_BOARD_CHECK_FAILED',error=str(exc),traceback=traceback.format_exc(),evidence=str(out),sd_written=False)
  if started:
   try:failure['restore']=restore_previous(out)
   except Exception as restore:failure['restore']=dict(status='RESTORE_NOT_COMPLETED',error=str(restore))
  write(ROOT/'board_failed.json',failure);raise

if __name__=='__main__':main()
