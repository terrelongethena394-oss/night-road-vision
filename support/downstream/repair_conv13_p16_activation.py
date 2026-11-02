"""Correct a verified extracted-bit checksum mirror, then confirm actual speed.
No algorithm, FPGA bitstream, weights, tolerance or performance gate changes.
"""
import subprocess,sys,zipfile,hashlib,shutil
from conv13_p16_config import RUNTIME as ROOT,BOARD
from prepare_fp32_cpu_pack import CURRENT,read,write,sha

def main():
    app=ROOT/'firmware';v=read(ROOT/'validated.json');s=read(ROOT/'session.json');chosen=v['selected_pl_mode']
    assert s['status']=='NOT_PROMOTED_PREVIOUS_ABI15_RESTORED' and s['restored']
    assert v['trace86_byte_exact'] and v['roi_outputs_byte_exact'] and all(r['outputs_byte_exact'] for r in v['fixed'])
    assert v['speedup_actual15_selected']>=1.05 and v['live'][chosen-1]['detection_hz']>=.9*v['actual_abi15_baseline']['live']['detection_hz']
    checks=read(app/'runtime_checksums.json');bad=[n for n,h in checks.items() if sha(app/n)!=h];assert bad==['road_conv.bit'],bad
    assert checks['road_conv.bit']==sha(CURRENT/'display.bit')
    with zipfile.ZipFile(app/'display.xsa') as z:
        names=[n for n in z.namelist() if n.endswith('.bit')];assert names==['road_conv.bit']
        digest=hashlib.sha256(z.read(names[0])).hexdigest()
    assert digest==sha(app/'road_conv.bit')==sha(app/'display.bit')==sha(BOARD/'road_conv.bit')
    archive=ROOT/'activation_repair_20261029';archive.mkdir()
    for p in [app/'runtime_checksums.json',ROOT/'session.json',ROOT/'activate.log',ROOT/'restore0.log',ROOT/'retry_20261029_console.log']:
        if p.exists():shutil.copy2(p,archive/p.name)
    checks['road_conv.bit']=digest;write(app/'runtime_checksums.json',checks)
    assert all(sha(app/n)==h for n,h in checks.items())
    write(archive/'audit.json',dict(cause='loadhw extracted the new embedded road_conv.bit over the cloned old mirror; only that inherited checksum differed',old_mirror_sha256=sha(CURRENT/'display.bit'),new_expected_mirror_sha256=digest,all_other_files_unchanged=True,algorithm_or_weights_changed=False,checks_relaxed=False,quality_and_speed_gates_unchanged=True,sd_written=False))
    p=subprocess.run([sys.executable,str(app/'experiment.py'),'start',str(chosen)],capture_output=True,text=True,timeout=500)
    (ROOT/'repaired_activate.log').write_text(p.stdout+p.stderr,encoding='utf-8')
    assert p.returncode==0 and 'ROAD_CONV13_LIVE_READY' in p.stdout
    write(ROOT/'session.json',dict(status='CONV13_BYTE_EXACT_FASTER_VALIDATED_AND_LIVE',selected_pl_mode=chosen,activation_repaired=True,speedup_single=v['speedup_single'],speedup_actual15_selected=v['speedup_actual15_selected'],sd_written=False))
    import confirm_conv13_speed as c
    c.ROOT=ROOT;c.APP=app;c.VERSION=18;c.SELECT_BEST_POLICY=True;c.main()

if __name__=='__main__':main()
