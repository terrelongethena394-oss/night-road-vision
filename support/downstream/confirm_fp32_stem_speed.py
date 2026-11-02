"""Alternating order confirmation after full R4 acceptance; never writes SD."""
import subprocess,sys,statistics,struct
import numpy as np
from prepare_fp32_stem_reuse import ROOT
if '--r5' in sys.argv:
    from prepare_fp32_stem_rgb import ROOT
from prepare_fp32_cpu_pack import CURRENT,read,write
APP=ROOT/'firmware'
XSCT='E:/Xilinx/Vitis/2020.2/bin/xsct.bat'

def main():
    assert read(ROOT/'session.json')['status']=='CPU_PACK_BYTE_EXACT_FASTER_VALIDATED_AND_LIVE'
    acceptance=read(ROOT/'validated.json')
    assert acceptance['live'][1]['completed']>=acceptance['live'][0]['completed'],'Live detection count regressed in the same20-second window'
    first=read(APP/'arm_complete.json')['cases'][0]
    out=APP/'alternating_speed'
    assert not out.exists()
    write(ROOT/'alternating_protocol.json',dict(order=[0,1,1,0,0,1,1,0,1,0,0,1,0,1,1,0,0,1,1,0,1,0,0,1],warmup=4,measured_per_mode=10,acceptance='Full accuracy/pixel acceptance AND median speedup>=1.05 AND paired mean savings bootstrap95% lower bound>0',bootstrap_seed=20261028,bootstrap_replicates=10000,sd_written=False))
    tcl=r'''source [file join [file dirname [file normalize [info script]]] camera_common.tcl]
set out $root/alternating_speed
if {[file exists $out]} {error "Preserve prior confirmation"}
if {[catch {
 connect -url tcp:127.0.0.1:3121
 targets -set -filter {name =~ "ARM*#0"} -timeout 10
 rc_check
 mwr 0x1380000c 0
 set ready 0
 for {set i 0} {$i<400} {incr i} {after 100;rc_check;if {[word 0x13800008] in {1 5}} {set ready 1;break}}
 if {!$ready} {error "Idle timeout"}
 dow -data $root/runtime/cases/FIRST/input400.u32 0x10000000
 mwr 0x1380006c EXPECTED
 mwr 0x138000b8 1
 mwr 0x13800070 0
 mwr 0x13800178 0
 file mkdir $out
 set j 0
 foreach cpu {0 1 1 0 0 1 1 0 1 0 0 1 0 1 1 0 0 1 1 0 1 0 0 1} {
  if {[word 0x13800008]==3} {
   if {[word 0x138000e0]!=1} {error "Not injected idle"}
   mwr 0x1380000c 0;after 300
  }
  if {[word 0x13800008] ni {1 5}} {error "Not idle"}
  mwr 0x13800200 $cpu
  set wanted [expr {[word 0x13800010]+1}]
  mwr 0x1380000c 2
  set ready 0
  for {set i 0} {$i<400} {incr i} {after 100;rc_check;if {[word 0x13800008]==5 && [word 0x13800010]==$wanted} {rc_pause;set ready 1;break}}
  if {!$ready} {error "Inference timeout"}
  mrd -bin -file $out/${j}_${cpu}.bin 0x13800000 144
  puts "STEM_ALTERNATING $j $cpu"
  incr j
 }
 disconnect
 puts "STEM_ALTERNATING_COMPLETE"
} why opts]} {
 puts stderr "STEM_ALTERNATING_FAILED $why"
 if {[dict exists $opts -errorinfo]} {puts stderr [dict get $opts -errorinfo]}
 catch {disconnect};exit 1
}
exit 0
'''.replace('FIRST',first['name']).replace('EXPECTED',str(first['input_fnv']))
    (APP/'confirm_speed.tcl').write_text(tcl,encoding='ascii')
    promoted=False
    result=dict(status='CONFIRMATION_INCOMPLETE',sd_written=False)
    try:
        with (ROOT/'alternating_speed.log').open('w') as f:
            p=subprocess.run([XSCT,str(APP/'confirm_speed.tcl')],stdout=f,stderr=subprocess.STDOUT,timeout=500)
        assert p.returncode==0 and 'STEM_ALTERNATING_COMPLETE' in (ROOT/'alternating_speed.log').read_text()
        runs={0:[],1:[]}
        for path in sorted(out.glob('*.bin'),key=lambda p:int(p.stem.split('_')[0])):
            j,cpu=map(int,path.stem.split('_'));m=struct.unpack('<144I',path.read_bytes())
            assert m[:4]==(0x524f4144,16,3,1) and m[6]==0 and m[57]==1 and m[132]==cpu
            assert m[99]==0 and m[104]==12 and m[17]==1483844061 and m[35]==m[41]==m[74]==0
            if j>=4:runs[cpu].append((m[19]+(m[20]<<32))/m[18])
        assert len(runs[0])==len(runs[1])==10
        med={cpu:statistics.median(a) for cpu,a in runs.items()}
        ratio=med[0]/med[1]
        delta=np.array(runs[0])-np.array(runs[1])
        ci=np.quantile(np.random.default_rng(20261028).choice(delta,size=(10000,10),replace=True).mean(1),[.025,.975]).tolist()
        result.update(status='CONFIRMATION_MEASURED',runs=runs,median_seconds=med,speedup=ratio,latency_reduction=1-med[1]/med[0],paired_mean_savings_seconds=float(delta.mean()),paired_mean_savings_bootstrap95=ci)
        write(ROOT/'alternating_speed.json',result)
        assert ratio>=1.05,'Alternating confirmation did not reproduce5% gain'
        assert ci[0]>0,'Paired interval includes no improvement'
        p=subprocess.run([sys.executable,str(APP/'experiment.py'),'start'],capture_output=True,text=True,timeout=500)
        (ROOT/'confirmed_activate.log').write_text(p.stdout+p.stderr,encoding='utf-8')
        assert p.returncode==0 and 'ROAD_CPU_PACK_LIVE_READY' in p.stdout
        promoted=True
        result.update(status='EXACT_STEM_REUSE_ALTERNATING_CONFIRMED_AND_LIVE')
    finally:
        if not promoted:
            p=subprocess.run([sys.executable,str(CURRENT/'experiment.py'),'start'],capture_output=True,text=True,timeout=500)
            (ROOT/'confirmation_restore.log').write_text(p.stdout+p.stderr,encoding='utf-8')
            restored=p.returncode==0 and 'ROAD_DETAIL_EXPERIMENT_LIVE_READY' in p.stdout
            result.update(status='NOT_PROMOTED_PREVIOUS_ABI15_RESTORED' if restored else 'RESTORE_NEEDS_REPAIR',restored=restored)
        write(ROOT/'alternating_speed.json',result)
        print(result,flush=True)

if __name__=='__main__':main()
