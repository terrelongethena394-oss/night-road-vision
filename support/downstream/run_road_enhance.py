"""Validate the requested feature in RAM; rollback on error, retain view mode2 on success."""
from pathlib import Path
import json,subprocess,sys,time
from road_enhance_common import ROOT,OLD,sha,write
HERE=Path(__file__).resolve().parent
APP=ROOT/'firmware'
XSCT='E:/Xilinx/Vitis/2020.2/bin/xsct.bat'
def main():
 for n,h in json.loads((APP/'runtime_checksums.json').read_text(encoding='utf-8')).items():assert sha(APP/n)==h,n
 reg=json.loads((ROOT/'regression480/complete.json').read_text());assert reg['selected_unchanged']
 source=(APP/'source/road_camera_main.c').read_text();assert 'm[80]=2U;' in source and 'pipe==1U?RC_ENH_INPUT:RC_INPUT' in source
 write(ROOT/'integration_addendum.json',dict(status='DEFAULT_DISPLAY_ONLY_ENHANCEMENT_FROZEN_AFTER_FAILED_ENHANCED_INPUT_REGRESSION',regression_sha256=sha(ROOT/'regression480/complete.json'),default_mode=2,default_detector_input='unchanged raw RGB',default_display='bounded adaptive gamma on same frozen RGB snapshot',experimental_mode1='Enhancement before detection; accuracy regression measured, not default',new_accuracy_improvement_claimed=False,sd_written=False))
 p=subprocess.run([sys.executable,str(OLD/'start_hybrid_ram.py'),'--verify-only'],capture_output=True,text=True);assert p.returncode==0 and 'ROAD_HYBRID_RUNTIME_HASHES_PASS' in p.stdout
 scan=subprocess.run([XSCT,str(APP/'scan_only.tcl')],capture_output=True,text=True,timeout=50);(APP/'scan_only.log').write_text(scan.stdout+scan.stderr,encoding='utf-8');assert scan.returncode==0 and 'ROAD_ENHANCE_SCAN_READY' in scan.stdout,'No chip detected; board not reset or downloaded'
 receipt=APP/'session_r1.json';assert not receipt.exists();state=dict(status='ENHANCEMENT_RAM_TEST_RUNNING',started_epoch=time.time(),sd_written=False,flash_written=False,default_mode=2);write(receipt,state);success=False
 try:
  with (APP/'test_console.log').open('w',encoding='utf-8') as f:p=subprocess.run([XSCT,str(APP/'test_ram.tcl')],stdout=f,stderr=subprocess.STDOUT,timeout=1200)
  text=(APP/'test_console.log').read_text(encoding='utf-8',errors='replace');assert p.returncode==0 and 'ROAD_ENHANCE_FULL_TEST_READBACK_COMPLETE' in text and 'ROAD_ENHANCE_FULL_TEST_FAILED' not in text
  p=subprocess.run([sys.executable,str(HERE/'validate_road_enhance.py')],capture_output=True,text=True);(APP/'validation.log').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stderr
  state['numerics_and_video_validated']=True
  with (APP/'activate_auto.log').open('w',encoding='utf-8') as f:p=subprocess.run([sys.executable,str(APP/'start_auto_live.py')],stdout=f,stderr=subprocess.STDOUT,timeout=180)
  assert p.returncode==0 and 'ROAD_ENHANCE_CAMERA_LIVE_READY' in (APP/'activate_auto.log').read_text(encoding='utf-8',errors='replace')
  success=True;state.update(status='ENHANCED_VIEW_RAW_DETECTION_DEPLOYED_AND_LIVE',enhanced_view_activated=True,detector_input='raw',experimental_enhanced_detector_input_enabled=False)
 except Exception as e:
  state['failure']=repr(e);raise
 finally:
  if not success:
   with (APP/'rollback.log').open('w',encoding='utf-8') as f:p=subprocess.run([sys.executable,str(OLD/'start_hybrid_ram.py')],stdout=f,stderr=subprocess.STDOUT,timeout=180)
   state['old_fp32_restored']=p.returncode==0 and 'ROAD_HYBRID_CAMERA_LIVE_READY' in (APP/'rollback.log').read_text(encoding='utf-8',errors='replace')
   state['status']='TEST_REQUIRES_REVIEW_OLD_FP32_RESTORED' if state['old_fp32_restored'] else 'ROLLBACK_REQUIRES_REPAIR'
  state['finished_epoch']=time.time();write(receipt,state);print(json.dumps(state,indent=2),flush=True)
if __name__=='__main__':main()
