from pathlib import Path
import subprocess
from car_roi_delivery_common import ROOT,read,write
def main():
    out=ROOT/'board_candidate';assert (out/'engineering_experiment_policy.json').exists();script=out/'probe_targets.tcl';script.write_text('''if {[catch {
 if {[catch {connect -url tcp:127.0.0.1:3121} why]} {connect}
 set listing [targets]
 puts $listing
 if {![regexp {APU|ARM.*#0} $listing]} {error "No Zynq CPU target; board power or JTAG link unavailable"}
 disconnect
 puts "ROI_ZYNQ_TARGET_PROBE_OK"
} why]} {puts stderr "ROI_ZYNQ_TARGET_PROBE_FAILED $why";catch {disconnect};exit 1}
exit 0
''',encoding='ascii')
    with (out/'probe_targets.log').open('w',encoding='utf-8') as log:p=subprocess.run(['E:/Xilinx/Vitis/2020.2/bin/xsct.bat',str(script)],stdout=log,stderr=subprocess.STDOUT,timeout=70)
    s=(out/'probe_targets.log').read_text(encoding='utf-8',errors='replace');ok=p.returncode==0 and 'ROI_ZYNQ_TARGET_PROBE_OK' in s;write(out/'probe_result.json',dict(available=ok,read_only=True,board_programmed=False,sd_written=False));print(s[-4000:]);print('ROI_PROBE_AVAILABLE',ok)
if __name__=='__main__':main()
