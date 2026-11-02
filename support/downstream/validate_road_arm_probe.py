"""Numerically validate physical readback; a completion string alone is insufficient."""
from pathlib import Path
import sys,numpy as np
from road_arm_common import ROOT,read,write,sha
from verify_road_arm_host import compare_boxes
def validate(folder,fixture):
    context=dict(x.split('=',1) for x in (folder/'context.txt').read_text().splitlines() if '=' in x)
    revision=context.get('revision','r1');assert revision in ['r1','r2']
    arm=read(ROOT/('arm_compile_complete_'+revision+'.json'));tools=read(ROOT/('probe_tools_r2.json' if revision=='r2' else 'probe_tools.json'));case=ROOT/'cases'/fixture
    assert context['fixture']==fixture and context['elf_sha256']==arm['elf_sha256'] and context['weights_sha256']==sha(ROOT/'weights.f32')
    assert context['source']=='physical_jtag_readback'
    def mailbox(path):
        m=np.fromfile(path,'<u4');assert len(m)==30 and m[0]==0x524F4144 and m[1]==1 and m[2]==3 and m[6]==0
        assert m[16]==tools['fixture_input_fnv'][fixture] and m[17]==arm['weight_fnv32']
        assert m[18]>0 and m[15]<=300;return m
    m=mailbox(folder/'mailbox.bin');assert m[28]==1 and m[14]==arm['trace_bytes']
    assert (folder/'input320.rgb').read_bytes()==(case/'input320.rgb').read_bytes()
    graph=read(ROOT/'graph.json');all_layers=np.fromfile(folder/'all_layers.f32','<f4');assert all_layers.nbytes==arm['trace_bytes']
    offset=0;errors=[]
    for t in graph['tensors']:
        got=all_layers[offset:offset+t['elements']];gold=np.fromfile(case/'golden'/f'{t["id"]:03d}.f32','<f4');offset+=t['elements']
        assert np.isfinite(got).all() and got.size==gold.size
        diff=np.abs(got-gold);assert np.all(diff<=1e-4+1e-4*np.abs(gold)),(t['id'],t['name'],float(diff.max()))
        errors.append(dict(id=t['id'],name=t['name'],max_abs=float(diff.max()),mae=float(diff.mean())))
    decoded=np.fromfile(folder/'decoded.f32','<f4').reshape(-1,9);gold=np.fromfile(case/'decoded.f32','<f4').reshape(-1,9)
    diff=abs(decoded-gold);assert np.isfinite(decoded).all() and diff[:,:4].max()<=.02 and diff[:,4:].max()<=2e-4
    boxes={}
    for name in ['boxes320','boxes400']:
        a=np.fromfile(folder/(name+'.f32'),'<f4').reshape(-1,6);b=np.fromfile(case/(name+'.f32'),'<f4').reshape(-1,6)
        assert len(a)==m[15];boxes[name]=compare_boxes(a,b,.04 if name=='boxes400' else .03)
    times=[];last=int(m[4])
    for j in range(1,4):
        v=mailbox(folder/f'timing{j}.bin');assert v[28]==0 and v[14]==0 and int(v[4])==last+1 and v[15]==m[15];last=int(v[4])
        def elapsed(lo):return (int(v[lo])+int(v[lo+1])*2**32)/int(v[18])
        times.append(dict(sequence=int(v[4]),total_seconds=elapsed(19),network_seconds=elapsed(21),prepare_seconds=elapsed(23),post_seconds=elapsed(25)))
    proof=dict(status='PHYSICAL_ARM_NEON_ALL_LAYERS_DECODE_NMS_AND_COORDINATES_VERIFIED',fixture=fixture,elf_sha256=arm['elf_sha256'],
       weights_sha256=sha(ROOT/'weights.f32'),layers=errors,preprocessing_bytes_exact=True,decoded_box_max_abs=float(diff[:,:4].max()),
       decoded_score_max_abs=float(diff[:,4:].max()),boxes=boxes,trace_disabled_timing=times,
       timing_scope='Fixed image, includes input/weight hash and output cache flush; excludes JTAG transfers, camera acquisition and display. Not live-camera FPS.',
       sd_written=False)
    return proof
def main():
    fixture=sys.argv[1];folder=Path(sys.argv[2]) if len(sys.argv)>2 else ROOT/('board_readback_'+fixture)
    assert not (folder/'validated.json').exists()
    proof=validate(folder,fixture);write(folder/'validated.json',proof)
    print('PHYSICAL_ROAD_ARM_PROBE_NUMERIC_PASS',fixture,'boxes',proof['boxes']['boxes400']['count'],'seconds',[x['total_seconds'] for x in proof['trace_disabled_timing']],flush=True)
if __name__=='__main__':main()
