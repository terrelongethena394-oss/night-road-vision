"""Snapshot immutable numerical cases. No expected output is sent to the ARM."""
from pathlib import Path
import json,hashlib,shutil
import numpy as np
ROOT=Path('E:/FPGA_Enhance_Work/multinex_static_20261025')
HLS=Path('E:/FPGA_Enhance_Work/multinex_hls_r3b_20261025')
HERE=Path(__file__).resolve().parent
def sha(b):return hashlib.sha256(b).hexdigest()
def fnv(data):
    h=2166136261
    for b in data:h=((h^b)*16777619)&0xffffffff
    return h
def pack(data):
    a=np.frombuffer(data,dtype=np.uint8).reshape(-1,3).astype(np.uint32)
    return (a[:,0]|(a[:,1]<<8)|(a[:,2]<<16)).astype('<u4').tobytes()
def main():
    assert not (ROOT/'case_manifest.json').exists(),'Preserve frozen input/expected cases'
    source={c['name']:c for c in json.loads((HLS/'test_manifest.json').read_text())}
    for d in ('inputs','expected'):(ROOT/d).mkdir(exist_ok=True)
    records=[];tcl=['set test_cases [list \\']
    names=['tiny','odd','black','white','random','wide','tall','native_real','full','odd']
    for i,name in enumerate(names):
        c=source[name];id=f'{i:02d}_{name}';h,w=c['height'],c['width']
        folder=Path(c['dir']);input=pack((folder/'input.rgb888').read_bytes());expected=pack((folder/c['expected']).read_bytes())
        assert len(input)==len(expected)==h*w*4
        (ROOT/'inputs'/(id+'.rgba32')).write_bytes(input)
        (ROOT/'expected'/(id+'.output32')).write_bytes(expected)
        scratch=bool(c['diag'])
        if scratch:shutil.copy2(c['scratchfile'],ROOT/'expected'/(id+'.scratch32'))
        records.append(dict(id=id,height=h,width=w,input_sha256=sha(input),expected_sha256=sha(expected),
            input_fnv=fnv(input),output_fnv=fnv(expected),diagnostics=c['diag'],scratch_check=scratch,
            provenance=dict(reference_dir=str(folder),reference_input_sha256=sha((folder/'input.rgb888').read_bytes())),
            expected_scratch_sha256=sha((ROOT/'expected'/(id+'.scratch32')).read_bytes()) if scratch else None))
        tcl.append(f' [dict create id {id} h {h} w {w} input_fnv {fnv(input)} scratch_check {int(scratch)}] \\')
    tcl.append(']')
    (ROOT/'cases.tcl').write_text('\n'.join(tcl)+'\n',encoding='ascii')
    (ROOT/'case_manifest.json').write_text(json.dumps(dict(status='HOST_REFERENCE_CASES_ONLY_NOT_BOARD_RESULTS',cases=records,
        note='Fixed integer references only. full is resized real image. No camera, labels, recognition scores or new quality test.'),indent=2),encoding='utf-8')
    for name in ('start_multinex_static.tcl','run_multinex_static.tcl','validate_multinex_readback.py'):
        shutil.copy2(HERE/name,ROOT/name)
    print('STATIC_CASES_FROZEN',len(records),flush=True)
if __name__=='__main__':main()
