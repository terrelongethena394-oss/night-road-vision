"""Activate already-speed-confirmedmode2 without redundant TCK reconfiguration."""
import subprocess,sys,shutil
from conv13_p16_config import RUNTIME as ROOT
from prepare_fp32_cpu_pack import read,write,sha

def main():
    app=ROOT/'firmware';a=read(ROOT/'alternating_speed.json');v=read(ROOT/'validated.json')
    assert a['status']=='NOT_PROMOTED_PREVIOUS_ABI15_RESTORED' and a['restored']
    assert a['selected_pl_mode']==2 and a['measured_per_mode']==20
    assert a['speedup_samebit']>=1.05 and a['speedup_actual15']>=1.05
    assert a['paired_mean_savings_bootstrap95'][0]>0 and a['actual15_independent_mean_savings_bootstrap95'][0]>0
    assert v['trace86_byte_exact'] and v['roi_outputs_byte_exact'] and v['live'][1]['detection_hz']>=.9*v['actual_abi15_baseline']['live']['detection_hz']
    failure=(ROOT/'confirmed_activate.log').read_text();assert 'port closed' in failure and 'jtag frequency 6000000' in failure
    archive=ROOT/'transport_activation_repair_20261029';archive.mkdir()
    for p in [app/'start_default.tcl',app/'runtime_checksums.json',ROOT/'alternating_speed.json',ROOT/'confirmed_activate.log',ROOT/'confirmation_restore.log']:
        shutil.copy2(p,archive/p.name)
    checks=read(app/'runtime_checksums.json');assert all(sha(app/n)==h for n,h in checks.items())
    script=app/'start_default.tcl';text=script.read_text();assert text.count(' jtag targets -set -filter {level == 0}\n puts "JTAG_CLOCK [jtag frequency 6000000]"\n')==1
    text=text.replace(' jtag targets -set -filter {level == 0}\n puts "JTAG_CLOCK [jtag frequency 6000000]"\n','',1);script.write_text(text,encoding='ascii')
    checks['start_default.tcl']=sha(script);write(app/'runtime_checksums.json',checks)
    assert all(sha(app/n)==h for n,h in checks.items())
    write(archive/'audit.json',dict(cause='TCF port closed while re-setting JTAG frequency before target reset. Removed only that redundant transport operation.',bit_elf_weights_unchanged=True,speed_measurements_and_gates_unchanged=True,sd_written=False))
    p=subprocess.run([sys.executable,str(app/'experiment.py'),'start','2'],capture_output=True,text=True,timeout=500)
    (ROOT/'transport_repaired_activate.log').write_text(p.stdout+p.stderr,encoding='utf-8')
    assert p.returncode==0 and 'ROAD_CONV13_LIVE_READY' in p.stdout
    a.update(status='CONV13_BYTE_EXACT_ALTERNATING_CONFIRMED_AND_LIVE',restored=False,activation_transport_repaired=True)
    write(ROOT/'alternating_speed.json',a)
    write(ROOT/'session.json',dict(status='CONV13_BYTE_EXACT_FASTER_VALIDATED_AND_LIVE',selected_pl_mode=2,selection_revision=2,independent_confirmation_passed=True,activation_transport_repaired=True,sd_written=False))
    import verify_conv13_final_live as verify
    verify.ROOT=ROOT;verify.VERSION=18;verify.MODE=2;verify.main()

if __name__=='__main__':main()
