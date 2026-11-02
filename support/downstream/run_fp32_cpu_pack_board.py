"""Same-ELF cache-layout A/B, exact outputs, native reference, camera and rollback."""
from pathlib import Path
import subprocess,sys,struct,json,statistics,time
import numpy as np
from prepare_fp32_cpu_pack import ROOT,CURRENT,BASE,read,write,sha
from verify_road_arm_host import compare_boxes
from road_enhance_common import enhance
APP=ROOT/'firmware';XSCT='E:/Xilinx/Vitis/2020.2/bin/xsct.bat';REF=BASE/'road_roi_spatial_verifier_20261028'
def main():
 assert (ROOT/'native_complete.json').exists() and not (ROOT/'session.json').exists()
 for n,h in read(APP/'runtime_checksums.json').items():assert sha(APP/n)==h
 cases=read(APP/'arm_complete.json')['cases'];first=cases[0]['name'];entries=' '.join('{%s} {%d %d %d}'%(r['name'],i+1,r['input_fnv'],r['roi_fnv']) for i,r in enumerate(cases))
 tcl='''source [file join [file dirname [file normalize [info script]]] camera_common.tcl]
set out $root/physical_pack_r1
if {[file exists $out]} {error "Preserve previous run"}
set cases [dict create CASES]
proc inject {id cpu detail trace} {
 global root cases
 lassign [dict get $cases $id] photo expected rexp
 mwr 0x13800200 $cpu
 mwr 0x13800178 $detail
 mwr 0x13800188 $rexp
 dow -data $root/runtime/cases/$id/roi400.u32 0x16900000
 catch {con}
 rc_test $id $photo $expected $trace
}
proc packet {p detail video trace} {
 file mkdir $p
 mrd -bin -file $p/mail.bin 0x13800000 144
 mrd -bin -file $p/heads.f32 0x16400000 58800
 mrd -bin -file $p/decoded.f32 0x16300000 56700
 set n [word 0x138000d0]
 if {$n<0 || $n>300} {error "Invalid boxes"}
 if {$n} {mrd -bin -file $p/boxes.f32 0x16200000 [expr {$n*6}]} else {close [open $p/boxes.f32 w]}
 if {$detail} {mrd -bin -file $p/full_heads.f32 0x17200000 58800;mrd -bin -file $p/full_decoded.f32 0x17100000 56700}
 if {$trace} {mrd -bin -file $p/trace.f32 0x14000000 4961200}
 if {$video} {
  foreach {n a c} {ui.u32 0x16500000 16 raw.u32 0x16700000 96000 enhanced.u32 0x16100000 96000 live.u32 0x16000000 96000} {mrd -bin -file $p/$n $a $c}
  set left [word 0x138001fc];if {$left ni {369098752 376438784}} {error "Invalid draw source"}
  mrd -bin -file $p/left.u32 $left 96000
  set frame [word 0x13800080];if {$frame!=0x02000000 && $frame!=0x02119400} {error "Invalid frame"}
  mrd -bin -file $p/frame.bgr $frame 288000
  set slot [word 0x138000f4];if {$slot>1} {error "Invalid capture"}
  mrd -bin -file $p/capture.bgr [expr {0x06000000+$slot*1152000}] 288000
 }
}
if {[catch {
 connect -url tcp:127.0.0.1:3121
 targets -set -filter {name =~ "ARM*#0"} -timeout 10
 rc_check
 mwr 0x1380000c 0
 set ready 0
 for {set i 0} {$i<400} {incr i} {after 100;rc_check;if {[word 0x13800008] in {1 5}} {set ready 1;break}}
 if {!$ready} {error "Idle timeout"}
 file mkdir $out
 set first FIRST
 foreach cpu {0 1} {
  inject $first $cpu 0 2
  mrd -bin -file $out/profile${cpu}.u64 0x17400000 174
  foreach detail {0 1} {
   for {set j 0} {$j<4} {incr j} {inject $first $cpu $detail 0;mrd -bin -file $out/time${cpu}_${detail}_${j}.bin 0x13800000 144;puts "PACK_TIMING $cpu $detail $j"}
   packet $out/${first}_${cpu}_${detail} $detail 1 0
  }
 }
 inject $first 1 0 1
 packet $out/trace_first 0 0 1
 dict for {id data} $cases {
  if {$id eq $first} {continue}
  foreach cpu {0 1} {inject $id $cpu 0 0;packet $out/${id}_${cpu}_0 0 0 0;puts "PACK_FIXED $id $cpu"}
 }
 foreach cpu {0 1} {
  mwr 0x13800200 $cpu
  mwr 0x13800178 0
  mwr 0x13800070 0
  set before [word 0x138000cc]
  mwr 0x1380000c 3
  set ready 0
  for {set i 0} {$i<400} {incr i} {after 100;rc_check;if {[word 0x138000cc]>=$before+2 && [word 0x13800210]==$cpu} {set ready 1;break}}
  if {!$ready} {error "Live mode did not commit"}
  set a [word 0x138000cc];set va [word 0x1380009c];set start [clock milliseconds]
  after 20000
  set stop [clock milliseconds];set b [word 0x138000cc];set vb [word 0x1380009c]
  rc_pause
  packet $out/live${cpu} 0 1 0
  set f [open $out/live${cpu}/cadence.txt w];puts $f "$start $stop $a $b $va $vb";close $f
 }
 close [open $out/COMPLETE w]
 disconnect
 puts "CPU_PACK_PHYSICAL_READBACK_COMPLETE"
} why opts]} {
 puts stderr "CPU_PACK_TEST_FAILED $why"
 if {[dict exists $opts -errorinfo]} {puts stderr [dict get $opts -errorinfo]}
 catch {disconnect};exit 1
}
exit 0
'''.replace('CASES',entries).replace('FIRST','{'+first+'}');(APP/'pack_acceptance.tcl').write_text(tcl,encoding='ascii')
 state=dict(status='CPU_PACK_TEMP_BOARD_TEST_RUNNING',sd_written=False);ok=False
 try:
  with (ROOT/'startup.log').open('w') as f:p=subprocess.run([sys.executable,str(APP/'experiment.py'),'start'],stdout=f,stderr=subprocess.STDOUT,timeout=500)
  assert p.returncode==0,'Startup failed'
  with (ROOT/'board_test.log').open('w') as f:p=subprocess.run([XSCT,str(APP/'pack_acceptance.tcl')],stdout=f,stderr=subprocess.STDOUT,timeout=1800)
  assert p.returncode==0 and 'CPU_PACK_PHYSICAL_READBACK_COMPLETE' in (ROOT/'board_test.log').read_text(),'Board readback failed'
  result=validate(cases);write(ROOT/'validated.json',result)
  assert result['speedup_single']>=1.05,'Packing did not provide5% median gain'
  with (ROOT/'activate.log').open('w') as f:p=subprocess.run([sys.executable,str(APP/'experiment.py'),'start'],stdout=f,stderr=subprocess.STDOUT,timeout=500)
  assert p.returncode==0,'Restart failed';ok=True;state.update(status='CPU_PACK_BYTE_EXACT_FASTER_VALIDATED_AND_LIVE',speedup_single=result['speedup_single'])
 finally:
  if not ok:
   restored=False
   for attempt in range(2):
    p=subprocess.run([sys.executable,str(CURRENT/'experiment.py'),'start'],capture_output=True,text=True,timeout=500);text=p.stdout+p.stderr;(ROOT/f'restore{attempt}.log').write_text(text,encoding='utf-8')
    if p.returncode==0 and 'ROAD_DETAIL_EXPERIMENT_LIVE_READY' in text:restored=True;break
    if 'Camera app error 220' not in text:break
   state.update(status='NOT_PROMOTED_PREVIOUS_ABI15_RESTORED' if restored else 'RESTORE_NEEDS_REPAIR',restored=restored)
  write(ROOT/'session.json',state);print(state,flush=True)
