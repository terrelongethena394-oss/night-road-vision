"""Accept real readbacks only with matching buffers, sequence, hashes and outputs."""
from pathlib import Path
import argparse,hashlib,json,math,statistics,struct
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def fnv(b):
    h=2166136261
    for v in b:h=((h^v)*16777619)&0xffffffff
    return h
def compare(actual,expected):
    assert len(actual)==len(expected) and len(actual)%4==0,'output length'
    aa=struct.unpack('<%df'%(len(actual)//4),actual);bb=struct.unpack('<%df'%(len(expected)//4),expected)
    assert all(math.isfinite(a) and math.isfinite(b) and abs(a-b)<=2e-5+2e-5*abs(b) for a,b in zip(aa,bb)),'numerical mismatch'
    return max([abs(a-b) for a,b in zip(aa,bb)],default=0.0)
def validate(folder,fixtures,elf_sha):
    context=(folder/'context.txt').read_text()
    assert 'source=physical_jtag_readback' in context and ('elf_sha256='+elf_sha) in context
    results=[]
    for seq,c in enumerate(fixtures,1):
        d=folder/c['name'];raw=(d/'mailbox.bin').read_bytes();assert len(raw)==256
        m=struct.unpack('<64I',raw)
        assert m[:3]==(0x52435033,1,3) and m[4]==seq and m[5]==0
        assert tuple(m[7:12])==tuple(c[k] for k in ['h','w','ic4','oc4','stride'])
        assert m[12]==m[14]==c['input_fnv32'] and m[13]==m[15]==c['packed_fnv32']
        assert m[16]>0 and m[17]==c['output_words'] and m[19]==0 and m[22:25]==(8,1,0)
        for name,expected in [('input','input'),('packed','packed')]:
            assert sha(d/(name+'.f32'))==c['files_sha256'][expected]
        expected=Path(c['expected']).read_bytes();assert sha(c['expected'])==c['files_sha256']['expected']
        cpu=(d/'cpu.f32').read_bytes();pl=(d/'pl.f32').read_bytes()
        assert fnv(cpu)==m[20] and fnv(pl)==m[21]
        errors=[compare(cpu,expected),compare(pl,expected),compare(pl,cpu)]
        times=[]
        for j in range(4):
            values=[m[i]+(m[i+1]<<32) for i in [32+6*j,34+6*j,36+6*j]]
            assert all(v>0 for v in values) and values[1]>=values[2]
            times.append(dict(cpu_ms=values[0]*1000/m[16],pl_total_ms=values[1]*1000/m[16],pl_wait_ms=values[2]*1000/m[16]))
        measured=times[1:];cpu_ms=statistics.median(t['cpu_ms'] for t in measured);pl_ms=statistics.median(t['pl_total_ms'] for t in measured)
        results.append(dict(name=c['name'],max_abs_errors=errors,byte_exact_cpu=cpu==expected,byte_exact_pl=pl==expected,warmup=times[0],measured=measured,cpu_median_ms=cpu_ms,pl_median_ms=pl_ms,single_layer_speedup=cpu_ms/pl_ms))
    return dict(status='SINGLE_LAYER_PHYSICAL_READBACK_VALIDATED',full_detector_acceleration_proven=False,camera_fps_measured=False,sd_written=False,results=results)
def selfcheck():
    valid=struct.pack('<3f',0.0,-1.5,3.25);assert compare(valid,valid)==0
    for bad in [valid[:-4],struct.pack('<3f',0,0,3.25),struct.pack('<3f',float('nan'),-1.5,3.25)]:
        try:compare(bad,valid)
        except AssertionError:continue
        raise AssertionError('bad output accepted')
    print('VALIDATOR_NUMERICAL_CORRUPTION_SELFCHECK_PASS; NOT_BOARD_EVIDENCE')
def main():
    p=argparse.ArgumentParser();p.add_argument('readback',nargs='?');p.add_argument('--selfcheck',action='store_true');args=p.parse_args()
    if args.selfcheck:selfcheck();return
    assert args.readback,'readback directory required'
    here=Path(__file__).resolve().parent;root=here.parent
    fixtures=json.loads((here/'fixtures.json').read_text());proof=json.loads((root/'arm_probe/compile_complete.json').read_text())
    result=validate(Path(args.readback),fixtures,proof['elf_sha256']);(Path(args.readback)/'validated.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
