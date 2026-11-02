"""Photo upload -> actual ABI30 ARM/PL processing -> LCD and PC readback.

The PC resizes, transfers, verifies bytes and draws returned boxes only.
Enhancement pixels and detections exported here always come from board RAM.
"""
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager
import argparse,ctypes,json,os,re,struct,subprocess,time,uuid
import numpy as np
from PIL import Image,ImageOps,ImageDraw,ImageFont
from car_roi_delivery_common import read,write,sha
from camera_snapshot_tools import fnv,rgb,words
from roi_delivery_board_tools import BOARD,APP,run,start,restore

STAGING=Path('E:/FPGA_Enhance_Work/photo_station_20261031')
DELIVERY=Path('E:/FPGA图像处理')
RESULT_ROOT=DELIVERY/'结果'

def prepare_photo(path,out):
    path=Path(path).resolve();out=Path(out);out.mkdir(parents=True,exist_ok=True)
    if not path.is_file():raise ValueError('找不到照片文件')
    with Image.open(path) as source:
        source.seek(0);im=ImageOps.exif_transpose(source)
        if im.width*im.height>80_000_000:raise ValueError('照片过大，请先缩小至8000万像素以内')
        if im.mode in ['RGBA','LA'] or 'transparency' in im.info:
            rgba=im.convert('RGBA');bg=Image.new('RGBA',rgba.size,(0,0,0,255));im=Image.alpha_composite(bg,rgba).convert('RGB')
        else:im=im.convert('RGB')
        w,h=im.size;scale=min(800/w,480/h);nw=max(1,min(800,int(w*scale+.5)));nh=max(1,min(480,int(h*scale+.5)))
        x=(800-nw)//2;y=(480-nh)//2
        canvas=Image.new('RGB',(800,480),(0,0,0));canvas.paste(im.resize((nw,nh),Image.Resampling.BILINEAR),(x,y))
        data=np.asarray(canvas,np.uint8)[:,:,::-1].copy().tobytes();(out/'source800.bgr').write_bytes(data)
        canvas.save(out/'input800.png')
    record=dict(original_path=str(path),original_sha256=sha(path),oriented_original_size=[w,h],board_size=[800,480],
                resized_size=[nw,nh],padding_xy=[x,y],scale_xy=[nw/w,nh/h],fit='aspect_preserving_letterbox_black',
                input_bgr_sha256=sha(out/'source800.bgr'),input_bgr_fnv=fnv(data),enhancement_output_size=[400,240])
    write(out/'input.json',record);return record

def _safe(path):
    p=Path(path).resolve().as_posix()
    if not re.fullmatch(r'[A-Za-z0-9_:/.-]+',p):raise ValueError('内部传输路径必须为无空格英文路径')
    return p

def protocol_common():
    # Keep the signed ABI30 release untouched. ABI31 only adds camera commands.
    return f'''source {_safe(APP)}/camera_common.tcl
proc rc_check {{}} {{
 if {{[word 0x13800000]!=0x524f4144 || [word 0x13800004] ni {{30 31 32}}}} {{error "Wrong workbench ABI"}}
 if {{[word 0x13800008]==4 || [word 0x13800018]!=0}} {{error "Board app error [word 0x13800018]"}}
}}
'''

@contextmanager
def device_lock(job):
    STAGING.mkdir(parents=True,exist_ok=True);p=STAGING/'jtag.lock';owner=dict(pid=os.getpid(),job=str(job),token=uuid.uuid4().hex)
    for _ in range(2):
        try:
            fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY);break
        except FileExistsError:
            previous=read(p);pid=int(previous['pid']);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            kernel.OpenProcess.argtypes=[ctypes.c_uint32,ctypes.c_int,ctypes.c_uint32];kernel.OpenProcess.restype=ctypes.c_void_p
            handle=kernel.OpenProcess(0x1000,0,pid)
            if handle:
                kernel.CloseHandle.argtypes=[ctypes.c_void_p];kernel.CloseHandle(handle)
                raise RuntimeError('已有图片任务正在使用下载器，请等它完成后再开始')
            if ctypes.get_last_error()!=87:raise RuntimeError('下载器任务锁无法确认，请检查是否还有处理任务')
            if p.resolve().parent!=STAGING.resolve():raise RuntimeError('锁文件路径异常')
            p.unlink()
    else:raise RuntimeError('无法取得下载器任务锁')
    with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(owner,f)
    try:yield
    finally:
        if p.exists() and read(p).get('token')==owner['token']:p.unlink()

