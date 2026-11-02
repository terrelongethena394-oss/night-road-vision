"""Cover all ten distinct 3x3 layer shapes with frozen real intermediate tensors."""
from pathlib import Path
import csv,hashlib,json,shutil,subprocess
import numpy as np
ROOT=Path('E:/FPGA_Enhance_Work/road_conv_burst_hls_20261027')
NN=Path('E:/FPGA_Enhance_Work/road_arm_prototype_20261026')
OLD=Path('E:/FPGA_Enhance_Work/road_conv_hls_20261027')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def fnv(b):
    h=2166136261
    for v in b:h=((h^v)*16777619)&0xffffffff
    return h
def main():
    assert (ROOT/'checked.json').exists()
    assert not (ROOT/'expanded_complete.json').exists()
    shutil.copy2(ROOT/'fixtures.json',ROOT/'fixtures_original11.json');shutil.copy2(ROOT/'cases_all.txt',ROOT/'cases_original11.txt')
    rows=json.loads((ROOT/'fixtures.json').read_text());g=json.loads((NN/'graph.json').read_text())
    weights=np.fromfile(NN/'weights.f32','<f4');which='02e67bab-27594c1d'
    for node in [13,24,67,75]:
        t=g['tensors'][node];p=g['tensors'][t['inputs'][0]];folder=ROOT/'fixtures'/f'real_node{node:02d}';folder.mkdir()
        a=np.fromfile(NN/'host_r2'/which/'trace'/f'{p["id"]:03d}.f32','<f4');a.tofile(folder/'input.f32')
        w=weights[t['woff']:t['woff']+9*p['c4']*t['c4']].reshape(9*p['c4'],t['c4']);bias=weights[t['boff']:t['boff']+t['c4']]
        w.tofile(folder/'weights.f32');bias.tofile(folder/'bias.f32')
        packed=np.empty((t['c4']//8,9*p['c4']+1,8),'<f4')
        for b in range(t['c4']//8):packed[b,0]=bias[8*b:8*b+8];packed[b,1:]=w[:,8*b:8*b+8]
        packed.tofile(folder/'packed_p8.f32')
        shape=[p['h'],p['w'],p['c4'],t['c4'],t['s']]
        (folder/'shape.txt').write_text(' '.join(map(str,shape))+'\n',encoding='ascii')
        subprocess.run([str(OLD/'reference.exe'),*map(str,shape),str(folder/'input.f32'),str(folder/'weights.f32'),str(folder/'bias.f32'),str(folder/'expected.f32'),str(folder/'expected_silu.f32')],check=True,capture_output=True)
        assert (folder/'expected_silu.f32').read_bytes()==(NN/'host_r2'/which/'trace'/f'{node:03d}.f32').read_bytes()
        rows.append(dict(name=folder.name,h=shape[0],w=shape[1],ic4=shape[2],oc4=shape[3],stride=shape[4],rtl=False,origin=dict(model_node=node,photo=which),post_silu_original_tensor_bytes_exact=True,files={p.name:sha(p) for p in folder.iterdir()}))
    (ROOT/'fixtures.json').write_text(json.dumps(rows,indent=2),encoding='utf-8');(ROOT/'cases_all.txt').write_text('\n'.join(v['name'] for v in rows)+'\n',encoding='ascii')
    with (ROOT/'csim_expanded.log').open('w') as f:subprocess.run(['E:/Xilinx/Vitis_HLS/2020.2/bin/vitis_hls.bat','-f',str(ROOT/'csim.tcl')],stdout=f,stderr=subprocess.STDOUT)
    assert 'ROAD_CONV3_CSIM_COMPLETE_P8' in (ROOT/'csim_expanded.log').read_text(errors='replace')
    csim=list(csv.DictReader((ROOT/'tb_csim.csv').open()));assert len(csim)==15 and all(int(r['bit_differences'])==0 for r in csim)
    fixtures=[]
    for row in rows:
        folder=ROOT/'fixtures'/row['name'];r={k:row[k] for k in ['name','h','w','ic4','oc4','stride']}
        r.update(input=str(folder/'input.f32'),packed=str(folder/'packed_p8.f32'),expected=str(folder/'expected.f32'))
        r.update(input_fnv32=fnv(Path(r['input']).read_bytes()),packed_fnv32=fnv(Path(r['packed']).read_bytes()),files_sha256={k:sha(r[k]) for k in ['input','packed','expected']})
        r['output_words']=((r['h']+r['stride']-1)//r['stride'])*((r['w']+r['stride']-1)//r['stride'])*r['oc4'];fixtures.append(r)
    required={(g['tensors'][t['inputs'][0]]['h'],g['tensors'][t['inputs'][0]]['w'],g['tensors'][t['inputs'][0]]['c4'],t['c4'],t['s']) for t in g['tensors'][1:] if t['kind']==1 and t['k']==3}
    covered={tuple(r[k] for k in ['h','w','ic4','oc4','stride']) for r in fixtures if r['name'].startswith('real_')}
    assert required==covered and len(required)==10
    (ROOT/'future_fixtures.json').write_text(json.dumps(fixtures,indent=2),encoding='utf-8')
    (ROOT/'expanded_complete.json').write_text(json.dumps(dict(status='ALL10_REAL_3X3_SHAPES_INDEPENDENT_REFERENCE_AND_ALL15_CSIM_EXACT',csim=csim,hardware_access=False),indent=2),encoding='utf-8')
    print('ROAD_BURST_EXPANDED_ALL15_CSIM_PASS_ALL10_REAL_SHAPES',flush=True)
if __name__=='__main__':main()