def words(p):
 b=p.read_bytes();assert len(b)==576;return struct.unpack('<144I',b)
def floats(a,b,decoded=False):
 # Cross-platform libm may differ; unchanged byte identity is checked against
 # the same-ARM baseline separately, as preregistered and used by ABI15.
 assert a.shape==b.shape and np.isfinite(a).all();d=abs(a-b)
 if decoded:assert d[:,:4].max()<=.02 and d[:,4:].max()<=2e-4
 else:assert np.all(d<=1e-4+1e-4*abs(b))
def validate(cases):
 out=APP/'physical_pack_r1';assert (out/'COMPLETE').exists();first=cases[0]['name'];records=[]
 def mail(m,cpu,detail,live=False):
  assert m[:4]==(0x524f4144,16,3,1) and m[6]==0 and m[35]==m[41]==m[74]==0 and m[57]==1 and m[72]==1 and m[17]==1483844061 and m[77]==0x5041434b
  assert m[132]==cpu and m[99]==detail and m[80]==m[93]==2
  if not live:assert m[73]==12 and m[104]==12*(1+detail)
 def video(p):
  m=words(p/'mail.bin');raw=(p/'raw.u32').read_bytes();enh=(p/'enhanced.u32').read_bytes()
  def rgb(b):
   a=np.frombuffer(b,'<u4').reshape(240,400);return np.stack([a&255,(a>>8)&255,(a>>16)&255],2).astype(np.uint8)
  e,s=enhance(rgb(raw),1,32);assert np.array_equal(e,rgb(enh))
  p0=subprocess.run([str(APP/'host/render.exe'),str(p/'left.u32'),str(p/'enhanced.u32'),str(p/'boxes.f32'),str(p/'ui.u32'),str(p/'expected.bgr')],capture_output=True,text=True);assert p0.returncode==0 and 'GUARDS_PASS' in p0.stdout and (p/'expected.bgr').read_bytes()==(p/'frame.bgr').read_bytes()
  source=np.fromfile(p/'capture.bgr',np.uint8).reshape(480,800,3);a=((source.astype(np.uint16).reshape(240,2,400,2,3).sum((1,3))+2)//4).astype(np.uint32);assert (a[:,:,2]|(a[:,:,1]<<8)|(a[:,:,0]<<16)).astype('<u4').tobytes()==(p/'live.u32').read_bytes()
  return s
 for c in cases:
  name=c['name']
  for cpu in [0,1]:
   p=out/f'{name}_{cpu}_0';mail(words(p/'mail.bin'),cpu,0);ref=REF/'native_detector_full/cases'/name/'host';h=np.concatenate([np.fromfile(ref/'trace'/f'{tid:03d}.f32','<f4') for tid in [83,84,85]]);floats(np.fromfile(p/'heads.f32','<f4'),h);floats(np.fromfile(p/'decoded.f32','<f4').reshape(-1,9),np.fromfile(ref/'decoded.f32','<f4').reshape(-1,9),True);compare_boxes(np.fromfile(p/'boxes.f32','<f4').reshape(-1,6),np.fromfile(ref/'boxes400.f32','<f4').reshape(-1,6),.04)
  for n in ['heads.f32','decoded.f32','boxes.f32']:assert (out/f'{name}_0_0'/n).read_bytes()==(out/f'{name}_1_0'/n).read_bytes(),(name,n)
  original=CURRENT/'physical_r1'/f'{name}_mode0'
  for n in ['heads.f32','decoded.f32','boxes.f32']:assert (out/f'{name}_1_0'/n).read_bytes()==(original/n).read_bytes(),('PreviousARMbaseline',name,n)
  records.append(dict(name=name,outputs_byte_exact=True))
 for cpu in [0,1]:
  p=out/f'{first}_{cpu}_1';mail(words(p/'mail.bin'),cpu,1)
  for n in ['heads.f32','decoded.f32','full_heads.f32','full_decoded.f32','boxes.f32']:assert (out/f'{first}_0_1'/n).read_bytes()==(out/f'{first}_1_1'/n).read_bytes(),n
  video(out/f'{first}_{cpu}_0');video(p)
 data=(out/'trace_first/trace.f32').read_bytes();old_trace=(CURRENT/'physical_r1/trace_first/all86.f32').read_bytes();assert data==old_trace;off=0
 for t in read(BASE/'road_arm_prototype_20261026/graph.json')['tensors']:
  n=t['elements']*4;floats(np.frombuffer(data[off:off+n],'<f4'),np.fromfile(REF/'native_detector_full/cases'/first/'host/trace'/f"{t['id']:03d}.f32",'<f4'));off+=n
 assert off==len(data)==19844800
 timing={};live=[]
 for cpu in [0,1]:
  for detail in [0,1]:
   ts=[]
   for i in range(4):m=words(out/f'time{cpu}_{detail}_{i}.bin');mail(m,cpu,detail);ts.append((m[19]+(m[20]<<32))/m[18])
   timing[f'{cpu}_{detail}']=dict(warmup=ts[0],runs=ts[1:],median=statistics.median(ts[1:]))
  p=out/f'live{cpu}';mail(words(p/'mail.bin'),cpu,0,True);video(p);s,e,a,b,va,vb=map(int,(p/'cadence.txt').read_text().split());live.append(dict(cpu_pack=cpu,seconds=(e-s)/1000,completed=b-a,detection_hz=1000*(b-a)/(e-s),preview_hz=1000*(vb-va)/(e-s)))
 profiles={str(cpu):np.fromfile(out/f'profile{cpu}.u64','<u8').tolist() for cpu in [0,1]}
 return dict(status='CPU_PACK_PHYSICAL_EXACT_CAMERA_AND_TIMING_COMPLETE',fixed=records,trace86_byte_exact=True,roi_outputs_byte_exact=True,timing=timing,speedup_single=timing['0_0']['median']/timing['1_0']['median'],speedup_detail=timing['0_1']['median']/timing['1_1']['median'],live=live,profiles=profiles,sd_written=False)
if __name__=='__main__':
 if '--validate' in sys.argv:write(ROOT/'validated.json',validate(read(APP/'arm_complete.json')['cases']))
 else:main()
