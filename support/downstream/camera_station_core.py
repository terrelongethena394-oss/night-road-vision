"""OV5640 preview and frozen capture through actual board RAM. No SD writes."""
from pathlib import Path
from datetime import datetime
import argparse,shutil,struct,threading,time,uuid
import numpy as np
from PIL import Image
from photo_station_core import (STAGING,RESULT_ROOT,APP,_safe,protocol_common,device_lock,
    capture_return,verify_return,export_results)
from roi_delivery_board_tools import run
from car_roi_delivery_common import read,write,sha
from camera_snapshot_tools import fnv

CAMERA=Path('E:/FPGA_Enhance_Work/camera_station_abi31_20261031')

def new_job(prefix):
    job=STAGING/'jobs'/(prefix+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
    job.mkdir(parents=True);return job

def ensure_camera(job,notify=print,force=False):
    preference=STAGING/'preferred_runtime.json';camera_root=Path(read(preference)['root']) if preference.exists() else CAMERA
    proof=read(camera_root/'build_verified.json');version=proof['version'];assert version in (31,32)
    assert proof['models_unchanged']
    if version==31:assert proof['only_main_interface_modified']
    else:assert proof['detector_unchanged'] and proof['integer_reference_byte_exact']
    assert sha(camera_root/'firmware/road_detail.elf')==proof['elf_sha256']
    assert sha(camera_root/'firmware/display.bit')==proof['bit_sha256']
    script=job/'camera_status.tcl'
    script.write_text(f'''{protocol_common()}
if {{[catch {{
 connect -url tcp:127.0.0.1:3121
 targets -set -filter {{name =~ "ARM*#0"}} -timeout 10
 loadhw -hw $root/display.xsa
 if {{[word 0x13800000]==0x524f4144 && [word 0x13800004]=={version} && [word 0x13800430]==0x43414d31 && [word 0x13800018]==0 && [word 0x13800008]!=4}} {{puts "CAMERA_REUSE_ABI{version}"}}
 disconnect
 puts "CAMERA_STATUS_DONE"
}} why]}} {{puts stderr "CAMERA_STATUS_FAILED $why";catch {{disconnect}};exit 1}}
exit 0
''',encoding='ascii')
    run(script,job/'camera_status.log','CAMERA_STATUS_DONE',timeout=70)
    if not force and f'CAMERA_REUSE_ABI{version}' in (job/'camera_status.log').read_text(encoding='utf-8',errors='replace'):
        return f'reused_ABI{version}'
    notify('正在加载摄像头程序到运行内存…')
    (job/'ram_load_started.txt').write_text('RAM only; SD and Flash untouched',encoding='ascii')
    run(camera_root/'start_camera.tcl',job/'camera_start.log',f'CAMERA_STATION_ABI{version}_PREVIEW_READY',timeout=240)
    return f'loaded_ABI{version}_to_RAM'

def command(job,number):
    assert number in (7,9)
    script=job/f'command{number}.tcl'
    script.write_text(f'''{protocol_common()}
if {{[catch {{
 connect -url tcp:127.0.0.1:3121
 targets -set -filter {{name =~ "ARM*#0"}} -timeout 10
 loadhw -hw $root/display.xsa
 rc_check
 if {{[word 0x13800004] ni {{31 32}} || [word 0x13800430]!=0x43414d31}} {{error "Camera interface unavailable"}}
 if {{[word 0x13800008] ni {{1 3 5}}}} {{error "Board busy"}}
 mwr 0x1380000c {number}
 set ready 0
 for {{set i 0}} {{$i<100}} {{incr i}} {{after 50;rc_check;if {{[word 0x1380000c]==0 && [word 0x13800434]=={1 if number==7 else 0}}} {{set ready 1;break}}}}
 if {{!$ready}} {{error "Camera command timeout"}}
 disconnect
 puts "CAMERA_COMMAND_DONE"
}} why]}} {{puts stderr "CAMERA_COMMAND_FAILED $why";catch {{disconnect}};exit 1}}
exit 0
''',encoding='ascii')
    run(script,job/f'command{number}.log','CAMERA_COMMAND_DONE',timeout=45)

def preview_frame(job,index):
    frame=job/f'frame{index:04d}';frame.mkdir();d=_safe(frame)
    script=frame/'preview.tcl'
    script.write_text(f'''{protocol_common()}
if {{[catch {{
 connect -url tcp:127.0.0.1:3121
 targets -set -filter {{name =~ "ARM*#0"}} -timeout 10
 loadhw -hw $root/display.xsa
 rc_check
 if {{[word 0x13800004] ni {{31 32}} || [word 0x13800430]!=0x43414d31 || [word 0x13800434]!=1 || [word 0x13800008]!=1}} {{error "Preview not active"}}
 set wanted [expr {{[word 0x13800438]+1}}]
 mwr 0x1380000c 8
 set ready 0
 for {{set i 0}} {{$i<100}} {{incr i}} {{after 50;rc_check;if {{[word 0x13800438]==$wanted}} {{set ready 1;break}}}}
 if {{!$ready}} {{error "Preview timeout"}}
 mrd -bin -file {d}/before.bin 0x13800430 9
 mrd -bin -file {d}/preview.rgb 0x1E000000 25920
 mrd -bin -file {d}/after.bin 0x13800430 9
 disconnect
 puts "CAMERA_PREVIEW_PACKET_READY"
}} why]}} {{puts stderr "CAMERA_PREVIEW_FAILED $why";catch {{disconnect}};exit 1}}
exit 0
''',encoding='ascii')
    begin=time.monotonic();run(script,frame/'preview.log','CAMERA_PREVIEW_PACKET_READY',timeout=60)
    before=(frame/'before.bin').read_bytes();assert before==(frame/'after.bin').read_bytes()
    m=struct.unpack('<9I',before);data=(frame/'preview.rgb').read_bytes()
    assert m[0]==0x43414d31 and m[1]==1 and m[3:7]==(0x1e000000,103680,240,144) and m[8] in (0,1)
    assert len(data)==103680 and fnv(data)==m[7]
    image=frame/'preview.png';Image.frombytes('RGB',(240,144),data).save(image)
    proof=dict(status='ACTUAL_OV5640_PREVIEW_READBACK_PASS',sequence=m[2],fnv=m[7],
        stable_payload_byte_exact=True,wall_seconds=time.monotonic()-begin,path=str(image),sd_written=False)
    write(frame/'verified.json',proof);return proof

def preview(stop_event,on_frame,notify=print,max_frames=None):
    from camera_preview_stream import stream
    job=new_job('preview_')
    with device_lock(job):
        ensure_camera(job,notify)
        notify('摄像头取景中 · 电脑定时更新')
        stream(job,stop_event,on_frame,max_frames)
    return job

def process_camera(output_root=None,notify=print):
    begin=time.monotonic();job=new_job('camera_');output=(Path(output_root) if output_root else RESULT_ROOT)/job.name
    with device_lock(job):
        try:
            mode=ensure_camera(job,notify)
            packet=capture_return(job,notify=notify,kind=4)
            notify('结果已回传，正在核对摄像头源帧、模型指纹和LCD…')
            receipt=verify_return(packet,kind=4)
            prepared=job/'prepared';prepared.mkdir();shutil.copyfile(packet/'source800.bgr',prepared/'source800.bgr')
            bgr=np.fromfile(packet/'source800.bgr',np.uint8).reshape(480,800,3)
            Image.fromarray(bgr[:,:,::-1]).save(prepared/'input800.png')
            meta=dict(source_kind='camera',original_path=str(prepared/'input800.png'),original_sha256=sha(prepared/'input800.png'),
                oriented_original_size=[800,480],board_size=[800,480],resized_size=[800,480],padding_xy=[0,0],scale_xy=[1,1],
                fit='native_OV5640_frozen_frame',input_bgr_sha256=sha(packet/'source800.bgr'),input_bgr_fnv=fnv((packet/'source800.bgr').read_bytes()),enhancement_output_size=[400,240])
            write(prepared/'input.json',meta);receipt.update(firmware_load_mode=mode,wall_seconds=time.monotonic()-begin)
            result=export_results(job,packet,meta,receipt,output)
            notify(f"抓拍完成：检出{result['car_count']}辆汽车，板上处理{result['board_processing_seconds']:.1f}秒")
            return result
        except Exception as e:
            write(job/'failed.json',dict(status='CAMERA_TASK_FAILED_NO_RESULT_CLAIM',error=str(e),sd_written=False))
            raise RuntimeError(f'摄像头任务未完成：{e}\n日志目录：{job}') from e

def main():
    p=argparse.ArgumentParser();p.add_argument('--preview-frames',type=int,default=0);p.add_argument('--capture',action='store_true');a=p.parse_args()
    if a.preview_frames:
        preview(threading.Event(),lambda f:print('PREVIEW',f['sequence'],f['fnv'],round(f['wall_seconds'],2),f['path'],flush=True),max_frames=a.preview_frames)
    if a.capture:
        result=process_camera();write(CAMERA/'actual_camera_roundtrip_verified.json',result)
        print('CAMERA_ACTUAL_ROUNDTRIP_PASS',result['output'],flush=True)

if __name__=='__main__':main()
