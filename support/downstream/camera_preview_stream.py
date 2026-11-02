"""Reuse one XSCT connection for preview; retain all packet integrity checks."""
from pathlib import Path
import os,struct,subprocess,time
from PIL import Image
from camera_snapshot_tools import fnv
from car_roi_delivery_common import write
from photo_station_core import _safe,protocol_common,STAGING
from roi_delivery_board_tools import XSCT

def validate_frame(frame,wall_seconds):
    before=(frame/'before.bin').read_bytes();assert before==(frame/'after.bin').read_bytes()
    m=struct.unpack('<9I',before);data=(frame/'preview.rgb').read_bytes()
    assert m[0]==0x43414d31 and m[1]==1 and m[3:7]==(0x1e000000,103680,240,144) and m[8] in (0,1)
    assert len(data)==103680 and fnv(data)==m[7]
    assert 'CAMERA_PREVIEW_PACKET_READY' in (frame/'preview.log').read_text(encoding='ascii')
    image=frame/'preview.png';Image.frombytes('RGB',(240,144),data).save(image)
    proof=dict(status='ACTUAL_OV5640_PREVIEW_READBACK_PASS',sequence=m[2],fnv=m[7],
        stable_payload_byte_exact=True,wall_seconds=wall_seconds,
        transport_seconds=int((frame/'ready').read_text(encoding='ascii').strip())/1000,
        connection_reused=True,path=str(image),sd_written=False)
    write(frame/'verified.json',proof);return proof

def stream(job,stop_event,on_frame,max_frames=None):
    job=Path(job);d=_safe(job);script=job/'stream.tcl';count=0;last=None;durations=[]
    script.write_text(f'''{protocol_common()}
set stream_root {d}
proc stream_wait {{command}} {{
 mwr 0x1380000c $command
 for {{set i 0}} {{$i<200}} {{incr i}} {{after 25;rc_check;if {{[word 0x1380000c]==0 && [word 0x13800434]==($command==7)}} {{return}}}}
 error "Preview control timeout"
}}
if {{[catch {{
 connect -url tcp:127.0.0.1:3121
 targets -set -filter {{name =~ "ARM*#0"}} -timeout 10
 loadhw -hw $root/display.xsa
 rc_check
 if {{[word 0x13800004] ni {{31 32}} || [word 0x13800430]!=0x43414d31}} {{error "Camera interface unavailable"}}
 if {{[word 0x13800008] ni {{1 3 5}} || ([word 0x13800008]==3 && [word 0x13800270]!=1)}} {{error "Board busy or incomplete inference"}}
 stream_wait 7
 set index 0
 while {{![file exists $stream_root/stop]}} {{
  incr index
  set frame [format "%s/frame%04d" $stream_root $index]
  file mkdir $frame
  set started [clock milliseconds]
  set wanted [expr {{[word 0x13800438]+1}}]
  mwr 0x1380000c 8
  set ready 0
  for {{set i 0}} {{$i<200}} {{incr i}} {{after 25;rc_check;if {{[word 0x13800438]==$wanted}} {{set ready 1;break}}}}
  if {{!$ready}} {{error "Preview frame timeout"}}
  mrd -bin -file $frame/before.bin 0x13800430 9
  mrd -bin -file $frame/preview.rgb 0x1E000000 25920
  mrd -bin -file $frame/after.bin 0x13800430 9
  set f [open $frame/preview.log w];puts $f "CAMERA_PREVIEW_PACKET_READY";close $f
  set f [open $frame/ready.tmp w];puts $f [expr {{[clock milliseconds]-$started}}];close $f
  file rename $frame/ready.tmp $frame/ready
  puts "STREAM_FRAME_COMPLETE $index";flush stdout
  set waited 0
  while {{![file exists $frame/ack] && ![file exists $stream_root/stop]}} {{after 25;incr waited;if {{$waited>2400}} {{error "Host preview acknowledgement timeout"}}}}
  after 100
 }}
 stream_wait 9
 disconnect
 puts "CAMERA_STREAM_STOPPED_CLEANLY";flush stdout
}} why opts]}} {{
 puts stderr "CAMERA_STREAM_FAILED $why"
 catch {{stream_wait 9}}
 catch {{disconnect}}
 exit 1
}}
exit 0
''',encoding='ascii')
    with (job/'stream.log').open('w',encoding='utf-8') as log:
        p=subprocess.Popen([XSCT,str(script)],stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,
            creationflags=0x08000000 if os.name=='nt' else 0)
        failure=None
        try:
            while not stop_event.is_set() and (max_frames is None or count<max_frames):
                frame=job/f'frame{count+1:04d}';begin=time.monotonic()
                while not (frame/'ready').exists():
                    if stop_event.is_set():break
                    if p.poll() is not None:raise RuntimeError('摄像头连接中断：'+str(job/'stream.log'))
                    if time.monotonic()-begin>70:raise TimeoutError('摄像头预览回传超时')
                    stop_event.wait(.025)
                if stop_event.is_set():break
                last=validate_frame(frame,time.monotonic()-begin);durations.append(last['wall_seconds']);count+=1;on_frame(last)
                if count>8:
                    expired=job/f'frame{count-6:04d}'
                    assert expired.resolve().parent==job.resolve() and job.resolve().is_relative_to(STAGING.resolve())
                    for name in ('before.bin','after.bin','preview.rgb','preview.png','preview.log','verified.json','ready','ack'):(expired/name).unlink(missing_ok=True)
                    expired.rmdir()
                (frame/'ack').write_text('validated',encoding='ascii')
        except BaseException as e:failure=e
        finally:
            (job/'stop').write_text('stop_after_current_packet',encoding='ascii')
            try:p.wait(timeout=45)
            except subprocess.TimeoutExpired:
                subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],stdout=log,stderr=subprocess.STDOUT)
                if failure is None:failure=RuntimeError('摄像头连接未正常结束，详情：'+str(job/'stream.log'))
        text=(job/'stream.log').read_text(encoding='utf-8',errors='replace')
        if failure is not None:raise failure
        if p.returncode!=0 or 'CAMERA_STREAM_STOPPED_CLEANLY' not in text:raise RuntimeError('取景未正常结束：'+str(job/'stream.log'))
    proof=dict(frames=count,last=last,connection_reused=True,frame_wait_seconds=durations,sd_written=False)
    write(job/'preview_complete.json',proof);return proof
