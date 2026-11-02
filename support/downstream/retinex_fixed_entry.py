"""Local, checked entry for fixed-photo ABI21/22 experiments.

Full enhancement or raw bypass only. No blend-strength semantics are assumed.
Requires the installed local Xilinx tools and Python environment.
"""
from pathlib import Path
import datetime, hashlib, json, struct, subprocess, sys
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parent
APP=ROOT/'firmware'
XSCT='E:/Xilinx/Vitis/2020.2/bin/xsct.bat'

def read(p): return json.loads(p.read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def rgbwords(p):
    w=np.fromfile(p,'<u4')
    return np.stack([w&255,w>>8&255,w>>16&255],1).astype(np.uint8)

def main():
    args=sys.argv[1:]
    assert len(args)==3 and args[0] in ['start','show'], 'Use: start|show photo1..3 full|raw'
    photo=int(args[1]);mode=args[2]
    assert photo in [1,2,3] and mode in ['full','raw']
    arm=read(APP/'arm_complete.json');version=arm['version'];assert version in [21,22]
    proof=read(ROOT/'board_verified.json')
    assert proof['elf_sha256']==sha(APP/'road_detail.elf') and proof['bit_sha256']==sha(APP/'display.bit')
    assert all(r['decode_byte_exact'] and r['boxes_byte_exact'] and r['frame_byte_exact'] for r in proof['results'])
    assert read(ROOT/'visual_review.json')['approved_for_experimental_demo'] is True
    checks=read(APP/'runtime_checksums.json')
    assert all(sha(APP/n)==h for n,h in checks.items()), 'Runtime file checksum mismatch'
    case=read(APP/'cases.json')[photo-1];folder=APP/'runtime/cases'/case['name']
    pipe=2 if mode=='full' else 0
    out=ROOT/'user_runs'/datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f');out.mkdir(parents=True)
    def run(cmd,label,marker):
        with (out/(label+'.log')).open('w',encoding='utf-8') as log:
            p=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=300)
        text=(out/(label+'.log')).read_text(encoding='utf-8');print(text,flush=True)
        assert p.returncode==0 and marker in text, 'No completion marker; see logs. Use 00_restore_camera.cmd if needed.'
    if args[0]=='start':run([XSCT,str(APP/'start_idle.tcl'),'2'],'start','ROAD_RETINEX_IDLE_READY')
    a=APP.as_posix();d=out.as_posix()
    tcl=f'''source {a}/camera_common.tcl
connect -url tcp:127.0.0.1:3121
if {{[catch {{
 targets -set -filter {{name =~ "ARM*#0"}} -timeout 10
 rc_check
 mwr 0x1380000c 0
 set idle 0
 for {{set i 0}} {{$i<600}} {{incr i}} {{
  after 100
  rc_check
  if {{[word 0x13800008] in {{1 5}}}} {{set idle 1;break}}
 }}
 if {{!$idle}} {{error "No safe idle boundary"}}
 mwr 0x13800120 2
 mwr 0x13800140 {pipe}
 mwr 0x13800144 48
 mwr 0x13800178 0
 rc_test {case['name']} {photo} {case['input_fnv']} 0
 mrd -bin -file {d}/mail.bin 0x13800000 144
 mrd -bin -file {d}/ui.u32 0x16500000 16
 mrd -bin -file {d}/raw.u32 0x16700000 96000
 mrd -bin -file {d}/enhanced.u32 0x16100000 96000
 mrd -bin -file {d}/decoded.f32 0x16300000 56700
 set count [word 0x138000d0]
 if {{$count>300}} {{error "Invalid box count"}}
 if {{$count>0}} {{mrd -bin -file {d}/boxes.f32 0x16200000 [expr {{$count*6}}]}} else {{close [open {d}/boxes.f32 w]}}
 set frame [word 0x13800080]
 if {{$frame!=0x02000000 && $frame!=0x02119400}} {{error "Invalid frame address"}}
 mrd -bin -file {d}/frame.bgr $frame 288000
 disconnect
 puts "FIXED_RETINEX_PACKET_READY"
}} why opts]}} {{
 puts stderr "FIXED_RETINEX_FAILED $why"
 catch {{disconnect}}
 exit 1
}}
exit 0
'''
    script=out/'show.tcl';script.write_text(tcl,encoding='ascii')
    run([XSCT,str(script)],'show','FIXED_RETINEX_PACKET_READY')
    m=struct.unpack('<144I',(out/'mail.bin').read_bytes())
    assert m[0]==0x524f4144 and m[1]==version and m[2]==3 and m[56]==m[57]==1
    assert m[6]==m[35]==m[41]==m[74]==0 and m[72]==m[132]==2 and m[104]==51 and m[93]==pipe
    assert m[30]==0x7084 and m[40]==0x5640 and m[17]==1483844061
    assert sha(out/'raw.u32')==case['input_sha256']
    assert (out/'decoded.f32').read_bytes()==(folder/'abi18_decoded.f32').read_bytes()
    assert (out/'boxes.f32').read_bytes()==(folder/'abi18_boxes.f32').read_bytes()
    expected=rgbwords(folder/('enhanced400.u32' if mode=='full' else 'input400.u32'))
    actual=rgbwords(out/'enhanced.u32')
    diff=np.abs(actual.astype(np.int16)-expected.astype(np.int16))
    assert diff.max()<=1 and diff.mean()<=.01
    p=subprocess.run([str(APP/'host/render.exe'),str(out/'raw.u32'),str(out/'enhanced.u32'),str(out/'boxes.f32'),str(out/'ui.u32'),str(out/'expected.bgr')],capture_output=True,text=True,timeout=30)
    assert p.returncode==0 and 'GUARDS_PASS' in p.stdout
    assert (out/'frame.bgr').read_bytes()==(out/'expected.bgr').read_bytes()
    Image.fromarray(np.fromfile(out/'frame.bgr',np.uint8).reshape(480,800,3)[:,:,::-1]).save(out/'lcd_readback.png')
    record=dict(version=version,photo=photo,mode=mode,detector_input='raw',decode_byte_exact=True,boxes_byte_exact=True,frame_byte_exact=True,pixel_max_abs=int(diff.max()),pixel_mean_abs=float(diff.mean()),processing_seconds=(m[19]+(m[20]<<32))/m[18],sd_written=False)
    (out/'verified.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print('FIXED_PHOTO_READY',photo,mode,'ABI',version,flush=True)

if __name__=='__main__': main()
