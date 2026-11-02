"""RAM-only physical acceptance with bounded recovery on any failure."""
from pathlib import Path
import shutil,subprocess,sys,time,json,hashlib
BASE=Path('E:/FPGA_Enhance_Work');BUNDLE=BASE/'road_detail_experiment_20261028';ROOT=BASE/'road_detail_board_20261028_r1';APP=ROOT/'firmware';HERE=Path(__file__).resolve().parent;XSCT='E:/Xilinx/Vitis/2020.2/bin/xsct.bat'
def write(p,v):p.write_text(json.dumps(v,indent=2),encoding='utf-8')
def main():
 ROOT.mkdir(exist_ok=False)
 for folder in [BUNDLE/'firmware',BUNDLE/'previous_verified']:
  for n,h in json.loads((folder/'runtime_checksums.json').read_text(encoding='utf-8')).items():assert hashlib.sha256((folder/n).read_bytes()).hexdigest()==h,n
 shutil.copytree(BUNDLE/'firmware',APP);proof=json.loads((APP/'arm_complete.json').read_text());cases=proof['cases'];first=cases[0]['name'];entries=' '.join('{%s} {%d %d %d}'%(r['name'],i+1,r['input_fnv'],r['roi_fnv']) for i,r in enumerate(cases))
 tcl='''source [file join [file dirname [file normalize [info script]]] camera_common.tcl]
set out $root/physical_r1
if {[file exists $out]} {error "Preserve previous acceptance"}
set cases [dict create CASES]
proc test {name detail trace} {
 global cases root
 lassign [dict get $cases $name] photo expected rexpected
 mwr 0x13800178 $detail
 mwr 0x13800188 $rexpected
 dow -data $root/runtime/cases/$name/roi400.u32 0x16900000
 catch {con}
 rc_test $name $photo $expected $trace
}
proc packet {folder trace} {
 file mkdir $folder
 mrd -bin -file $folder/mail.bin 0x13800000 128
 mrd -bin -file $folder/ui.u32 0x16500000 16
 foreach {name addr count} {raw.u32 0x16700000 96000 enhanced.u32 0x16100000 96000 live.u32 0x16000000 96000 live_roi.u32 0x16800000 96000 heads.f32 0x16400000 58800 decoded.f32 0x16300000 56700 prep.rgb 0x13200000 76800} {mrd -bin -file $folder/$name $addr $count}
 set n [word 0x138000d0]
 if {$n<0 || $n>300} {error "Invalid boxes"}
 if {$n} {mrd -bin -file $folder/boxes.f32 0x16200000 [expr {$n*6}]} else {close [open $folder/boxes.f32 w]}
 if {[word 0x1380018c]} {
  mrd -bin -file $folder/roi.u32 0x16a00000 96000
  mrd -bin -file $folder/full_heads.f32 0x17200000 58800
  mrd -bin -file $folder/full_decoded.f32 0x17100000 56700
  mrd -bin -file $folder/full_prep.rgb 0x17300000 76800
 }
 set left [word 0x138001fc]
 if {$left ni {369098752 375390208}} {error "Bad left source"}
 mrd -bin -file $folder/left.u32 $left 96000
 set frame [word 0x13800080]
 if {$frame!=0x02000000 && $frame!=0x02119400} {error "Bad frame"}
 mrd -bin -file $folder/frame.bgr $frame 288000
 set slot [word 0x138000f4]
 if {$slot>1} {error "Bad capture slot"}
 mrd -bin -file $folder/capture.bgr [expr {0x06000000+$slot*1152000}] 288000
 if {$trace} {mrd -bin -file $folder/all86.f32 0x14000000 4961200}
}
proc idle {} {
 mwr 0x1380000c 0
 for {set i 0} {$i<400} {incr i} {after 100;rc_check;if {[word 0x13800008] in {1 5}} {return}}
 error "Safe idle timeout"
}
if {[catch {
 connect -url tcp:127.0.0.1:3121
 targets -set -filter {name =~ "ARM*#0"} -timeout 10
 rc_check
 idle
 file mkdir $out
 set first FIRST
 foreach detail {0 1} {
  for {set j 0} {$j<4} {incr j} {
   test $first $detail 0
   mrd -bin -file $out/timing${detail}_${j}.bin 0x13800000 128
   puts "DETAIL_TIMING $detail $j"
  }
  packet $out/${first}_mode${detail} 0
 }
 mwr 0x13800120 0
 test $first 1 0
 packet $out/cpu_detail 0
 mwr 0x13800120 1
 test $first 1 1
 packet $out/trace_first 1
 dict for {name shape} $cases {
  if {$name eq $first} {continue}
  foreach detail {0 1} {test $name $detail 0;packet $out/${name}_mode${detail} 0;puts "DETAIL_FIXED $name $detail"}
 }
 foreach detail {0 1} {
  mwr 0x13800178 $detail
  set before [word 0x138000cc]
  mwr 0x1380000c 3
  set ready 0
  for {set i 0} {$i<400} {incr i} {
   after 100;rc_check
   if {[word 0x138000cc]>=$before+2 && [word 0x1380018c]==$detail} {set ready 1;break}
  }
  if {!$ready} {error "Live mode failed"}
  set begin [word 0x138000cc];set vbegin [word 0x1380009c];set start [clock milliseconds]
  after 20000
  set finish [clock milliseconds];set done [word 0x138000cc];set views [word 0x1380009c]
  rc_pause
  packet $out/live${detail} 0
  set f [open $out/live${detail}/cadence.txt w];puts $f "$start $finish $begin $done $vbegin $views";close $f
 }
 close [open $out/COMPLETE w]
 disconnect
 puts "DETAIL_ACCEPTANCE_READBACK_COMPLETE"
} why opts]} {
 puts stderr "DETAIL_ACCEPTANCE_FAILED $why"
 if {[dict exists $opts -errorinfo]} {puts stderr [dict get $opts -errorinfo]}
 catch {disconnect};exit 1
}
exit 0
'''.replace('CASES',entries).replace('FIRST','{'+first+'}')
 # Allowed display-left sources are RC_LIVE0x16000000 and RC_RAW_RESULT0x16700000.
 tcl=tcl.replace('369098752 375390208','369098752 376438784')
 (APP/'acceptance.tcl').write_text(tcl,encoding='ascii');state={'status':'RAM_ACCEPTANCE_RUNNING','sd_written':False,'flash_written':False};ok=False
 try:
  with (ROOT/'startup.log').open('w') as f:p=subprocess.run([sys.executable,str(APP/'experiment.py'),'start'],stdout=f,stderr=subprocess.STDOUT,timeout=500)
  assert p.returncode==0,'Experimental startup failed'
  with (ROOT/'test.log').open('w') as f:p=subprocess.run([XSCT,str(APP/'acceptance.tcl')],stdout=f,stderr=subprocess.STDOUT,timeout=1800)
  assert p.returncode==0 and 'DETAIL_ACCEPTANCE_READBACK_COMPLETE' in (ROOT/'test.log').read_text(),'Readback failed'
  p=subprocess.run([sys.executable,str(HERE/'validate_detail_board_r1.py')],capture_output=True,text=True);(ROOT/'validation.log').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stderr
  with (ROOT/'activate_default.log').open('w') as f:p=subprocess.run([sys.executable,str(APP/'experiment.py'),'start'],stdout=f,stderr=subprocess.STDOUT,timeout=500)
  assert p.returncode==0,'Default restart failed';ok=True;state['status']='PHYSICAL_VALIDATED_EXPERIMENT_RUNNING_DEFAULT_SINGLE_PASS'
 finally:
  if not ok:
   restored=False
   for attempt in range(2):
    p=subprocess.run([sys.executable,str(BUNDLE/'previous_verified/start_auto_live.py')],capture_output=True,text=True,timeout=240);text=p.stdout+p.stderr;(ROOT/f'restore{attempt}.log').write_text(text,encoding='utf-8')
    if p.returncode==0 and 'ROAD_ENHANCE_CAMERA_LIVE_READY' in text:restored=True;break
    if 'Camera app error 220' not in text:break
   state.update(status='FAILED_ORIGINAL_RESTORED' if restored else 'FAILED_RESTORE_REQUIRES_ATTENTION',restored=restored)
  write(ROOT/'session.json',state);print(state,flush=True)
if __name__=='__main__':main()
