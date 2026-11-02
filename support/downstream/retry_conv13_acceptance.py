"""Preserve pre-reset connection failure and run authorized hardware acceptance."""
import subprocess,sys
from prepare_fp32_cpu_pack import read,write,sha
from prepare_road_conv13_runtime import ROOT

def main():
    scan=(ROOT/'scan_after_replug.log').read_text(errors='replace');assert 'APU' in scan and 'xc7z020' in scan
    assert not (ROOT/'firmware/physical_pack_r1').exists()
    s=read(ROOT/'session.json');assert s['status']=='RESTORE_NEEDS_REPAIR'
    assert 'no targets found' in (ROOT/'startup.log').read_text() and 'Camera app' not in (ROOT/'startup.log').read_text()
    archive=ROOT/'connection_attempt2_after_build';archive.mkdir()
    for name in ['session.json','startup.log','restore0.log','restore1.log','acceptance_console.log','scan_after_long_build.log']:
        p=ROOT/name
        if p.exists():
            assert p.resolve().parent==ROOT.resolve() and (archive/name).resolve().is_relative_to(ROOT.resolve())
            p.rename(archive/name)
    app=ROOT/'firmware'
    for p in app.glob('last_start_attempt*.log'):p.rename(archive/('app_'+p.name))
    write(archive/'audit.json',dict(status='NO_APU_BEFORE_RST_OR_BIT_ELF_DOWNLOAD',coarse_restore_receipt_does_not_mean_old_ram_changed=True,subsequent_scan=str(ROOT/'scan_after_replug.log'),sd_written=False))
    assert sha(ROOT/'run_acceptance.py')==read(ROOT/'protocol.json')['acceptance_script_sha256']
    with (ROOT/'acceptance_console2.log').open('w') as f:p=subprocess.run([sys.executable,str(ROOT/'run_acceptance.py')],stdout=f,stderr=subprocess.STDOUT,timeout=2600)
    state=read(ROOT/'session.json')
    if state['status']=='CONV13_BYTE_EXACT_FASTER_VALIDATED_AND_LIVE':
        import confirm_conv13_speed
        confirm_conv13_speed.main()
    else:assert state['status']=='NOT_PROMOTED_PREVIOUS_ABI15_RESTORED' and state['restored'],state

if __name__=='__main__':main()
