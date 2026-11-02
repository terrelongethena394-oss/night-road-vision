"""Prepare JTAG checks, startup and raw/auto switches without accessing hardware."""
from pathlib import Path
import json,shutil
from road_enhance_common import ROOT,OLD,NN,sha,write
HERE=Path(__file__).resolve().parent
def main():
 app=ROOT/'firmware';proof=json.loads((app/'arm_complete.json').read_text(encoding='utf-8'));assert (ROOT/'host_complete.json').exists()
 runtime=app/'runtime';fixtures=json.loads((NN/'export_complete.json').read_text())['fixtures']
 for f in fixtures:
  p=runtime/'cases'/f['name'];p.mkdir(parents=True);shutil.copy2(NN/'cases'/f['name']/'input400.u32',p/'input400.u32')
 common=(OLD/'camera_common.tcl').read_text().replace('!=11','!=13')
 common=common.replace('$out/mailbox.bin 0x13800000 72','$out/mailbox.bin 0x13800000 96').replace('$out/ui.u32 0x16500000 11','$out/ui.u32 0x16500000 15')
 common=common.replace('26112bb4c89f99eacbd05a7fa123b2b0f906952160287bfcc3c1be9321d00d28',proof['elf_sha256'])
 needle=' mrd -bin -file $out/result400.u32 0x16100000 96000';assert common.count(needle)==1
 common=common.replace(needle,needle+'\n mrd -bin -file $out/raw_result400.u32 0x16700000 96000\n mrd -bin -file $out/preprocessed.rgb 0x13200000 76800')
 (app/'camera_common.tcl').write_text(common,encoding='ascii')
 startup=(OLD/'start_hybrid_camera_only.tcl').read_text().replace('==11','==13').replace('road_hybrid.elf','road_enhance.elf').replace('ROAD_HYBRID_CAMERA_LIVE_READY','ROAD_ENHANCE_CAMERA_LIVE_READY')
 (app/'start_auto_live.tcl').write_text(startup,encoding='ascii')
 for mode,label in [(0,'raw'),(2,'auto'),(1,'enhanced_input_experiment')]:
  (app/f'switch_{label}.tcl').write_text('source [file join [file dirname [file normalize [info script]]] camera_common.tcl]\nconnect -url tcp:127.0.0.1:3121\ntargets -set -filter {name =~ "ARM*#0"} -timeout 10\nrc_check\nmwr 0x13800140 '+str(mode)+'\nputs "ROAD_ENHANCE_NEXT_RESULTS_'+label.upper()+'"\ndisconnect\nexit\n',encoding='ascii')
  (app/f'02_switch_{label}.cmd').write_text('@echo off\r\ncall "E:\\Xilinx\\Vitis\\2020.2\\bin\\xsct.bat" "%~dp0switch_'+label+'.tcl"\r\npause\r\n',encoding='ascii')
 test=(OLD/'test_full_ram.tcl').read_text().replace('physical_full_r1','board_fixed_r1').replace('road_hybrid.elf','road_enhance.elf').replace('==11','==13').replace('ROAD_HYBRID','ROAD_ENHANCE')
 # Keep the proven PL selected-layer mode1 fixed; compare enhancement mode0/1.
 test=test.replace('foreach {mode label} {0 cpu 1 hybrid}', 'foreach {mode label} {0 raw 1 input 2 view}').replace('mwr 0x13800120 $mode','mwr 0x13800120 1\n  mwr 0x13800140 $mode')
 test=test.replace('if {$mode==0} {compact $out/cpu_first} else {compact $out/$first}','if {$mode==0} {rc_packet $out/raw_first fixed $first 0} elseif {$mode==1} {rc_packet $out/input_first fixed $first 0} else {compact $out/$first}')
 test=test.replace('$folder/mailbox80.bin 0x13800000 80','$folder/mailbox96.bin 0x13800000 96').replace('$out/${label}_timing$j.bin 0x13800000 80','$out/${label}_timing$j.bin 0x13800000 96')
 needle=' mrd -bin -file $folder/head0.f32';pos=test.index(needle)
 test=test[:pos]+' mrd -bin -file $folder/raw_result400.u32 0x16700000 96000\n mrd -bin -file $folder/enhanced400.u32 0x16100000 96000\n mrd -bin -file $folder/preprocessed.rgb 0x13200000 76800\n'+test[pos:]
 test=test.replace('first_hybrid_full','first_view_full').replace('$out/first_view_full/mailbox80.bin 0x13800000 80','$out/first_view_full/mailbox96.bin 0x13800000 96')
 needle=' set f [open $out/COMPLETE.txt w]';assert test.count(needle)==1
 live=''' mwr 0x1380000c 0
 after 300
 mwr 0x13800140 2
 mwr 0x1380000c 3
 after 15000
 rc_pause
 rc_packet $out/live_auto live camera 0
 puts "ROAD_ENHANCE_LIVE_PACKET_COMPLETE"
'''
 test=test.replace(needle,live+needle);(app/'test_ram.tcl').write_text(test,encoding='ascii')
 (app/'scan_only.tcl').write_text((Path('E:/FPGA_Enhance_Work/road_qconv_app_20261027/scan_only.tcl')).read_text().replace('ROAD_QCONV_SCAN_READY','ROAD_ENHANCE_SCAN_READY'),encoding='ascii')
 checks={str(p.relative_to(app)):sha(p) for p in app.rglob('*') if p.is_file() and (p.parent==app and p.suffix in ['.elf','.bit','.xsa','.tcl'] or 'runtime' in p.relative_to(app).parts or 'source' in p.relative_to(app).parts)}
 write(app/'runtime_checksums.json',checks)
 start='''from pathlib import Path
import hashlib,json,subprocess
root=Path(__file__).resolve().parent
for n,h in json.loads((root/'runtime_checksums.json').read_text()).items():
 assert hashlib.sha256((root/n).read_bytes()).hexdigest()==h,n
print('ROAD_ENHANCE_RUNTIME_HASHES_PASS',flush=True)
p=subprocess.run(['E:/Xilinx/Vitis/2020.2/bin/xsct.bat',str(root/'start_auto_live.tcl')],capture_output=True,text=True)
(root/'last_start.log').write_text(p.stdout+p.stderr,encoding='utf-8');print(p.stdout+p.stderr)
assert p.returncode==0 and 'ROAD_ENHANCE_CAMERA_LIVE_READY' in p.stdout
'''
 (app/'start_auto_live.py').write_text(start,encoding='ascii')
 (app/'00_start_enhanced_detection.cmd').write_text('@echo off\r\n"E:\\FPGA_Enhance_Work\\nn_env312\\Scripts\\python.exe" "%~dp0start_auto_live.py"\r\npause\r\n',encoding='ascii')
 checks['start_auto_live.py']=sha(app/'start_auto_live.py');write(app/'runtime_checksums.json',checks)
 write(app/'test_prepared.json',dict(status='RAW_AUTO_PHYSICAL_PROTOCOL_AND_STARTUP_PREPARED_NO_BOARD_ACCESS',mailbox=13,default_mode=2,default_description='Enhanced view / raw detector',mode1='Explicit enhanced-input experiment',pl_mode=1,default_cap=proof['selected_cap'],same_detector_weights_and_bit=True,sd_written=False));print('ROAD_ENHANCE_TOOLS_READY',flush=True)
if __name__=='__main__':main()