def ensure_firmware(job,force=False,notify=print):
    if (STAGING/'preferred_runtime.json').exists():
        from camera_station_core import ensure_camera
        return ensure_camera(job,notify,force=force)
    assert read(BOARD/'board_verified.json')['physical_readback']
    proof=read(APP/'arm_complete.json');assert sha(APP/'road_detail.elf')==proof['elf_sha256']
    if not force:
        script=job/'status.tcl';a=_safe(APP)
        script.write_text(f'''source {a}/camera_common.tcl
if {{[catch {{
 connect -url tcp:127.0.0.1:3121
 targets -set -filter {{name =~ "ARM*#0"}} -timeout 10
 loadhw -hw $root/display.xsa
 if {{[word 0x13800000]==0x524f4144 && [word 0x13800004] in {{30 31 32}} && [word 0x13800018]==0 && [word 0x13800008]!=4}} {{puts "PHOTO_REUSE_COMPATIBLE"}} else {{puts "PHOTO_LOAD_REQUIRED"}}
 disconnect
 puts "PHOTO_STATUS_DONE"
}} why]}} {{puts stderr "PHOTO_STATUS_FAILED $why";catch {{disconnect}};exit 1}}
exit 0
''',encoding='ascii')
        try:run(script,job/'status.log','PHOTO_STATUS_DONE',timeout=70)
        except Exception as e:raise RuntimeError('没有连到开发板，请检查独立电源和JTAG两端连接。详细日志：'+str(job/'status.log')) from e
        if 'PHOTO_REUSE_COMPATIBLE' in (job/'status.log').read_text(encoding='utf-8',errors='replace'):
            notify('已连接现有处理程序');return 'reused_compatible_ABI_then_output_fingerprints_checked'
    notify('正在加载已验收程序到运行内存，首次加载较慢……')
    (job/'ram_load_started.txt').write_text('JTAG RAM load attempted; no SD/Flash write',encoding='ascii')
    start(job);return 'verified_disk_ELF_loaded_to_RAM'

