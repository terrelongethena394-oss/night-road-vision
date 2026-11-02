"""Exercise IPC/stop/cleanup in Tcl with hardware commands replaced by mocks.

This never connects to hardware and never produces hardware acceptance records.
"""
import struct,threading,time,uuid
from pathlib import Path
import camera_preview_stream as module
from camera_snapshot_tools import fnv
from car_roi_delivery_common import BASE,write
from photo_station_core import STAGING

def main():
    out=BASE/'workbench_optimization_20261031_r1/offline_stream_tests';out.mkdir(parents=True,exist_ok=True)
    fixture=out/'synthetic.rgb';fixture.write_bytes(bytes(range(256))*405);assert fixture.stat().st_size==103680
    h=fnv(fixture.read_bytes())
    common=f'''# OFFLINE ONLY: replace every hardware command before the driver starts.
set root {out.as_posix()}
set fixture {fixture.as_posix()}
set sequence 0
set active 0
proc connect {{args}} {{}}
proc targets {{args}} {{}}
proc loadhw {{args}} {{}}
proc disconnect {{args}} {{}}
proc rc_check {{}} {{}}
proc word {{a}} {{
 global sequence active
 switch -- [expr {{$a+0}}] {{
  327155716 {{return 31}}
  327155720 {{return 1}}
  327156784 {{return 1128353073}}
  327156788 {{return $active}}
  327156792 {{return $sequence}}
  327155724 {{return 0}}
  default {{error "Unexpected mocked register $a"}}
 }}
}}
proc mwr {{a value}} {{
 global sequence active
 if {{$a!=0x1380000c}} {{error "Unexpected mocked write"}}
 if {{$value==7}} {{set active 1}} elseif {{$value==9}} {{set active 0}} elseif {{$value==8}} {{incr sequence}} else {{error "Unexpected mock command"}}
}}
proc mrd {{args}} {{
 global sequence active fixture
 set path [lindex $args 2];set address [lindex $args 3]
 if {{$address==0x1E000000}} {{file copy $fixture $path;return}}
 if {{$address!=0x13800430}} {{error "Unexpected mock memory read"}}
 set f [open $path wb];fconfigure $f -translation binary
 puts -nonewline $f [binary format i* [list 1128353073 $active $sequence 503316480 103680 240 144 {h} 0]];close $f
}}
'''
    # Use expressions to obtain register keys, avoiding manually transcribed hex.
    replacements={327155716:0x13800004,327155720:0x13800008,327156784:0x13800430,327156788:0x13800434,327156792:0x13800438,327155724:0x1380000c}
    for old,new in replacements.items():common=common.replace(str(old),str(new))
    common=common.replace('1128353073',str(0x43414d31))
    module.protocol_common=lambda:common
    def validate(frame,wall):
        before=(frame/'before.bin').read_bytes();assert before==(frame/'after.bin').read_bytes()
        m=struct.unpack('<9I',before);assert m[7]==fnv((frame/'preview.rgb').read_bytes())==h
        result=dict(status='OFFLINE_SIMULATED_PACKET_ONLY',sequence=m[2],wall_seconds=wall,physical_readback=False)
        write(frame/'verified.json',result);return result
    module.validate_frame=validate
    cases=[]
    for kind in ('complete','user_stop','callback_failure'):
        job=STAGING/'jobs'/('mock_preview_'+kind+'_'+uuid.uuid4().hex[:8]);job.mkdir(parents=True)
        stop=threading.Event();frames=[]
        def callback(r):
            frames.append(r)
            if kind=='user_stop' and len(frames)==3:stop.set()
            if kind=='callback_failure' and len(frames)==2:raise ValueError('EXPECTED_MOCK_CALLBACK_FAILURE')
        if kind=='callback_failure':
            try:module.stream(job,stop,callback,max_frames=10)
            except ValueError as e:assert str(e)=='EXPECTED_MOCK_CALLBACK_FAILURE'
            else:raise AssertionError('Expected callback exception')
        else:module.stream(job,stop,callback,max_frames=10)
        log=(job/'stream.log').read_text(encoding='utf-8',errors='replace');assert 'CAMERA_STREAM_STOPPED_CLEANLY' in log
        if kind=='complete':assert len(frames)==10 and not (job/'frame0003').exists() and (job/'frame0001').is_dir()
        if kind=='user_stop':assert len(frames)==3
        cases.append(dict(case=kind,frames=len(frames),stopped_cleanly=True,job=str(job)))
        print('OFFLINE_STREAM_CASE_PASS',kind,len(frames),flush=True)
    write(out/'verified.json',dict(status='OFFLINE_IPC_AND_SHUTDOWN_TESTS_PASS',cases=cases,hardware_access=False,
        synthetic_pixels=True,performance_claimed=False,hardware_acceptance_claimed=False))

if __name__=='__main__':main()
