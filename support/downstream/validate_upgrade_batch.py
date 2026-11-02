"""Validate completed JTAG photo dumps while later cases are being captured."""
from pathlib import Path
import json,subprocess,sys,time
ROOT=Path('E:/FPGA_Enhance_Work/multinex_camera_digit_upgrade_20261026')
def main():
    cases=json.loads((ROOT/'digit_cases.json').read_text(encoding='utf-8'));done=set();start=time.monotonic()
    while len(done)<len(cases):
        if time.monotonic()-start>480:raise TimeoutError('Incomplete fixed-photo board captures; do not finalize')
        progressed=False
        for c in cases:
            name=c['id'];folder=ROOT/'board_digit'/name
            if name in done or not (folder/'resumed.txt').exists():continue
            r=subprocess.run([sys.executable,str(ROOT/'validate_digit_camera.py'),str(folder)],capture_output=True,text=True)
            (folder/'validator.log').write_text(r.stdout+r.stderr,encoding='utf-8')
            assert r.returncode==0,f'{name}: {r.stderr}'
            result=json.loads((folder/'digit_validation.json').read_text())
            assert result['input_contract']==2 and result['logits_exact'] and result['gray_exact'] and result['display_digits_exact']
            done.add(name);progressed=True;print('BOARD_CASE_VERIFIED',len(done),len(cases),name,result['predictions'],flush=True)
        if not progressed:time.sleep(1)
    (ROOT/'batch_validation_complete.json').write_text(json.dumps(dict(status='ALL_FIXED_PHOTO_DUMPS_VALIDATED',cases=len(done),seconds=time.monotonic()-start),indent=2),encoding='utf-8')
    print('ALL_BOARD_PHOTO_CASES_VERIFIED',len(done),flush=True)
if __name__=='__main__':main()