def capture_return(job,source=None,notify=print,kind=5):
    assert kind in (4,5)
    out=job/'packet';out.mkdir();d=_safe(out)
    upload=''
    if kind==5:
        source=Path(source);assert source.stat().st_size==1152000
        source_hash=fnv(source.read_bytes())
        upload=f'''if {{[word 0x13800270]==1 && [word 0x13800244]=={source_hash} && [word 0x13800250]=={source_hash}}} {{
  set upload_reused 1
 }} else {{
  dow -data {_safe(source)} 0x1A300000
  catch {{con}}
 }}
 mwr 0x13800274 {source_hash}'''
    camera_read=f'''set bank [word 0x13800248]
 if {{$bank ni {{0 1}}}} {{error "Invalid camera bank"}}
 mrd -bin -file {d}/camera_bank.bgr [expr {{0x06000000+$bank*1152000}}] 288000''' if kind==4 else ''
    script=out/'request.tcl';script.write_text(f'''{protocol_common()}
set timing_start [clock milliseconds]
connect -url tcp:127.0.0.1:3121
if {{[catch {{
 targets -set -filter {{name =~ "ARM*#0"}} -timeout 10
 loadhw -hw $root/display.xsa
 rc_check
 set timing_connected [clock milliseconds]
 if {{[word 0x13800008]==3 && [word 0x13800270]!=1}} {{error "Incomplete prior inference"}}
 mwr 0x1380000c 0
 set idle 0
 for {{set i 0}} {{$i<3000}} {{incr i}} {{after 100;rc_check;if {{[word 0x13800008] in {{1 5}}}} {{set idle 1;break}}}}
 if {{!$idle}} {{error "No safe idle boundary"}}
 set upload_reused 0
 set timing_idle [clock milliseconds]
 {upload}
 set timing_uploaded [clock milliseconds]
 mwr 0x1380006c 0
 mwr 0x13800220 0
 mwr 0x13800224 0
 mwr 0x13800228 0
 mwr 0x138000b8 1
 mwr 0x13800070 0
 mwr 0x13800120 2
 mwr 0x13800140 2
 mwr 0x13800144 48
 mwr 0x13800178 2
 mwr 0x138002bc 0
 set wanted [expr {{[word 0x13800010]+1}}]
 mwr 0x1380000c {kind}
 set ready 0
 for {{set i 0}} {{$i<3000}} {{incr i}} {{after 100;rc_check;if {{[word 0x13800008]==5 && [word 0x13800010]==$wanted && [word 0x13800270]==1}} {{set ready 1;break}}}}
 if {{!$ready}} {{error "Photo processing timeout"}}
 rc_pause
 set timing_processed [clock milliseconds]
 mrd -bin -file {d}/mail.bin 0x13800000 320
 mrd -bin -file {d}/ui.u32 0x16500000 17
 mrd -bin -file {d}/source800.bgr 0x1A300000 288000
 {camera_read}
 mrd -bin -file {d}/raw.u32 0x16700000 96000
 mrd -bin -file {d}/enhanced.u32 0x16100000 96000
 set n [word 0x138000d0]
 set b [word 0x13800238]
 if {{$n>300 || $b>300}} {{error "Invalid detection count"}}
 if {{$n>0}} {{mrd -bin -file {d}/boxes.f32 0x16200000 [expr {{$n*6}}]}} else {{close [open {d}/boxes.f32 w]}}
 if {{$b>0}} {{mrd -bin -file {d}/baseline.f32 0x1A200000 [expr {{$b*6}}]}} else {{close [open {d}/baseline.f32 w]}}
 set frame [word 0x13800080]
 if {{$frame!=0x02000000 && $frame!=0x02119400}} {{error "Invalid LCD frame address"}}
 mrd -bin -file {d}/frame.bgr $frame 288000
 mrd -bin -file {d}/vdma.bin 0x43000000 16
 set timing_readback [clock milliseconds]
 set f [open {d}/timings.tsv w]
 puts $f "connect_ms [expr {{$timing_connected-$timing_start}}]"
 puts $f "idle_ms [expr {{$timing_idle-$timing_connected}}]"
 puts $f "upload_ms [expr {{$timing_uploaded-$timing_idle}}]"
 puts $f "processing_wait_and_pause_ms [expr {{$timing_processed-$timing_uploaded}}]"
 puts $f "readback_ms [expr {{$timing_readback-$timing_processed}}]"
 puts $f "upload_reused $upload_reused"
 close $f
 set f [open {d}/packet_origin.txt w];puts $f "actual_hardware_jtag_readback";close $f
 disconnect
 puts "PHOTO_RETURN_PACKET_READY"
}} why opts]}} {{puts stderr "PHOTO_RETURN_FAILED $why";catch {{disconnect}};exit 1}}
exit 0
''',encoding='ascii')
    notify('正在上传照片、板上增强与汽车检测、回传结果；请保持供电……' if kind==5 else '正在抓拍、板上增强与汽车检测、回传结果；请保持供电……')
    transfer_begin=time.monotonic();run(script,out/'request.log','PHOTO_RETURN_PACKET_READY',timeout=480)
    timings={key:int(value) for key,value in (line.split() for line in (out/'timings.tsv').read_text(encoding='ascii').splitlines())}
    timings['request_wall_seconds']=time.monotonic()-transfer_begin;write(out/'timings.json',timings)
    return out

