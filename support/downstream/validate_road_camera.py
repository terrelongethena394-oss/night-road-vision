"""Read-only validation of camera/inference snapshot correspondence and LCD bytes."""
from pathlib import Path
import sys,subprocess
import numpy as np
from build_road_camera import ROOT,NN,read,write,sha
from build_road_arm_probe import fnv
from verify_road_arm_host import compare_boxes

def validate(out):
    out=Path(out);o=read(ROOT/'offline_complete.json');g=read(NN/'graph.json')
    ctx=dict(line.split('=',1) for line in (out/'context.txt').read_text().splitlines() if '=' in line)
    assert ctx['source']=='physical_camera_cooperative_paused_readback' and ctx['kind'] in ['fixed','live']
    assert ctx['elf_sha256']==o['elf_sha256'] and ctx['weights_sha256']==o['weights_sha256'] and ctx['bit_sha256']==o['bit_sha256']
    assert sha(ROOT/'road_camera.elf')==o['elf_sha256'] and sha(ROOT/'runtime/weights.f32')==o['weights_sha256']
    m=np.fromfile(out/'mailbox.bin','<u4');u=np.fromfile(out/'ui.u32','<u4')
    assert len(m)==72 and len(u)==11 and m[0]==0x524F4144 and m[1]==10 and m[2]==3 and m[3]==1 and m[6]==0 and m[57]==1
    assert m[30]==0x7084 and m[40]==0x5640 and m[35]==0 and m[41]==0 and m[17]==1483844061 and m[69]==0x57475453
    assert 0<m[4]==m[51] and m[31]<=1 and m[32]==0x02000000+int(m[31])*1152000 and m[38]==2
    assert m[39]==u[0] and m[45]==u[1] and m[36]==u[2] and m[52]==u[6] and u[6]<=300 and u[7]==1 and m[56]==u[8] and u[9]==1
    hz=int(m[18]);assert hz>0
    total_ticks=int(m[19])+(int(m[20])<<32);assert int(u[3])==(total_ticks*1000+hz//2)//hz
    assert u[4]>=u[3] and m[54]>0
    if ctx['kind']=='fixed':assert m[70]>0 # Injected single test has no next in-flight cycle.
    live=(out/'live400.u32').read_bytes();result=(out/'result400.u32').read_bytes();frame=(out/'frame.bgr').read_bytes()
    assert len(live)==len(result)==384000 and fnv(live)==m[65] and fnv(result)==m[64]
    assert len(frame)==1152000 and fnv(frame)==m[37]
    regs=np.fromfile(out/'vdma_regs.bin','<u4');assert len(regs)==12 and regs[0]&1 and regs[1]&0xff0==0 and not (regs[1]&1)
    assert ((int(regs[10])>>16)&31)==m[31] and ((int(regs[10])>>24)&31)==1-int(m[61])
    assert int(regs[10])&31==m[31] and (int(regs[10])>>8)&31==1-int(m[61])
    source=np.fromfile(out/'capture_source.bgr',np.uint8).reshape(480,800,3)
    avg=((source.astype(np.uint16).reshape(240,2,400,2,3).sum((1,3))+2)//4).astype(np.uint32)
    words=avg[:,:,2]|(avg[:,:,1]<<8)|(avg[:,:,0]<<16);assert words.astype('<u4').tobytes()==live
    assert bool(u[8])==(ctx['kind']=='fixed')
    if ctx['kind']=='fixed':
        fixture=ctx['fixture'];assert result==(NN/'cases'/fixture/'input400.u32').read_bytes();reference=NN/'host_r2'/fixture
    else:
        assert u[0]>u[1] and u[8]==0
        reference=out/'host_reference';reference.mkdir(exist_ok=False);trace=reference/'trace';trace.mkdir()
        p=subprocess.run([str(NN/'host_r2/road_simd.exe'),str(NN/'weights.f32'),str(out/'result400.u32'),str(reference),str(trace)],capture_output=True,text=True)
        assert p.returncode==0 and 'ROAD_FP32_HOST_DONE' in p.stdout,(p.stdout,p.stderr)
    headproof=[]
    for j,i in enumerate(g['heads']):
        a=np.fromfile(out/f'head{j}.f32','<f4');b=np.fromfile(reference/'trace'/f'{i:03d}.f32','<f4');delta=abs(a-b)
        assert a.shape==b.shape and np.isfinite(a).all() and np.all(delta<=1e-4+1e-4*abs(b)),(j,float(delta.max()))
        headproof.append(dict(id=i,max_abs=float(delta.max())))
    a=np.fromfile(out/'decoded.f32','<f4').reshape(-1,9);b=np.fromfile(reference/'decoded.f32','<f4').reshape(-1,9);delta=abs(a-b)
    assert a.shape==b.shape and np.isfinite(a).all() and delta[:,:4].max()<=.02 and delta[:,4:].max()<=2e-4
    actual=np.fromfile(out/'boxes400.f32','<f4').reshape(-1,6);gold=np.fromfile(reference/'boxes400.f32','<f4').reshape(-1,6)
    boxes=compare_boxes(actual,gold,.04);assert boxes['count']==u[6]
    layers=[]
    if (out/'all_layers.f32').exists():
        raw=(out/'all_layers.f32').read_bytes();assert len(raw)==m[14]==19844800;cursor=0
        for t in g['tensors']:
            n=t['elements']*4;a=np.frombuffer(raw[cursor:cursor+n],'<f4');b=np.fromfile(reference/'trace'/f'{t["id"]:03d}.f32','<f4');d=abs(a-b)
            assert a.shape==b.shape and np.isfinite(a).all() and np.all(d<=1e-4+1e-4*abs(b)),(t['id'],float(d.max()))
            layers.append(dict(id=t['id'],max_abs=float(d.max())));cursor+=n
        assert cursor==len(raw)
    p=subprocess.run([str(ROOT/'host/render.exe'),str(out/'live400.u32'),str(out/'result400.u32'),str(out/'boxes400.f32'),str(out/'ui.u32'),str(out/'expected_frame.bgr')],capture_output=True,text=True,check=True)
    assert 'GUARDS_PASS' in p.stdout and (out/'expected_frame.bgr').read_bytes()==frame
    from PIL import Image
    Image.fromarray(np.frombuffer(frame,np.uint8).reshape(480,800,3)[:,:,::-1]).save(out/'actual_framebuffer.png')
    verdict=dict(status='PHYSICAL_CAMERA_CAPTURE_RESULT_CORRESPONDENCE_NUMERICS_AND_FULL_LCD_FRAME_PASS',kind=ctx['kind'],fixture=ctx['fixture'],
        all_layers=layers,heads=headproof,boxes=boxes,capture_average_all384000bytes_exact=True,framebuffer_all1152000bytes_exact=True,
        live_snapshot_id=int(u[0]),result_source_id=int(u[1]),active_inference_id=int(u[2]),completed_inferences=int(m[51]),preview_updates_in_current_or_last_cycle=int(m[70]),
        display_view_hz=float(u[5])/10,active_detection_seconds=total_ticks/hz,snapshot_age_display_ms=int(u[4]),pause_flag_latest_cycle=int(m[62]),
        paused_for_readback=True,resumption_done_by_loader=True,elf_sha256=o['elf_sha256'],weights_sha256=o['weights_sha256'],camera_id=int(m[40]),lcd_id=int(m[30]),
        sd_written=False,enhancement_enabled=False,neural_compute='ARM Cortex-A9; cooperativepreview is not detection acceleration')
    write(out/'validated.json',verdict);return verdict
if __name__=='__main__':
    v=validate(Path(sys.argv[1]));print('ROAD_CAMERA_PHYSICAL_PACKET_PASS',v['kind'],v['boxes']['count'],v['active_detection_seconds'],v['preview_updates_in_current_or_last_cycle'],flush=True)
