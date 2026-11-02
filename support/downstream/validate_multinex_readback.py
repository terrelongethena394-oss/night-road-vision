"""Validate actual board dumps; never manufacture or infer board results."""
from pathlib import Path
import json,csv,sys,hashlib
import numpy as np
def fnv(data):
    h=2166136261
    for b in data:h=((h^b)*16777619)&0xffffffff
    return h
def compare(got,want):
    if len(got)!=len(want):return dict(exact=False,reason='byte_count',actual=len(got),expected=len(want))
    a=np.frombuffer(got,dtype=np.uint8);b=np.frombuffer(want,dtype=np.uint8)
    return dict(exact=got==want,mismatching_bytes=int(np.count_nonzero(a!=b)),max_byte_error=int(np.abs(a.astype(np.int16)-b).max(initial=0)))
def main():
    root=Path(__file__).resolve().parent
    if len(sys.argv)!=2:raise SystemExit('Usage: validate_multinex_readback.py ACTUAL_BOARD_RESULTS_DIRECTORY')
    folder=Path(sys.argv[1]);manifest=json.loads((root/'case_manifest.json').read_text())
    cases={c['id']:c for c in manifest['cases']}
    with (folder/'runtime.csv').open(newline='') as f:runtime=list(csv.DictReader(f))
    assert runtime,'No actual runtime rows supplied'
    seen=set();records=[]
    for row in runtime:
        id=row['id'];assert id in cases and id not in seen;seen.add(id);c=cases[id]
        assert int(row['height'])==c['height'] and int(row['width'])==c['width']
        assert int(row['input_fnv'])==c['input_fnv'] and int(row['dma_errors'])==0
        expected=(root/'expected'/(id+'.output32')).read_bytes();got=(folder/(id+'.output32')).read_bytes()
        assert hashlib.sha256(expected).hexdigest()==c['expected_sha256']
        result=compare(got,expected);assert fnv(got)==int(row['output_fnv']),'Dump/checksum mismatch'
        diag=(folder/(id+'.diag64')).read_bytes();assert len(diag)==96
        actual_diag=np.frombuffer(diag,dtype='<i8').tolist()
        diag_ok=None if not c['diagnostics'] else actual_diag==c['diagnostics']
        scratch_ok=None
        if c['scratch_check']:
            gold=(root/'expected'/(id+'.scratch32')).read_bytes()
            assert hashlib.sha256(gold).hexdigest()==c['expected_scratch_sha256']
            scratch_ok=(folder/(id+'.scratch32')).read_bytes()==gold
        ticks,hz=int(row['ticks']),int(row['timer_hz']);assert ticks>0 and hz>0
        records.append(dict(id=id,height=c['height'],width=c['width'],output=result,diagnostics_exact=diag_ok,scratch_exact=scratch_ok,
            kernel_wall_seconds=ticks/hz,output_sha256=hashlib.sha256(got).hexdigest()))
    passed=all(r['output']['exact'] and r['diagnostics_exact'] is not False and r['scratch_exact'] is not False for r in records)
    report=dict(status='ACTUAL_BOARD_NUMERICAL_PASS' if passed else 'ACTUAL_BOARD_NUMERICAL_FAIL',cases=records,
        all_prepared_cases_covered=len(records)==len(cases),full_480x800_tested=any(r['height']==480 and r['width']==800 for r in records),
        note='Static images only. ARM wall timer covers start-to-done polling, includes AXI/DDR/display contention and poll granularity. Host transfer/render time excluded. Not camera FPS or recognition accuracy.')
    (folder/'readback_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)
    if not passed:raise SystemExit(1)
if __name__=='__main__':main()
