from pathlib import Path
import json,csv,shutil,sys
import numpy as np
ROOT=Path('E:/FPGA_Enhance_Work/multinex_camera_protected_20261026')
BASE=ROOT.parent
def fnv(data):
    h=2166136261
    for b in data:h=((h^b)*16777619)&0xffffffff
    return h
def main():
    global ROOT
    if len(sys.argv)>1:ROOT=Path(sys.argv[1])
    q=json.loads((ROOT/'quality_policy.json').read_text());assert q['accepted']
    with (BASE/'camera_quality_mean_20261026/per_image.csv').open() as f:rows=list(csv.DictReader(f))
    selected=[]
    for k in (256,0,224):
        r=next(r for r in rows if int(r['alpha'])==k)
        selected.append((f'alpha{k}_{Path(r["id"]).stem}',r))
    assert not (ROOT/'quality_cases.json').exists()
    (ROOT/'quality_inputs').mkdir(exist_ok=True)
    cases=[]
    for id,r in selected:
        folder=BASE/'camera_quality_20261026/test'/Path(r['id']).stem/r['condition']
        raw=np.frombuffer((folder/'input.rgb888').read_bytes(),np.uint8).reshape(240,400,3)
        packed=np.zeros((240,400,4),np.uint8);packed[:,:,:3]=raw
        p=ROOT/'quality_inputs'/(id+'.rgba32');p.write_bytes(packed.tobytes())
        cases.append(dict(id=id,file=p.as_posix(),alpha=int(r['alpha']),input_fnv=fnv(p.read_bytes()),
            original=r['id'],condition=r['condition']))
    (ROOT/'quality_cases.json').write_text(json.dumps(cases,indent=2),encoding='utf-8')
    lines=['set cases [list]']
    for c in cases:lines.append(f'lappend cases [dict create id {c["id"]} file {{{c["file"]}}} fnv {c["input_fnv"]} alpha {c["alpha"]}]')
    (ROOT/'quality_cases.tcl').write_text('\n'.join(lines)+'\n',encoding='ascii')
    source=Path(__file__).resolve().parent/'test_camera_quality.tcl'
    shutil.copy2(source,ROOT/source.name)
    print('THREE_PROTECTION_BRANCH_CASES_PREPARED',flush=True)
if __name__=='__main__':main()
