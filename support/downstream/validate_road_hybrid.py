"""Strict frozen-photo ARM/PL numerical and timing acceptance; no hardware calls."""
from pathlib import Path
import json,statistics,struct,sys
ROOT=Path('E:/FPGA_Enhance_Work/road_hybrid_20261027_r1')
NN=Path('E:/FPGA_Enhance_Work/road_arm_prototype_20261026')
def words(p,n):
    raw=Path(p).read_bytes();assert len(raw)==n*4;return struct.unpack('<%dI'%n,raw)
def fnv(raw):
    h=2166136261
    for v in raw:h=((h^v)*16777619)&0xffffffff
    return h
def check_mail(m,mode,calls,fixture):
    assert m[0]==0x524F4144 and m[1]==11 and m[2]==3 and m[3]==1 and m[6]==0 and m[57]==1
    assert m[30]==0x7084 and m[40]==0x5640 and m[35]==m[41]==0
    assert m[72]==mode and m[73]==calls and m[74]==0 and m[77]==0x5041434B
    assert m[16]==fnv((NN/'cases'/fixture/'input400.u32').read_bytes()) and m[17]==1483844061
    assert m[18]>0 and m[62]==0
def packet(folder,fixture,mode,calls):
    m=words(folder/'mailbox80.bin',80);check_mail(m,mode,calls,fixture)
    # Same-platform invariant: original trusted ARM readbacks, not another libm.
    prior=NN/'board_batch_r2'/fixture
    for name in ['head0.f32','head1.f32','head2.f32','decoded.f32','boxes400.f32']:assert (folder/name).read_bytes()==(prior/name).read_bytes(),(fixture,name)
    return dict(fixture=fixture,heads_decode_nms_bytes_exact=True,pl_calls=m[73],preview_updates_in_network=m[70],boxes=m[52])
def validate(folder):
    proof=json.loads((ROOT/'arm_complete.json').read_text());fixtures=json.loads((NN/'export_complete.json').read_text())['fixtures'];first=fixtures[0]['name'];calls=len(proof['selected_layers'])
    assert json.loads((NN/'board_batch_r2/complete.json').read_text())['status']=='PHYSICAL_CORTEX_A9_NEON_ALL8_FIXTURES_HEADS_DECODE_NMS_COORDINATES_PASS'
    assert (folder/'COMPLETE.txt').read_text().strip()=='ROAD_HYBRID_FULL_TEST_READBACK_COMPLETE'
    expected=json.loads((folder/'context.json').read_text());assert expected['elf_sha256']==proof['elf_sha256'] and expected['bit_sha256']==proof['bit_sha256']
    packets=[packet(folder/'cpu_first',first,0,0)]
    for f in fixtures:packets.append(packet(folder/f['name'],f['name'],1,calls))
    full=folder/'first_hybrid_full';m=words(full/'mailbox80.bin',80);check_mail(m,1,calls,first)
    raw=(full/'all_layers.f32').read_bytes();g=json.loads((NN/'graph.json').read_text());offset=0
    original_arm=Path('E:/FPGA_Enhance_Work/road_camera_20261027/board_fixed_first/all_layers.f32')
    assert raw==original_arm.read_bytes(),'Full86 differs from immutable previously validated ARM trace'
    import numpy as np
    for t in g['tensors']:
        n=t['elements']*4;a=np.frombuffer(raw[offset:offset+n],'<f4');b=np.fromfile(NN/'host_r2'/first/'trace'/f'{t["id"]:03d}.f32','<f4')
        assert a.shape==b.shape and np.isfinite(a).all() and np.all(abs(a-b)<=1e-4+1e-4*abs(b)),('previous_host_tolerance',t['id']);offset+=n
    assert offset==len(raw)==19844800
    # Existing renderer/capture proof is reused as an independent output definition.
    u=words(full/'ui.u32',11);live=(full/'live400.u32').read_bytes();result=(full/'result400.u32').read_bytes();frame=(full/'frame.bgr').read_bytes()
    assert fnv(live)==m[65] and fnv(result)==m[64] and fnv(frame)==m[37]
    assert result==(NN/'cases'/first/'input400.u32').read_bytes()
    src=np.fromfile(full/'capture_source.bgr',np.uint8).reshape(480,800,3)
    avg=((src.astype(np.uint16).reshape(240,2,400,2,3).sum((1,3))+2)//4).astype(np.uint32)
    assert (avg[:,:,2]|(avg[:,:,1]<<8)|(avg[:,:,0]<<16)).astype('<u4').tobytes()==live
    import subprocess
    render='E:/FPGA_Enhance_Work/road_camera_20261027/host/render.exe'
    p=subprocess.run([render,str(full/'live400.u32'),str(full/'result400.u32'),str(full/'boxes400.f32'),str(full/'ui.u32'),str(full/'expected_frame.bgr')],capture_output=True,text=True,check=True)
    assert 'GUARDS_PASS' in p.stdout and (full/'expected_frame.bgr').read_bytes()==frame
    timing={}
    for mode,label,count in [(0,'cpu',0),(1,'hybrid',calls)]:
        entries=[]
        for j in range(4):
            tm=words(folder/(label+'_timing%d.bin'%j),80);check_mail(tm,mode,count,first)
            assert tm[70]>0
            hz=tm[18];total=(tm[19]+(tm[20]<<32))/hz;net=(tm[21]+(tm[22]<<32))/hz
            entries.append(dict(total_seconds=total,network_seconds=net,pl_calls=tm[73],preview_updates=tm[70]))
        timing[label]=dict(warmup=entries[0],runs=entries[1:],median_total_seconds=statistics.median(r['total_seconds'] for r in entries[1:]),median_network_seconds=statistics.median(r['network_seconds'] for r in entries[1:]))
    speedup=timing['cpu']['median_total_seconds']/timing['hybrid']['median_total_seconds']
    result=dict(status='FULL_NETWORK_PHYSICAL_NUMERICS_AND_CAMERA_PATH_PASS',full86_first_photo_bytes_exact_to_original_ARM=True,all8_photos_heads_decode_nms_bytes_exact_to_original_ARM=True,cross_host_layer_tolerance='Unchanged original camera contract: 1e-4+1e-4*abs(reference); ARM/SSE libm outputs are not byteidentical, including original CPU baseline',full_framebuffer_bytes_exact=True,capture_average_bytes_exact=True,selected_layers=proof['selected_layers'],timing=timing,first_photo_end_to_end_speedup=speedup,performance_gate_passed=speedup>1.03,pack_startup_excluded_from_steady_state_timing=True,accuracy_improvement_claimed=False,hardware_access=True,sd_written=False,packets=packets)
    (folder/'validated.json').write_text(json.dumps(result,indent=2),encoding='utf-8');return result
if __name__=='__main__':print(json.dumps(validate(Path(sys.argv[1])),indent=2))