def verify_return(packet,prepared=None,kind=5):
    packet=Path(packet);m=struct.unpack('<320I',(packet/'mail.bin').read_bytes());proof=read(APP/'arm_complete.json')
    assert (packet/'packet_origin.txt').read_text().strip()=='actual_hardware_jtag_readback'
    assert 'PHOTO_RETURN_PACKET_READY' in (packet/'request.log').read_text(encoding='utf-8',errors='replace')
    assert m[0]==0x524f4144 and m[1] in (30,31,32) and m[2]==3 and m[57]==1 and m[155]==kind and m[156]==m[158]==1 and m[56]==(kind==5)
    assert m[6]==m[35]==m[41]==m[74]==0 and m[30]==0x7084 and m[40]==0x5640
    assert m[17]==m[161]==proof['weight_fnv']['detector'] and m[162]==m[192]==m[193]==proof['weight_fnv']['refiner'] and m[210]==proof['roi_weight_fnv']
    assert m[200:208]==(0x53544631,411,1005712079,3137536,0x19000000,0x3f000000,9,1)
    src=(packet/'source800.bgr').read_bytes();assert fnv(src)==m[145]==m[148]
    if kind==5:assert src==(Path(prepared)/'source800.bgr').read_bytes()
    else:assert m[146] in (0,1) and m[147]>0 and src==(packet/'camera_bank.bgr').read_bytes()
    sensor=np.frombuffer(src,np.uint8).reshape(480,800,3)[:,:,::-1]
    raw=((sensor.astype(np.uint16).reshape(240,2,400,2,3).sum(axis=(1,3))+2)//4).astype(np.uint8)
    assert words(raw).tobytes()==(packet/'raw.u32').read_bytes() and fnv((packet/'raw.u32').read_bytes())==m[16]
    boxes=np.fromfile(packet/'boxes.f32','<f4').reshape(-1,6)
    assert len(boxes)==m[52]==m[172] and np.isfinite(boxes).all()
    if len(boxes):
        assert np.all(boxes[:,5]==1) and np.all((boxes[:,4]>=.25)&(boxes[:,4]<=1))
        assert np.all(boxes[:,[0,2]]>=0) and np.all(boxes[:,[0,2]]<=400) and np.all(boxes[:,[1,3]]>=0) and np.all(boxes[:,[1,3]]<=240)
        assert np.all(boxes[:,2]>=boxes[:,0]) and np.all(boxes[:,3]>=boxes[:,1])
    assert 0<=m[209]<=8 and m[169]==204 and m[170]==(153 if m[189] else 0) and m[215]==51*m[209]
    assert m[104]==m[169]+m[170]+m[215] and m[175]==0
    assert (packet/'enhanced.u32').stat().st_size==384000 and (packet/'frame.bgr').stat().st_size==1152000
    if m[1]==32:
        from natural_guard_lab import ROOT as natural_root,PROFILES,table
        proof32=read(natural_root/'build_verified.json');lut=table(PROFILES['natural55'])
        assert m[280:288]==(0x4e475231,proof32['lut_fnv'],1,55,550,12,130,245) and fnv(lut.tobytes())==m[281]
        out=rgb(packet/'enhanced.u32').astype(np.uint32);source=raw.astype(np.uint32);weights=np.array([54,183,19],np.uint32)
        yr=(source*weights).sum(2);ye=(out*weights).sum(2);target=np.maximum(yr,lut[((yr+128)>>8).astype(np.int32)])
        assert np.all(ye<=target+128) and not out[yr==0].any()
    env=dict(os.environ);env['PATH']='E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin;'+env['PATH']
    p=subprocess.run([str(APP/'host/render.exe'),str(packet/'raw.u32'),str(packet/'enhanced.u32'),str(packet/'boxes.f32'),str(packet/'baseline.f32'),str(packet/'ui.u32'),str(packet/'expected_frame.bgr')],capture_output=True,text=True,timeout=30,env=env)
    assert p.returncode==0 and 'GUARDS_PASS' in p.stdout and (packet/'expected_frame.bgr').read_bytes()==(packet/'frame.bgr').read_bytes()
    timings=read(packet/'timings.json') if (packet/'timings.json').exists() else None
    return dict(status='ACTUAL_PHOTO_UPLOAD_PROCESS_RETURN_PASS' if kind==5 else 'ACTUAL_CAMERA_CAPTURE_PROCESS_RETURN_PASS',source_kind='photo' if kind==5 else 'camera',firmware_abi=m[1],enhancement_profile='natural_exposure_guard55' if m[1]==32 else 'legacy_learned_exposure_fusion',natural_exposure_bounds_checked=(m[1]==32),camera_bank_byte_exact=(kind==4),physical_readback=True,input_byte_exact=True,raw_average_byte_exact=True,transport_timings=timings,
                frame_byte_exact=True,board_processing_seconds=(m[19]+(m[20]<<32))/m[18],car_count=len(boxes),roi_count=m[209],pl_conv_calls=m[104],
                source_sha256=sha(packet/'source800.bgr'),enhanced_payload_sha256=sha(packet/'enhanced.u32'),boxes_payload_sha256=sha(packet/'boxes.f32'),
                model_fingerprints_checked=True,neural_outputs_replayed_on_PC=False,enhancement_executed_on_PC=False,sd_written=False)

def _overlay(a,boxes):
    im=Image.fromarray(a);d=ImageDraw.Draw(im);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',12)
    for x1,y1,x2,y2,conf,cls in boxes:
        d.rectangle((float(x1),float(y1),float(x2),float(y2)),outline=(0,255,220),width=1)
        # Keep small distant cars visible without covering them in overlapping text.
        if x2-x1<40 and y2-y1<30:continue
        label=f'CAR {conf:.0%}';tx=float(x1);ty=max(0,float(y1)-14)
        d.rectangle((tx,ty,min(399,tx+64),ty+14),fill=(0,0,0));d.text((tx+1,ty),label,font=font,fill=(0,255,220))
    return im

def write_previews(raw,enh,boxes,output):
    output=Path(output)
    _overlay(raw,boxes).save(output/'04_原图汽车检测.png');_overlay(enh,boxes).save(output/'05_增强显示与汽车框.png')
    canvas=Image.new('RGB',(800,270),(18,18,18));canvas.paste(Image.fromarray(raw),(0,30));canvas.paste(_overlay(enh,boxes),(400,30));d=ImageDraw.Draw(canvas);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',15)
    d.text((8,6),'ORIGINAL IMAGE',fill='white',font=font);d.text((408,6),'BOARD ENHANCED / CAR DETECTION',fill='white',font=font);canvas.save(output/'07_电脑对照图.png')

def export_results(job,packet,meta,receipt,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    raw=rgb(packet/'raw.u32');enh=rgb(packet/'enhanced.u32');boxes=np.fromfile(packet/'boxes.f32','<f4').reshape(-1,6)
    Image.open(job/'prepared/input800.png').save(output/'01_板卡输入.png')
    Image.fromarray(raw).save(output/'02_板上原图400.png');Image.fromarray(enh).save(output/'03_板上增强400.png')
    write_previews(raw,enh,boxes,output)
    frame=np.fromfile(packet/'frame.bgr',np.uint8).reshape(480,800,3)[:,:,::-1];Image.fromarray(frame).save(output/'06_LCD实际读回.png')
    details=[];sx,sy=meta['scale_xy'];px,py=meta['padding_xy'];w,h=meta['oriented_original_size']
    for x1,y1,x2,y2,score,cls in boxes:
        original=[float(np.clip((x1*2-px)/sx,0,w)),float(np.clip((y1*2-py)/sy,0,h)),float(np.clip((x2*2-px)/sx,0,w)),float(np.clip((y2*2-py)/sy,0,h))]
        details.append(dict(class_name='car',class_id=int(cls),confidence=float(score),box_board400=[float(x1),float(y1),float(x2),float(y2)],box_oriented_original=original))
    record=dict(**receipt,input=meta,detections=details,packet_evidence=str(packet),output=str(output),
                detector_input='raw_original_pixels_with_native_ROI_verification',enhancement_role='board_ARM_display_enhancement',
                computer_role='image_decode_resize_transfer_readback_validation_and_box_drawing_only',
                enhancement_or_detection_accuracy_evaluated=False)
    write(output/'处理结果.json',record);write(job/'complete.json',record)
    return record

def process_photo(path,output_root=None,force_reload=False,notify=print):
    begin=time.monotonic();stamp=datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]
    job=STAGING/'jobs'/stamp;job.mkdir(parents=True)
    output_root=Path(output_root) if output_root else RESULT_ROOT;output=output_root/stamp
    notify('正在读取照片并等比例缩放到板卡输入尺寸……');meta=prepare_photo(path,job/'prepared')
    with device_lock(job):
        touched=False
        try:
            mode=ensure_firmware(job,force_reload,notify);touched=True
            packet=capture_return(job,job/'prepared/source800.bgr',notify)
            notify('结果已回传，正在核对源图、程序指纹和LCD帧缓冲……');receipt=verify_return(packet,job/'prepared')
            receipt['firmware_load_mode']=mode;receipt['wall_seconds']=time.monotonic()-begin
            result=export_results(job,packet,meta,receipt,output)
            notify(f"完成：检出{result['car_count']}辆汽车，板上处理{result['board_processing_seconds']:.1f}秒")
            return result
        except Exception as e:
            failure=dict(status='PHOTO_STATION_FAILED_NO_RESULT_CLAIM',error=str(e),job=str(job),sd_written=False)
            if touched or (job/'ram_load_started.txt').exists():
                try:failure['restoration']=restore(job)
                except Exception as restore_error:failure['restoration']=dict(status='FAILED',error=str(restore_error))
            write(job/'failed.json',failure)
            raise RuntimeError(f'处理未完成：{e}\n日志目录：{job}') from e

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--image',required=True);p.add_argument('--output');p.add_argument('--reload',action='store_true');a=p.parse_args()
    result=process_photo(a.image,a.output,a.reload,lambda s:print(s,flush=True))
    print('PHOTO_STATION_ACTUAL_ROUNDTRIP_PASS',result['output'],flush=True)

if __name__=='__main__':main()
