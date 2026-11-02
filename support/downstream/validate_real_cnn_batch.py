"""Audit recorded hardware results without replacing them by PC expectations."""
from pathlib import Path
import csv,hashlib,json,sys

def validate(root,batch):
    root=Path(root);manifest=json.loads((root/'case_manifest.json').read_text(encoding='utf-8'))
    cases=manifest['cases'];expected={r['id']:r for r in cases}
    records=list(csv.DictReader((root/batch/'board_results.csv').open(encoding='utf-8')))
    assert len(records)==len(cases)==66
    assert [r['id'] for r in records]==[r['id'] for r in cases]
    previous=-1
    for r in records:
        c=expected[r['id']]
        for k,v in [('raw_board',c['raw_expected']),('enh_board',c['enh_expected']),('raw_margin',c['raw_margin']),('enh_margin',c['enh_margin']),('fnv_board',c['fnv']),('fnv_expected',c['fnv']),('dma_errors',0)]:
            assert int(r[k])==v,(r['id'],k,int(r[k]),v)
        assert int(r['frame'])>previous;previous=int(r['frame'])
        payload=(root/'inputs'/(c['id']+'.bgr888')).read_bytes()
        assert hashlib.sha256(payload).hexdigest()==c['sha256']
        if 'roi_mean' in r:
            assert int(r['roi_mean'])==c['roi_mean'] and int(r['enhance_mode'])==c['expected_mode']
            if int(r['enhance_mode'])==0:assert r['raw_board']==r['enh_board'] and r['raw_margin']==r['enh_margin']
    first=(root/'inputs'/(cases[0]['id']+'.bgr888')).read_bytes()
    readback=(root/batch/'first_input_readback.bin').read_bytes();assert readback==first
    groups=[]
    for name in sorted({c['group'] for c in cases}):
        group=[r for r in records if expected[r['id']]['group']==name]
        groups.append(dict(group=name,n=len(group),raw_correct=sum(r['raw_board']==r['truth'] for r in group),
            enh_correct=sum(r['enh_board']==r['truth'] for r in group)))
    status=dict(status='NUMERIC_PASS_ALL_66',cases=66,route_comparisons=132,class_or_margin_mismatches=0,
        all_input_fnv_verified=True,all_input_file_sha256_verified=True,vdma_errors=0,
        first_input_readback_bytes=len(readback),first_input_readback_sha256=hashlib.sha256(readback).hexdigest(),
        first_input_readback_byte_identical=True,groups=groups,
        caveat='Numeric equivalence is not 100% recognition accuracy. Given digit ROIs, synthetic dim is not real night/lux. PC previews are not FPGA output readback.',sd_written=False)
    (root/batch/'validated_results.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
    return status

if __name__=='__main__':print(json.dumps(validate(sys.argv[1],sys.argv[2]),indent=2),flush=True)
