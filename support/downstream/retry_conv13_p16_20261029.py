"""Fresh-day baseline, preserved no-APU receipts, and complete authorized RAM test."""
import subprocess,sys,shutil
from conv13_p16_config import RUNTIME as ROOT
from prepare_fp32_cpu_pack import CURRENT,HERE,read,write,sha

def main():
    assert 'APU' in (ROOT/'scan_ready_20261029.log').read_text() and 'xc7z020' in (ROOT/'scan_ready_20261029.log').read_text()
    assert not (ROOT/'firmware/physical_pack_r1').exists()
    assert read(ROOT/'session.json')['status']=='RESTORE_NEEDS_REPAIR'
    log=(ROOT/'startup.log').read_text();assert 'no targets found' in log and 'ROAD_CAMERA_STAGE sensor_and_preview_ready' not in log
    archive=ROOT/'pretest_records_20261028';archive.mkdir()
    for name in ['session.json','startup.log','restore0.log','restore1.log','acceptance_console.log','original_baseline','original_baseline.json','measure_original.log','original_measure_console.log']:
        p=ROOT/name
        if p.exists():
            assert p.resolve().is_relative_to(ROOT.resolve()) and (archive/name).resolve().is_relative_to(ROOT.resolve())
            p.rename(archive/name)
    for p in (ROOT/'firmware').glob('last_start_attempt*.log'):p.rename(archive/('app_'+p.name))
    write(archive/'audit.json',dict(status='PREVIOUS_NO_APU_BEFORE_ANY_RST_OR_BIT_ELF_DOWNLOAD',coarse_restore_receipt_does_not_mean_ram_modified=True,old_baseline_preserved=True,sd_written=False))
    clock=subprocess.run(['E:/Xilinx/Vitis/2020.2/bin/xsct.bat','-eval','connect -url tcp:127.0.0.1:3121; jtag targets -set -filter {level == 0}; puts [jtag frequency 6000000]; puts [targets]; disconnect'],capture_output=True,text=True,timeout=60)
    (ROOT/'prebaseline_clock_20261029.log').write_text(clock.stdout+clock.stderr,encoding='utf-8');assert '6000000' in clock.stdout and 'APU' in clock.stdout
    p=subprocess.run([sys.executable,str(CURRENT/'experiment.py'),'start'],capture_output=True,text=True,timeout=500)
    (ROOT/'prebaseline_start_20261029.log').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0 and 'ROAD_DETAIL_EXPERIMENT_LIVE_READY' in p.stdout
    import measure_conv13_original as measure
    measure.ROOT=ROOT;measure.main()
    assert sha(ROOT/'run_acceptance.py')==read(ROOT/'protocol.json')['acceptance_script_sha256']
    with (ROOT/'acceptance_console_20261029.log').open('w') as f:p=subprocess.run([sys.executable,str(ROOT/'run_acceptance.py')],stdout=f,stderr=subprocess.STDOUT,timeout=2600)
    state=read(ROOT/'session.json')
    if state['status']=='CONV13_BYTE_EXACT_FASTER_VALIDATED_AND_LIVE':
        import confirm_conv13_speed as confirm
        confirm.ROOT=ROOT;confirm.APP=ROOT/'firmware';confirm.VERSION=18;confirm.SELECT_BEST_POLICY=True;confirm.main()
    else:assert state['status']=='NOT_PROMOTED_PREVIOUS_ABI15_RESTORED' and state['restored'],state

if __name__=='__main__':main()
