"""Check HLS generated ROM content against frozen independently quantized weights."""
from pathlib import Path
import hashlib,json,re
import numpy as np
from train_real_digit_cnn import OUT

def main():
    weights=np.load(OUT/'integer_weights.npz')
    root=OUT/'hls/real_cnn_project/solution_100mhz/syn/verilog'
    sim=OUT/'hls/real_cnn_project/solution_100mhz/sim/verilog'
    rows=[]
    for dat in root.glob('*CNN_*_rom.dat'):
        m=re.search(r'CNN_(CONV1|CONV2|FC1|FC2)_(WEIGHT|BIAS)(?:_(\d+)(?:_0)?)?_rom.dat$',dat.name)
        assert m,dat
        layer,kind,bank=m.groups();key=layer.lower()+'.'+kind.lower();a=weights[key]
        if bank is not None:a=a[int(bank)::4]
        vfile=dat.with_name(dat.name.replace('_rom.dat','.v'))
        bits=int(re.search(r'parameter DWIDTH = (\d+);',vfile.read_text()).group(1))
        actual=np.array([int(line.strip(),16) for line in dat.read_text().splitlines() if line.strip()],np.int64)
        expected=(a.ravel()&((1<<bits)-1))
        assert len(actual)==len(expected),(dat,len(actual),len(expected))
        bad=int((actual!=expected).sum())
        simfile=sim/dat.name
        copied_ok=simfile.exists() and hashlib.sha256(dat.read_bytes()).digest()==hashlib.sha256(simfile.read_bytes()).digest()
        rows.append(dict(file=dat.name,key=key,bank=bank,bits=bits,words=len(actual),mismatches=bad,
            value_range_fits_signed=bool(a.min()>=-(1<<(bits-1)) and a.max()<(1<<(bits-1))),simulator_rom_identical=copied_ok))
    assert len(rows)==17,len(rows)
    passed=all(r['mismatches']==0 and r['value_range_fits_signed'] and r['simulator_rom_identical'] for r in rows)
    (OUT/'rom_content_audit.json').write_text(json.dumps(dict(pass_all=passed,roms=rows,
        limitation='ROM contents and signed storage range only; address/control scheduling and arithmetic are not checked.'),indent=2),encoding='utf-8')
    print('CNN_ROM_CONTENT_AUDIT',passed,'files',len(rows),'words',sum(r['words'] for r in rows),flush=True)

if __name__=='__main__':main()
