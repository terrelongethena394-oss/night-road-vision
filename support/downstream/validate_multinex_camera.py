"""Independently evaluate a genuine paused live frame; no expected image sent to board."""
from pathlib import Path
import json,sys,subprocess,hashlib
import numpy as np
from PIL import Image
REF=Path('E:/FPGA_Enhance_Work/multinex_fixed_w18_20261025/cpp_reference/multinex_reference.exe')
def fnv(b):
    v=2166136261
    for c in b:v=((v^c)*16777619)&0xffffffff
    return v
def main():
    ref_hash=hashlib.sha256(REF.read_bytes()).hexdigest()
    assert ref_hash=='2eb7289db70c9f5f305cc2b0c84187653b312c03409247db82ecc005aded622d'
    folder=Path(sys.argv[1]);words=[int(v,0) for v in (folder/'mailbox.txt').read_text().split()]
    resumed=[int(v,0) for v in (folder/'resumed.txt').read_text().split()]
    assert len(words)==29 and words[0]==0x4d584334 and words[2]==3 and words[4]==1
    assert words[6:8]==[240,400] and words[25]==0x5640
    assert words[13]==words[14]==words[15]==0
    assert resumed[5]>words[5] and resumed[15]==0
    raw=(folder/'input32.bin').read_bytes();got=(folder/'output32.bin').read_bytes()
    assert len(raw)==len(got)==240*400*4
    assert fnv(raw)==words[27] and fnv(got)==words[28]
    a=np.frombuffer(raw,dtype=np.uint8).reshape(240,400,4);b=np.frombuffer(got,dtype=np.uint8).reshape(240,400,4)
    assert np.all(a[:,:,3]==0) and np.all(b[:,:,3]==0)
    protection=None;displayed=b[:,:,:3];source_kind='live_camera'
    if (folder/'quality.txt').exists():
        q=[int(v,0) for v in (folder/'quality.txt').read_text().split()]
        policy=json.loads((Path(__file__).resolve().parent/'quality_policy.json').read_text())
        assert policy['accepted'] and policy['selected']['dark']==32 and policy['selected']['normal']==48
        u=a[:,:,:3].astype(np.uint32);y=(54*u[:,:,0]+183*u[:,:,1]+19*u[:,:,2]+128)>>8
        mean=(int(y.sum())+y.size//2)//y.size
        k=256 if mean<=32 else 0 if mean>=48 else ((48-mean)*256+8)//16
        base_alpha=k;plate_fallback=None
        if (folder/'plate_telemetry.txt').exists():
            telemetry=[int(v,0) for v in (folder/'plate_telemetry.txt').read_text().split()]
            if len(telemetry)==22:
                assert words[1]==8 and telemetry[13]==4 and telemetry[21]==base_alpha and telemetry[20] in (0,1)
                plate_fallback=bool(telemetry[20]);k=0 if plate_fallback else base_alpha
        assert q[:3]==[mean,k,0x04c00000]
        want=((u*(256-k)+b[:,:,:3].astype(np.uint32)*k+128)>>8).astype(np.uint8)
        final=np.fromfile(folder/'protected32.bin',np.uint8).reshape(240,400,4)
        assert np.array_equal(want,final[:,:,:3]) and np.all(final[:,:,3]==0)
        displayed=final[:,:,:3];source_kind='host_photo' if q[3] else 'live_camera'
        protection=dict(mean_luma=mean,alpha=k,base_alpha=base_alpha,plate_consistency_fallback=plate_fallback,protected_pixels_exact=True,policy_sha256=hashlib.sha256((Path(__file__).resolve().parent/'quality_policy.json').read_bytes()).hexdigest())
    capture_ok=None
    if (folder/'capture.bgr24').exists() and source_kind=='live_camera':
        sensor=np.fromfile(folder/'capture.bgr24',dtype=np.uint8).reshape(480,800,3)[:,:,::-1].astype(np.uint16)
        reduced=((sensor[0::2,0::2]+sensor[1::2,0::2]+sensor[0::2,1::2]+sensor[1::2,1::2]+2)//4).astype(np.uint8)
        assert np.array_equal(reduced,a[:,:,:3]),'CPU input differs from actual completed capture buffer'
        capture_ok=True
    (folder/'input.rgb888').write_bytes(a[:,:,:3].tobytes())
    cmd=[str(REF),str(folder/'input.rgb888'),'240','400',str(folder/'reference.rgb888')]
    r=subprocess.run(cmd,capture_output=True,text=True);assert r.returncode==0,r.stderr
    expected=(folder/'reference.rgb888').read_bytes();assert expected==b[:,:,:3].tobytes(),'Live enhancement differs from frozen reference'
    # Verify actual displayed image geometry/color against the same input and output.
    lcd=np.fromfile(folder/'display.bgr24',dtype=np.uint8).reshape(480,800,3)[:,:,::-1]
    raw_display=a[:,:,:3].copy();enh_display=displayed.copy()
    if (folder/'digit_telemetry.txt').exists():
        dt=[int(v,0) for v in (folder/'digit_telemetry.txt').read_text().split()]
        assert len(dt)==15 and dt[13] in (1,2) and dt[14]==words[5]
        x,y,size=dt[8:11]
        assert size>=28 and size<=224 and size%28==0 and 1<=x<400-size and 1<=y<240-size
        for target in (raw_display,enh_display):
            target[y-1:y+size+1,x-1]=[0,255,0];target[y-1:y+size+1,x+size]=[0,255,0]
            target[y-1,x-1:x+size+1]=[0,255,0];target[y+size,x-1:x+size+1]=[0,255,0]
    elif (folder/'plate_telemetry.txt').exists():
        pt=[int(v,0) for v in (folder/'plate_telemetry.txt').read_text().split()]
        assert (len(pt)==20 and pt[13]==3 and words[1]==7) or (len(pt)==22 and pt[13]==4 and words[1]==8)
        assert pt[14]==words[5]
        x,y,width=pt[8:11];height=pt[16]
        assert 1<=x<400-width and 1<=y<240-height and width%96==0 and height%32==0
        for target in (raw_display,enh_display):
            target[y-1:y+height+1,x-1]=[0,255,0];target[y-1:y+height+1,x+width]=[0,255,0]
            target[y-1,x-1:x+width+1]=[0,255,0];target[y+height,x-1:x+width+1]=[0,255,0]
    assert np.array_equal(lcd[120:360,:400,:],raw_display)
    assert np.array_equal(lcd[120:360,400:800,:],enh_display)
    Image.fromarray(lcd).save(folder/'actual_lcd_ddr.png')
    Image.fromarray(a[:,:,:3]).save(folder/('actual_host_input.png' if source_kind=='host_photo' else 'actual_camera_raw.png'))
    Image.fromarray(b[:,:,:3]).save(folder/('actual_model_output.png' if source_kind=='host_photo' else 'actual_camera_enh.png'))
    if protection is not None:Image.fromarray(displayed).save(folder/'actual_protected.png')
    kernel=(words[9]+(words[10]<<32))/words[8]
    loop=(words[11]+(words[12]<<32))/words[8]
    profile=None
    if (folder/'profile.txt').exists():
        p=[int(v,0) for v in (folder/'profile.txt').read_text().split()]
        profile=dict(snapshot_seconds=(p[0]+(p[1]<<32))/words[8],render_seconds=(p[2]+(p[3]<<32))/words[8],cache_enabled=bool(p[4]))
    result=dict(status='ACTUAL_HOST_PHOTO_ENHANCEMENT_EXACT' if source_kind=='host_photo' else 'ACTUAL_LIVE_CAMERA_ENHANCEMENT_EXACT',pixels=240*400,
        camera_id=words[25],lcd_id=words[26],kernel_seconds=kernel,completed_loop_seconds=loop,
        displayed_update_rate_hz=None if source_kind=='host_photo' else 1/loop,profile=profile,sequence=words[5],resumed_sequence=resumed[5],
        source_kind=source_kind,protection=protection,
        rgb_output_exact=True,capture_reduction_exact=capture_ok,lcd_pixels_exact=True,read_dma_error=words[13],write_dma_error=words[14],
        input_sha256=hashlib.sha256(raw).hexdigest(),output_sha256=hashlib.sha256(got).hexdigest(),reference_exe_sha256=ref_hash,
        note=('An existing host photo loaded into DDR, processed by the physical PL kernel and checked against frozen independent CPU reference; actual LCD DDR checked. Not a camera capture or camera FPS.' if source_kind=='host_photo' else 'One actual paused camera frame, frozen independent CPU reference, actual LCD DDR. Loop includes capture wait, 2x2 reduction, PL enhancement, composition and display parking; not sensor FPS or direct panel photograph. Auto exposure remains default.'))
    (folder/'validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()
