from pathlib import Path
import numpy as np,sys
from road_arm_common import ROOT,read,write,sha
from verify_road_arm_host import compare_boxes
def main():
    arm=read(ROOT/'arm_compile_complete_r2.json');tools=read(ROOT/'probe_tools_r2.json');g=read(ROOT/'graph.json')
    export=read(ROOT/'export_complete.json');records=[];folder=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'board_batch_r2'
    fixtures=export['fixtures']
    if len(sys.argv)>2:fixtures=[r for r in fixtures if r['name']==sys.argv[2]];assert len(fixtures)==1
    for fixture in fixtures:
        name=fixture['name'];case=ROOT/'cases'/name;out=folder/name;context=dict(x.split('=',1) for x in (out/'context.txt').read_text().splitlines() if '=' in x)
        assert context==dict(fixture=name,elf_sha256=arm['elf_sha256'],weights_sha256=sha(ROOT/'weights.f32'),source='physical_jtag_batch_readback')
        m=np.fromfile(out/'mailbox.bin','<u4');assert len(m)==30 and m[0]==0x524F4144 and m[1]==1 and m[2]==3 and m[6]==0 and m[28]==0 and m[14]==0
        assert m[16]==tools['fixture_input_fnv'][name] and m[17]==arm['weight_fnv32'] and m[18]>0 and m[15]<=300
        assert (out/'input320.rgb').read_bytes()==(case/'input320.rgb').read_bytes();heads=[]
        for j,i in enumerate(g['heads']):
            a=np.fromfile(out/f'head{j}.f32','<f4');b=np.fromfile(case/'golden'/f'{i:03d}.f32','<f4');assert a.shape==b.shape and np.isfinite(a).all()
            diff=abs(a-b);assert np.all(diff<=1e-4+1e-4*abs(b)),(name,j,float(diff.max()))
            heads.append(dict(head=j,max_abs=float(diff.max()),mae=float(diff.mean())))
        d=np.fromfile(out/'decoded.f32','<f4').reshape(-1,9);gold=np.fromfile(case/'decoded.f32','<f4').reshape(-1,9);diff=abs(d-gold)
        assert np.isfinite(d).all() and diff[:,:4].max()<=.02 and diff[:,4:].max()<=2e-4
        boxes={}
        for key in ['boxes320','boxes400']:
            a=np.fromfile(out/(key+'.f32'),'<f4').reshape(-1,6);b=np.fromfile(case/(key+'.f32'),'<f4').reshape(-1,6);assert len(a)==m[15]
            boxes[key]=compare_boxes(a,b,.04 if key=='boxes400' else .03)
        def seconds(lo):return (int(m[lo])+int(m[lo+1])*2**32)/int(m[18])
        record=dict(name=name,kind=fixture['kind'],heads=heads,boxes=boxes,preprocessing_bytes_exact=True,total_seconds=seconds(19),network_seconds=seconds(21),
                prepare_seconds=seconds(23),post_seconds=seconds(25),sequence=int(m[4]),file_sha256={p.name:sha(p) for p in out.iterdir() if p.is_file()})
        records.append(record);write(out/'validated.json',record)
        print('ROAD_PHYSICAL_BATCH_NUMERIC_PASS',name,'boxes',int(m[15]),'seconds',seconds(19),flush=True)
    write(folder/'complete.json',dict(status='PHYSICAL_CORTEX_A9_NEON_ALL8_FIXTURES_HEADS_DECODE_NMS_COORDINATES_PASS' if len(fixtures)==8 else 'PHYSICAL_CORTEX_A9_NEON_FINAL_REAL_PHOTO_RESTORED_AND_VERIFIED',fixtures=records,
          elf_sha256=arm['elf_sha256'],weights_sha256=sha(ROOT/'weights.f32'),camera_integrated=False,sd_written=False))
    print('ROAD_PHYSICAL_BATCH_ALL8_VERIFIED' if len(fixtures)==8 else 'ROAD_FINAL_REAL_PHOTO_VERIFIED',flush=True)
if __name__=='__main__':main()
