"""Alternating same-bit mode1/2 confirmation, plus actualABI15 speed gate."""
import subprocess,sys,struct,statistics
import numpy as np
from prepare_fp32_cpu_pack import CURRENT,read,write
from prepare_road_conv13_runtime import ROOT
APP=ROOT/'firmware';XSCT='E:/Xilinx/Vitis/2020.2/bin/xsct.bat'
VERSION=17
SELECT_BEST_POLICY=False
SAMPLES_PER_MODE=10
ORDER=[1,2,2,1,1,2,2,1,2,1,1,2,1,2,2,1,1,2,2,1,2,1,1,2]

def main():
    assert read(ROOT/'session.json')['status']=='CONV13_BYTE_EXACT_FASTER_VALIDATED_AND_LIVE'
    original=read(ROOT/'original_baseline.json');first=read(APP/'arm_complete.json')['cases'][0]
    selected=read(ROOT/'session.json').get('selected_pl_mode',2)
    out=APP/'alternating_speed';assert not out.exists()
    write(ROOT/'alternating_protocol.json',dict(order=ORDER,warmup=4,measured_per_mode=SAMPLES_PER_MODE,seed=2026102839,bootstrap_replicates=10000,acceptance='median>=5% faster than samebit mode1 and actual15; paired mean savings95%lower>0; independent mean savings actual15 versus candidate95%lower>0; complete prior quality/video gates',sd_written=False))
    if SELECT_BEST_POLICY:
        policy=read(ROOT/'alternating_protocol.json');policy.update(selected_pl_mode_frozen_from_pilot=selected,acceptance=f'Selected mode fixed fromcalibration: actual15 median>=5% faster and independent mean-savings95%lower>0. Ifmode2: also samebitmode1 median>=5% and paired95%lower>0. Ifmode1: no morethan5% slower thanmode2. Both{SAMPLES_PER_MODE}samples and allpriorquality/video gates.');write(ROOT/'alternating_protocol.json',policy)
    tcl=r'''source [file join [file dirname [file normalize [info script]]] camera_common.tcl]
set out $root/alternating_speed
if {[file exists $out]} {error "Preserve confirmation"}
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
 foreach mode {ORDER} {
  if {[word 0x13800008]==3} {
   if {[word 0x138000e0]!=1} {error "Not injected idle"}
   mwr 0x1380000c 0;after 300
  }
  if {[word 0x13800008] ni {1 5}} {error "Not idle"}
  mwr 0x13800120 $mode
  set wanted [expr {[word 0x13800010]+1}]
  mwr 0x1380000c 2
  set ready 0
  for {set i 0} {$i<400} {incr i} {after 100;rc_check;if {[word 0x13800008]==5 && [word 0x13800010]==$wanted} {rc_pause;set ready 1;break}}
  if {!$ready} {error "Inference timeout"}
  mrd -bin -file $out/${j}_${mode}.bin 0x13800000 144
  puts "CONV13_ALTERNATING $j $mode"
  incr j
 }
 disconnect
 puts "CONV13_ALTERNATING_COMPLETE"
} why opts]} {
 puts stderr "CONV13_ALTERNATING_FAILED $why"
 if {[dict exists $opts -errorinfo]} {puts stderr [dict get $opts -errorinfo]}
 catch {disconnect};exit 1
}
exit 0
'''.replace('FIRST',first['name']).replace('EXPECTED',str(first['input_fnv'])).replace('ORDER',' '.join(map(str,ORDER)))
    (APP/'confirm_speed.tcl').write_text(tcl,encoding='ascii');ok=False;result=dict(status='CONV13_CONFIRMATION_PENDING',sd_written=False)
    try:
        with (ROOT/'alternating_speed.log').open('w') as f:p=subprocess.run([XSCT,str(APP/'confirm_speed.tcl')],stdout=f,stderr=subprocess.STDOUT,timeout=600)
        assert p.returncode==0 and 'CONV13_ALTERNATING_COMPLETE' in (ROOT/'alternating_speed.log').read_text()
        runs={1:[],2:[]}
        for f in sorted(out.glob('*.bin'),key=lambda p:int(p.stem.split('_')[0])):
            j,mode=map(int,f.stem.split('_'));m=struct.unpack('<144I',f.read_bytes());calls=12 if mode==1 else 51
            assert m[:4]==(0x524f4144,VERSION,3,1) and m[6]==m[35]==m[41]==m[74]==0 and m[57]==1 and m[132]==m[72]==mode and m[99]==0 and m[104]==m[73]==calls and m[17]==1483844061
            if j>=4:runs[mode].append((m[19]+(m[20]<<32))/m[18])
        assert len(runs[1])==len(runs[2])==SAMPLES_PER_MODE
        med={mode:statistics.median(a) for mode,a in runs.items()};delta=np.array(runs[1])-np.array(runs[2]);rng=np.random.default_rng(2026102839)
        ci=np.quantile(rng.choice(delta,(10000,SAMPLES_PER_MODE),replace=True).mean(1),[.025,.975]).tolist()
        actual=np.array(original['runs']);candidate=np.array(runs[selected]);aci=np.quantile(rng.choice(actual,(10000,len(actual)),replace=True).mean(1)-rng.choice(candidate,(10000,SAMPLES_PER_MODE),replace=True).mean(1),[.025,.975]).tolist()
        result.update(status='CONV13_CONFIRMATION_MEASURED',runs=runs,median_seconds=med,speedup_samebit=med[1]/med[2],speedup_actual15=original['median']/med[2],paired_mean_savings_bootstrap95=ci,actual15_independent_mean_savings_bootstrap95=aci,original_baseline=original)
        result.update(selected_pl_mode=selected,speedup_actual15=original['median']/med[selected],measured_per_mode=SAMPLES_PER_MODE)
        write(ROOT/'alternating_speed.json',result)
        if SELECT_BEST_POLICY:
            result.update(selected_pl_mode=selected,speedup_actual15=original['median']/med[selected])
            assert original['median']/med[selected]>=1.05 and aci[0]>0,'Actual15 speed improvement not confirmed'
            if selected==2:assert med[1]/med[2]>=1.05 and ci[0]>0,'51layer advantage not confirmed'
            else:assert med[1]<=1.05*med[2],'Selected12layer mode was more than5% slower'
        else:assert med[1]/med[2]>=1.05 and original['median']/med[2]>=1.05 and ci[0]>0 and aci[0]>0,'Stable speed improvement not confirmed'
        command=[sys.executable,str(APP/'experiment.py'),'start']+([str(selected)] if SELECT_BEST_POLICY else [])
        p=subprocess.run(command,capture_output=True,text=True,timeout=500);(ROOT/'confirmed_activate.log').write_text(p.stdout+p.stderr,encoding='utf-8')
        assert p.returncode==0 and 'ROAD_CONV13_LIVE_READY' in p.stdout
        ok=True;result['status']='CONV13_BYTE_EXACT_ALTERNATING_CONFIRMED_AND_LIVE'
    finally:
        if not ok:
            p=subprocess.run([sys.executable,str(CURRENT/'experiment.py'),'start'],capture_output=True,text=True,timeout=500);(ROOT/'confirmation_restore.log').write_text(p.stdout+p.stderr,encoding='utf-8')
            restored=p.returncode==0 and 'ROAD_DETAIL_EXPERIMENT_LIVE_READY' in p.stdout
            result.update(status='NOT_PROMOTED_PREVIOUS_ABI15_RESTORED' if restored else 'RESTORE_NEEDS_REPAIR',restored=restored)
        write(ROOT/'alternating_speed.json',result);print(result,flush=True)
    if ok:
        import verify_conv13_final_live
        verify_conv13_final_live.ROOT=ROOT;verify_conv13_final_live.VERSION=VERSION;verify_conv13_final_live.MODE=selected
        verify_conv13_final_live.main()

if __name__=='__main__':main()
