"""Local files only: test fixtures, bounded launch/switch and independent recovery."""
from pathlib import Path
import shutil,subprocess,os,struct
import numpy as np
from road_roi_spatial_common import ROOT,BASE,read,write,sha
from road_roi_guard_common import fuse
HERE=Path(__file__).resolve().parent
APP=ROOT/'firmware_experiment'
CURRENT=BASE.parent/'road_enhance_20261027/firmware'

def main():
 proof=read(APP/'arm_complete.json');assert proof['default_roi_mode']==0 and not proof['verifier_included'];assert not (APP/'entries_complete.json').exists();policy=read(ROOT/'protocol.json')['roi_policy']
 for row in proof['cases']:
  name=row['name'];folder=APP/'runtime/cases'/name;full=ROOT/'native_detector_full/cases'/name/'host/boxes400.f32';roi=ROOT/'native_detector_roi/cases'/name/'host/boxes400.f32';a=np.fromfile(full,'<f4').reshape(-1,6);z=np.fromfile(roi,'<f4').reshape(-1,6);z=z[(z[:,0]>1)&(z[:,1]>1)&(z[:,2]<399)&(z[:,3]<239)].copy();z[:,[0,2]]=z[:,[0,2]]*.5+100;z[:,[1,3]]=z[:,[1,3]]*.5+60;b=np.asarray(fuse(a,z,policy),'<f4').reshape(-1,6);b=b[b[:,4]>=.25];a.tofile(folder/'gold_raw_boxes400.f32');b.tofile(folder/'gold_detail_boxes400.f32')
  # Exercise the actual16-word UI and renderer guard bytes offline, without calling it board evidence.
  for mode,boxes in [(0,a),(1,b)]:
   ui=[0,1,1,0,0,0,len(boxes),1,1,0,0,0,0,32,0,mode];struct.pack('<16I',*ui)
   (folder/'host_ui.u32').write_bytes(struct.pack('<16I',*ui));boxes.tofile(folder/'host_boxes.f32');p=subprocess.run([str(APP/'host/render.exe'),str(folder/'input400.u32'),str(folder/'input400.u32'),str(folder/'host_boxes.f32'),str(folder/'host_ui.u32'),str(folder/'host_frame.bgr')],capture_output=True,text=True);assert p.returncode==0 and 'GUARDS_PASS' in p.stdout
 startup=(CURRENT/'start_auto_live.tcl').read_text(encoding='utf-8').replace('==13','==15').replace('road_enhance.elf','road_detail.elf').replace('ROAD_ENHANCE_CAMERA_LIVE_READY','ROAD_DETAIL_EXPERIMENT_LIVE_READY');(APP/'start_default.tcl').write_text(startup,encoding='ascii')
 switch='''source [file join [file dirname [file normalize [info script]]] camera_common.tcl]
if {$argc!=1 || [lindex $argv 0] ni {0 1}} {error "Use mode0(single pass) or1(detail two passes)"}
set mode [lindex $argv 0]
if {[catch {
 connect -url tcp:127.0.0.1:3121
 targets -set -filter {name =~ "ARM*#0"} -timeout 10
 rc_check
 set before [word 0x138000cc]
 mwr 0x13800178 $mode
 mwr 0x1380000c 3
 set ok 0
 for {set i 0} {$i<300} {incr i} {
  after 100
  rc_check
  if {[word 0x138000cc]>$before && [word 0x1380018c]==$mode} {set ok 1;break}
 }
 if {!$ok} {error "New selected-mode camera result not observed"}
 disconnect
 puts "ROAD_DETAIL_MODE_APPLIED $mode"
} why opts]} {
 puts stderr "ROAD_DETAIL_SWITCH_FAILED $why"
 catch {disconnect}
 exit 1
}
exit 0
''';(APP/'switch_mode.tcl').write_text(switch,encoding='ascii')
 cases=' '.join('{%s} {%d %d %d}'%(r['name'],i+1,r['input_fnv'],r['roi_fnv']) for i,r in enumerate(proof['cases']))
 test='''source [file join [file dirname [file normalize [info script]]] camera_common.tcl]
set cases [dict create CASES]
if {$argc!=2 || ![dict exists $cases [lindex $argv 0]] || [lindex $argv 1] ni {0 1}} {error "Supply fixture name and mode0/1"}
set id [lindex $argv 0]
set detail [lindex $argv 1]
lassign [dict get $cases $id] photo expected roi_expected
if {[catch {
 connect -url tcp:127.0.0.1:3121
 targets -set -filter {name =~ "ARM*#0"} -timeout 10
 rc_check
 mwr 0x1380000c 0
 set idle 0
 for {set i 0} {$i<400} {incr i} {
  after 100
  rc_check
  if {[word 0x13800008] in {1 5}} {set idle 1;break}
 }
 if {!$idle} {error "Cannot stop at a safe idle boundary"}
 mwr 0x13800178 $detail
 mwr 0x13800188 $roi_expected
 dow -data $root/runtime/cases/$id/roi400.u32 0x16900000
 catch {con}
 rc_test $id $photo $expected 0
 set out $root/static_readback/${id}_mode${detail}
 if {[file exists $out]} {error "Preserve earlier test readback; choose another fixture or archive it"}
 file mkdir $out
 mrd -bin -file $out/mailbox128.bin 0x13800000 128
 mrd -bin -file $out/ui.u32 0x16500000 16
 mrd -bin -file $out/raw_result400.u32 0x16700000 96000
 mrd -bin -file $out/enhanced400.u32 0x16100000 96000
 set count [word 0x138000d0]
 if {$count<0 || $count>300} {error "Invalid box count"}
 if {$count>0} {mrd -bin -file $out/boxes400.f32 0x16200000 [expr {$count*6}]} else {close [open $out/boxes400.f32 w]}
 mrd -bin -file $out/head_all.f32 0x16400000 58800
 mrd -bin -file $out/decoded.f32 0x16300000 56700
 if {$detail} {
  mrd -bin -file $out/roi_result400.u32 0x16A00000 96000
  mrd -bin -file $out/full_head_all.f32 0x17200000 58800
  mrd -bin -file $out/full_decoded.f32 0x17100000 56700
 }
 set frame [word 0x13800080]
 if {$frame!=0x02000000 && $frame!=0x02119400} {error "Invalid display address"}
 mrd -bin -file $out/frame.bgr $frame 288000
 disconnect
 puts "ROAD_DETAIL_STATIC_READBACK_COMPLETE $id $detail"
} why opts]} {
 puts stderr "ROAD_DETAIL_STATIC_FAILED $why"
 catch {disconnect}
 exit 1
}
exit 0
'''.replace('CASES',cases);(APP/'test_static.tcl').write_text(test,encoding='ascii')
 python='''from pathlib import Path
import json,hashlib,subprocess,sys
root=Path(__file__).resolve().parent
for n,h in json.loads((root/'runtime_checksums.json').read_text(encoding='utf-8')).items():assert hashlib.sha256((root/n).read_bytes()).hexdigest()==h,n
args=sys.argv[1:]
if not args:raise RuntimeError('Use start, switch0/1, or static fixture mode')
if args[0]=='start':command=[str(root/'start_default.tcl')]
elif args[0]=='switch' and len(args)==2 and args[1] in ['0','1']:command=[str(root/'switch_mode.tcl'),args[1]]
elif args[0]=='static' and len(args)==3 and args[2] in ['0','1']:command=[str(root/'test_static.tcl'),args[1],args[2]]
else:raise RuntimeError('Invalid experiment command')
for attempt in range(2):
 p=subprocess.run(['E:/Xilinx/Vitis/2020.2/bin/xsct.bat',*command],capture_output=True,text=True,timeout=240)
 text=p.stdout+p.stderr;(root/f'last_{args[0]}_attempt{attempt}.log').write_text(text,encoding='utf-8');print(text)
 if p.returncode==0 and any(marker in p.stdout for marker in ['ROAD_DETAIL_EXPERIMENT_LIVE_READY','ROAD_DETAIL_MODE_APPLIED','ROAD_DETAIL_STATIC_READBACK_COMPLETE']):break
 if args[0]=='start' and attempt==0 and 'Camera app error 220' in text:continue
 raise RuntimeError('Experiment command failed; original recovery entry remains available')
else:raise RuntimeError('Two bounded startup attempts failed')
''';(APP/'experiment.py').write_text(python,encoding='ascii')
 # Scripts are syntax-checked, never executed against hardware during this preparation.
 compile(python,str(APP/'experiment.py'),'exec')
 checks={str(p.relative_to(APP)):sha(p) for p in APP.rglob('*') if p.is_file() and (p.parent==APP and p.suffix in ['.tcl','.py','.elf','.bit','.xsa'] or 'runtime' in p.relative_to(APP).parts or 'source' in p.relative_to(APP).parts)};checks['arm_complete.json']=sha(APP/'arm_complete.json');write(APP/'runtime_checksums.json',checks)
 write(APP/'entries_complete.json',dict(status='EXPERIMENT_ENTRIES_AND_7_STATIC_GOLD_PAIRS_PREPARED_NOT_BOARD_EXECUTED',default_roi_mode=0,cases=len(proof['cases']),host_renderer14_guard_checks_passed=True,UI_words=16,hardware_test_status='PENDING_USER_EXPLICITLY_DEFERRED_BOARD_TEST',hardware_access=False,sd_written=False));print('ROI_EXPERIMENT_LOCAL_ENTRIES_AND_GOLDS_READY',flush=True)
if __name__=='__main__':main()
