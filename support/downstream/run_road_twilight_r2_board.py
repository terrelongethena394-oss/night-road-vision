"""Preserve the current ABI13 camera; activate ABI14 only after accepted quality+board gates."""
from pathlib import Path
import subprocess,sys,time
from road_twilight_r2_common import ROOT,read,write,sha
CURRENT=Path('E:/FPGA_Enhance_Work/road_enhance_20261027/firmware')
APP=ROOT/'firmware';HERE=Path(__file__).resolve().parent;XSCT='E:/Xilinx/Vitis/2020.2/bin/xsct.bat'
def main():
 assert read(ROOT/'fresh_complete.json')['deployment_decision']!='retain_current'
 for n,h in read(APP/'runtime_checksums.json').items():assert sha(APP/n)==h,n
 for n,h in read(CURRENT/'runtime_checksums.json').items():assert sha(CURRENT/n)==h,n
 p=subprocess.run([XSCT,str(APP/'scan_only.tcl')],capture_output=True,text=True,timeout=50);(APP/'scan_only.log').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0 and 'ROAD_TWILIGHT_SCAN_READY' in p.stdout,'JTAG not ready; current program not changed'
 receipt=APP/'session_r1.json';assert not receipt.exists();state=dict(status='NEW_MODEL_RAM_BOARD_TEST_RUNNING',started_epoch=time.time(),sd_written=False,flash_written=False);ok=False
 try:
  with (APP/'test_console.log').open('w',encoding='utf-8') as f:p=subprocess.run([XSCT,str(APP/'test_ram.tcl')],stdout=f,stderr=subprocess.STDOUT,timeout=1200)
  text=(APP/'test_console.log').read_text(encoding='utf-8',errors='replace');assert p.returncode==0 and 'ROAD_TWILIGHT_FULL_TEST_READBACK_COMPLETE' in text and 'ROAD_TWILIGHT_FULL_TEST_FAILED' not in text
  p=subprocess.run([sys.executable,str(HERE/'validate_road_twilight_r2_board.py')],capture_output=True,text=True);(APP/'validation.log').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stderr
  with (APP/'activation.log').open('w',encoding='utf-8') as f:p=subprocess.run([sys.executable,str(APP/'start_live.py')],stdout=f,stderr=subprocess.STDOUT,timeout=300)
  assert p.returncode==0 and 'ROAD_TWILIGHT_CAMERA_LIVE_READY' in (APP/'activation.log').read_text(encoding='utf-8',errors='replace')
  ok=True;state.update(status='NEW_MODEL_QUALITY_AND_BOARD_VALIDATED_RUNNING',default_pipe=read(APP/'arm_complete.json')['default_pipe'],model_weights_sha256=read(APP/'arm_complete.json')['weights_sha256'])
 finally:
  if not ok:
   restored=False
   for attempt in range(2):
    p=subprocess.run([sys.executable,str(CURRENT/'start_auto_live.py')],capture_output=True,text=True,timeout=180);text=p.stdout+p.stderr;(APP/f'rollback_attempt{attempt}.log').write_text(text,encoding='utf-8')
    if p.returncode==0 and 'ROAD_ENHANCE_CAMERA_LIVE_READY' in text:restored=True;break
    if 'Camera app error 220' not in text:break
   state['previous_enhanced_view_restored']=restored;state['status']='REQUIRES_REVIEW_PREVIOUS_ABI13_RESTORED' if restored else 'RESTORE_REQUIRES_REPAIR'
  state['finished_epoch']=time.time();write(receipt,state);print(state,flush=True)
if __name__=='__main__':main()
