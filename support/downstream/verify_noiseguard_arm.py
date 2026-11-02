"""Reuse authenticated same-input ABI18 baseline, then verify ABI22 in RAM."""
from pathlib import Path
import json, hashlib, subprocess
import verify_retinex_arm_board as v

ROOT=Path('E:/FPGA_Enhance_Work/road_retinex_noiseguard_arm_20261029_r1')
PREVIOUS=Path('E:/FPGA_Enhance_Work/road_retinex_detail_arm_20261029_r1')
APP=ROOT/'firmware'

def read(p): return json.loads(p.read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    arm=read(APP/'arm_complete.json'); source=PREVIOUS/'actual_abi18_baseline.json'; old=read(source)
    oldarm=read(PREVIOUS/'firmware/arm_complete.json')
    assert arm['bit_sha256']==oldarm['bit_sha256'] and arm['weights_sha256']==oldarm['weights_sha256']
    assert old['protocol']['baseline_elf_sha256']==sha(v.STABLE/'road_detail.elf')
    for case in read(APP/'cases.json'):
        f=Path(old['evidence'])/case['name']
        identity=next(r for r in old['results'] if r['name']==case['name'])
        assert sha(f/'raw.u32')==case['input_sha256']
        assert sha(f/'decoded.f32')==identity['decode_sha256'] and sha(f/'boxes.f32')==identity['boxes_sha256']
    baseline=dict(old)
    baseline['reused_from']=dict(path=str(source),sha256=sha(source),reason='Identical input bytes, bitstream, weights and detector code. These are actual previous ABI18 outputs, not a fresh measurement or native-x86 reference.')
    baseline['original_protocol']=old['protocol']
    baseline['protocol']=dict(old['protocol'],candidate_elf_sha256=sha(APP/'road_detail.elf'),reason='Reuse authenticated same-input actual ABI18 baseline for enhancement-only ABI22 revision.')
    (ROOT/'actual_abi18_baseline.json').write_text(json.dumps(baseline,indent=2),encoding='utf-8')
    scan=ROOT/'preflight.tcl'
    scan.write_text('connect -url tcp:127.0.0.1:3121\nputs [targets]\nif {[catch {targets -set -filter {name =~ "ARM*#0"} -timeout 10} why]} {puts stderr "PREFLIGHT_NO_ARM $why";catch {disconnect};exit 1}\nputs "NOISEGUARD_PREFLIGHT_ARM_FOUND"\ndisconnect\nexit 0\n',encoding='ascii')
    with (ROOT/'preflight.log').open('w',encoding='utf-8') as log:
        p=subprocess.run([v.XSCT,str(scan)],stdout=log,stderr=subprocess.STDOUT,timeout=45)
    text=(ROOT/'preflight.log').read_text(encoding='utf-8');print(text,flush=True)
    if p.returncode!=0 or 'NOISEGUARD_PREFLIGHT_ARM_FOUND' not in text:
        (ROOT/'board_session.json').write_text(json.dumps(dict(status='ABI22_COMPILED_NOT_DOWNLOADED_NO_ARM_TARGET',sd_written=False,hardware_mutation=False),indent=2),encoding='utf-8')
        print('NOISEGUARD_BOARD_NEEDS_CONNECTION',flush=True);return
    v.ROOT=ROOT;v.APP=APP;v.VERSION=22;v.DEFAULT_CAP=48
    v.ENHANCEMENT_LABEL='guard_light: rational dark protection; max gain4.5; chroma .6 and luminance <=.3 patch filtering'
    v.main()

if __name__=='__main__':main()
