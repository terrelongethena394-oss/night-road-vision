"""Preserve failed no-target attempt, restore known program after reconnection."""
import subprocess,sys,shutil
from prepare_fp32_cpu_pack import CURRENT,write
from prepare_road_conv13_runtime import ROOT
import measure_conv13_original
def main():
    assert not (ROOT/'original_baseline').exists()
    archive=ROOT/'connection_attempt1';archive.mkdir()
    for n in ['measure_original.log','original_measure_console.log','original_baseline_failed.json','original_measure_restore.log']:
        p=ROOT/n
        if p.exists():shutil.copy2(p,archive/n)
    write(archive/'audit.json',dict(status='NO_ARM_TARGET_BEFORE_ANY_BOARD_MAILBOX_WRITE',note='Subsequent readonly scan recognizes APU/xc7z020 after user reconnected; XSCT launcher returned0 despite Tclerror, fixed marker validation.',sd_written=False))
    p=subprocess.run([sys.executable,str(CURRENT/'experiment.py'),'start'],capture_output=True,text=True,timeout=500)
    (ROOT/'prebaseline_start.log').write_text(p.stdout+p.stderr,encoding='utf-8')
    assert p.returncode==0 and 'ROAD_DETAIL_EXPERIMENT_LIVE_READY' in p.stdout
    measure_conv13_original.main()
if __name__=='__main__':main()
