"""Use prior rejected confirmation as calibration, then a new frozen20/mode run.
No gates or model files change; the failed round is kept in full.
"""
import subprocess,sys,shutil
from conv13_p16_config import RUNTIME as ROOT
from prepare_fp32_cpu_pack import read,write,sha

def main():
    app=ROOT/'firmware';old=read(ROOT/'alternating_speed.json');v=read(ROOT/'validated.json')
    assert old['status']=='NOT_PROMOTED_PREVIOUS_ABI15_RESTORED' and old['restored']
    assert old['selected_pl_mode']==1 and old['speedup_samebit']>=1.05 and old['paired_mean_savings_bootstrap95'][0]>0
    assert v['trace86_byte_exact'] and v['roi_outputs_byte_exact'] and all(r['outputs_byte_exact'] for r in v['fixed'])
    assert v['actual_abi15_baseline']['median']/v['timing']['2_0']['median']>=1.05
    assert v['live'][1]['detection_hz']>=.9*v['actual_abi15_baseline']['live']['detection_hz']
    archive=ROOT/'selection_round1';archive.mkdir()
    for n in ['alternating_speed.json','alternating_protocol.json','alternating_speed.log','confirmation_restore.log','session.json','activation_repair_console.log']:
        p=ROOT/n
        if p.exists():p.rename(archive/n)
    data=app/'alternating_speed';assert data.resolve().is_relative_to(ROOT.resolve());data.rename(archive/'alternating_speed')
    p=app/'confirm_speed.tcl'
    if p.exists():p.rename(archive/'confirm_speed.tcl')
    order=[2,1,1,2]+[2,1,1,2]*10
    write(ROOT/'reselection_protocol_20261029.json',dict(status='MODE2_FIXED_BEFORE_FRESH_CONFIRMATION',selected_pl_mode=2,prior_round_role='Calibration only; selectedmode1 was rejected, not passed',prior_calibration_sha256=sha(archive/'alternating_speed.json'),physical_quality_proof_sha256=sha(ROOT/'validated.json'),calibration_median_seconds=old['median_seconds'],fresh_order=order,warmup=4,measured_per_mode=20,unchanged_gates='>=5% faster than actual15 AND mode1; paired and independent mean savings bootstrap95%lower>0; prior complete byteexact/video checks.',sd_written=False))
    p=subprocess.run([sys.executable,str(app/'experiment.py'),'start','2'],capture_output=True,text=True,timeout=500)
    (ROOT/'reselected_activate.log').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0 and 'ROAD_CONV13_LIVE_READY' in p.stdout
    write(ROOT/'session.json',dict(status='CONV13_BYTE_EXACT_FASTER_VALIDATED_AND_LIVE',selected_pl_mode=2,selection_revision=2,reason='First independent round rejected mode1 and provided calibration evidence for mode2; awaiting new heldout confirmation',sd_written=False))
    import confirm_conv13_speed as c
    c.ROOT=ROOT;c.APP=app;c.VERSION=18;c.SELECT_BEST_POLICY=True;c.SAMPLES_PER_MODE=20;c.ORDER=order;c.main()

if __name__=='__main__':main()
