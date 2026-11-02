"""Activate already validated immutable firmware after a host-only checker repair."""
from pathlib import Path
import json,shutil,subprocess,sys,time
from road_enhance_common import ROOT,OLD,sha,write
APP=ROOT/'firmware'
def main():
 before=json.loads((APP/'session_r1.json').read_text(encoding='utf-8'));assert before['old_fp32_restored']
 repair=json.loads((ROOT/'renderer_repair.json').read_text(encoding='utf-8'));assert repair['validation_sha256']==sha(APP/'board_fixed_r1/validated.json')
 assert sha(APP/'road_enhance.elf')==repair['elf_unchanged_sha256']
 proof=json.loads((APP/'board_fixed_r1/validated.json').read_text(encoding='utf-8'));assert proof['default_view_all86_bytes_exact_to_original_arm']
 for n,h in json.loads((APP/'runtime_checksums.json').read_text(encoding='utf-8')).items():assert sha(APP/n)==h,n
 evidence=ROOT/'attempts/renderer_ui_header';saved=evidence/'session_after_validation_failure.json';assert not saved.exists();shutil.copy2(APP/'session_r1.json',saved)
 state=dict(status='ACTIVATING_VALIDATED_ENHANCEMENT_AFTER_HOST_CHECKER_REPAIR',started_epoch=before['started_epoch'],activation_started_epoch=time.time(),default_mode=2,sd_written=False,flash_written=False,numerics_and_video_validated=True,intermediate_old_fp32_restored=True,prior_failure_record=str(saved),renderer_repair_sha256=sha(ROOT/'renderer_repair.json'));success=False
 try:
  for attempt in range(2):
   p=subprocess.run([sys.executable,str(APP/'start_auto_live.py')],capture_output=True,text=True,timeout=180);text=p.stdout+p.stderr
   (APP/f'activate_auto_attempt{attempt}.log').write_text(text,encoding='utf-8')
   if p.returncode==0 and 'ROAD_ENHANCE_CAMERA_LIVE_READY' in text:
    (APP/'activate_auto.log').write_text(text,encoding='utf-8');success=True;break
   if attempt==0 and 'Camera app error 220' in text:continue
   raise RuntimeError('Enhanced camera startup failed; inspect activation attempt log')
  assert success
  state.update(status='ENHANCED_VIEW_RAW_DETECTION_DEPLOYED_AND_LIVE',enhanced_view_activated=True,detector_input='raw',experimental_enhanced_detector_input_enabled=False)
 finally:
  if not success:
   p=subprocess.run([sys.executable,str(OLD/'start_hybrid_ram.py')],capture_output=True,text=True,timeout=180);text=p.stdout+p.stderr;(APP/'rollback_after_activation.log').write_text(text,encoding='utf-8');state['old_fp32_restored']=p.returncode==0 and 'ROAD_HYBRID_CAMERA_LIVE_READY' in text;state['status']='ACTIVATION_FAILED_OLD_FP32_RESTORED' if state['old_fp32_restored'] else 'ROLLBACK_REQUIRES_REPAIR'
  state['finished_epoch']=time.time();write(APP/'session_r1.json',state);print(json.dumps(state,indent=2),flush=True)
if __name__=='__main__':main()
