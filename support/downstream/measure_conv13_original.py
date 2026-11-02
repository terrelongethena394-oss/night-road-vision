"""Measure actual unchanged ABI15 before loading the new FPGA design, then resume."""
import subprocess,sys,struct,statistics
from prepare_fp32_cpu_pack import CURRENT,read,write
from prepare_road_conv13_runtime import ROOT
XSCT='E:/Xilinx/Vitis/2020.2/bin/xsct.bat'

def main():
    out=ROOT/'original_baseline';assert not out.exists()
    first=read(CURRENT/'arm_complete.json')['cases'][0]
    tcl=r'''source E:/FPGA_Enhance_Work/road_detail_board_20261028_r1/firmware/camera_common.tcl
set out E:/FPGA_Enhance_Work/road_conv13_runtime_20261028_r1/original_baseline
if {[file exists $out]} {error "Preserve prior baseline"}
if {[catch {
 connect -url tcp:127.0.0.1:3121
 targets -set -filter {name =~ "ARM*#0"} -timeout 10
 rc_check
 mwr 0x1380000c 0
 set ready 0
 for {set i 0} {$i<400} {incr i} {after 100;rc_check;if {[word 0x13800008] in {1 5}} {set ready 1;break}}
 if {!$ready} {error "Idle timeout"}
 mwr 0x13800178 0
 mwr 0x13800120 1
 file mkdir $out
 for {set j 0} {$j<9} {incr j} {
  rc_test FIRST 1 EXPECTED 0
  mrd -bin -file $out/time${j}.bin 0x13800000 144
  puts "ORIGINAL_ABI15_TIMING $j"
 }
 mwr 0x13800070 0
 mwr 0x1380000c 3
 set before [word 0x138000cc]
 set ready 0
 for {set i 0} {$i<400} {incr i} {after 100;rc_check;if {[word 0x138000cc]>=$before+2} {set ready 1;break}}
 if {!$ready} {error "Camera resume timeout"}
 set a [word 0x138000cc];set va [word 0x1380009c];set start [clock milliseconds]
 after 20000
 set stop [clock milliseconds];set b [word 0x138000cc];set vb [word 0x1380009c]
 set f [open $out/cadence.txt w];puts $f "$start $stop $a $b $va $vb";close $f
 mrd -bin -file $out/live_mail.bin 0x13800000 144
 close [open $out/COMPLETE w]
 disconnect
 puts "ORIGINAL_ABI15_BASELINE_AND_CAMERA_RESUMED"
} why opts]} {
 puts stderr "ORIGINAL_BASELINE_FAILED $why"
 if {[dict exists $opts -errorinfo]} {puts stderr [dict get $opts -errorinfo]}
 catch {disconnect};exit 1
}
exit 0
'''.replace('FIRST',first['name']).replace('EXPECTED',str(first['input_fnv'])).replace('E:/FPGA_Enhance_Work/road_conv13_runtime_20261028_r1',ROOT.as_posix())
    (ROOT/'measure_original.tcl').write_text(tcl,encoding='ascii')
    with (ROOT/'measure_original.log').open('w') as f:p=subprocess.run([XSCT,str(ROOT/'measure_original.tcl')],stdout=f,stderr=subprocess.STDOUT,timeout=600)
    if p.returncode!=0 or not (out/'COMPLETE').exists() or 'ORIGINAL_ABI15_BASELINE_AND_CAMERA_RESUMED' not in (ROOT/'measure_original.log').read_text():
        # This command is authorized recovery of the original program if a test was interrupted.
        p0=subprocess.run([sys.executable,str(CURRENT/'experiment.py'),'start'],capture_output=True,text=True,timeout=500)
        (ROOT/'original_measure_restore.log').write_text(p0.stdout+p0.stderr,encoding='utf-8')
        write(ROOT/'original_baseline_failed.json',dict(status='ORIGINAL_MEASURE_FAILED',restored=p0.returncode==0 and 'ROAD_DETAIL_EXPERIMENT_LIVE_READY' in p0.stdout))
        raise RuntimeError('Original measurement failed; inspect recovery receipt')
    assert (out/'COMPLETE').exists() and 'ORIGINAL_ABI15_BASELINE_AND_CAMERA_RESUMED' in (ROOT/'measure_original.log').read_text()
    runs=[]
    for j in range(9):
        m=struct.unpack('<144I',(out/f'time{j}.bin').read_bytes());assert m[:4]==(0x524f4144,15,3,1) and m[6]==m[35]==m[41]==m[74]==0 and m[99]==0 and m[104]==12
        runs.append((m[19]+(m[20]<<32))/m[18])
    a,b,c,d,e,f=map(int,(out/'cadence.txt').read_text().split())
    write(ROOT/'original_baseline.json',dict(status='ACTUAL_ABI15_MEASURED_CAMERA_RESUMED',warmup=runs[0],runs=runs[1:],median=statistics.median(runs[1:]),live=dict(seconds=(b-a)/1000,completed=d-c,detection_hz=1000*(d-c)/(b-a),preview_hz=1000*(f-e)/(b-a)),sd_written=False))
    print('ACTUAL_ABI15_MEASURED_CAMERA_RESUMED',statistics.median(runs[1:]),flush=True)

if __name__=='__main__':main()
