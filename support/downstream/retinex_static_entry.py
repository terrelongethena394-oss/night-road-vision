"""Local user entry for the accepted fixed-photo ABI20 demonstration."""
from pathlib import Path
import datetime,json,hashlib,subprocess,sys,struct
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parent
APP=ROOT/'firmware'
XSCT='E:/Xilinx/Vitis/2020.2/bin/xsct.bat'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    assert read(ROOT/'manual_display_status.json')['accepted'] is True,'Awaiting physical display check'
    checks=read(APP/'runtime_checksums.json');assert all(sha(APP/n)==h for n,h in checks.items())
    args=sys.argv[1:];assert len(args)==3 and args[0] in ['start','show']
    photo=int(args[1]);strength=int(args[2]);assert photo in [1,2,3] and strength in [0,12,24,36,48]
    case=read(APP/'cases.json')[photo-1];folder=APP/'runtime/cases'/case['name']
    out=ROOT/'user_runs'/datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f');out.mkdir(parents=True)
    def run(cmd,label,marker,timeout=300):
        with (out/(label+'.log')).open('w',encoding='utf-8') as log:p=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
        text=(out/(label+'.log')).read_text(encoding='utf-8');print(text,flush=True)
        assert p.returncode==0 and marker in text,'Command failed; see log or use 00_restore_camera.cmd'
    if args[0]=='start':run([XSCT,str(APP/'start_idle.tcl'),'2'],'start','ROAD_RETINEX_IDLE_READY')
    a=APP.as_posix();d=out.as_posix();id=case['name']
    tcl=f'''source {a}/camera_common.tcl
connect -url tcp:127.0.0.1:3121
targets -set -filter {{name =~ "ARM*#0"}} -timeout 10
rc_check
mwr 0x1380000c 0
set idle 0
for {{set i 0}} {{$i<600}} {{incr i}} {{
 after 100
 rc_check
 if {{[word 0x13800008] in {{1 5}}}} {{set idle 1;break}}
}}
if {{!$idle}} {{error "Not idle"}}
mwr 0x13800120 2
mwr 0x13800140 2
mwr 0x13800144 {strength}
mwr 0x13800178 0
rc_test {id} {photo} {case['input_fnv']} 0
mrd -bin -file {d}/mail.bin 0x13800000 144
mrd -bin -file {d}/raw.u32 0x16700000 96000
mrd -bin -file {d}/enhanced.u32 0x16100000 96000
mrd -bin -file {d}/decoded.f32 0x16300000 56700
set frame [word 0x13800080]
if {{$frame!=0x02000000 && $frame!=0x02119400}} {{error "Invalid frame"}}
mrd -bin -file {d}/frame.bgr $frame 288000
disconnect
puts "RETINEX_USER_PHOTO_DISPLAYED"
exit 0
'''
    p=out/'show.tcl';p.write_text(tcl,encoding='ascii');run([XSCT,str(p)],'show','RETINEX_USER_PHOTO_DISPLAYED')
    m=struct.unpack('<144I',(out/'mail.bin').read_bytes());assert m[1]==20 and m[2]==3 and m[57]==1 and m[56]==1 and m[93]==2
    assert m[6]==m[35]==m[41]==m[74]==0 and m[104]==51
    assert sha(out/'raw.u32')==case['input_sha256'] and (out/'decoded.f32').read_bytes()==(folder/'abi18_decoded.f32').read_bytes()
    aa=np.fromfile(folder/'input400.u32','<u4');bb=np.fromfile(folder/'strong400.u32','<u4');actual=np.fromfile(out/'enhanced.u32','<u4')
    a=np.stack([aa&255,aa>>8&255,aa>>16&255],1);b=np.stack([bb&255,bb>>8&255,bb>>16&255],1);c=np.stack([actual&255,actual>>8&255,actual>>16&255],1)
    expected=(a*(48-strength)+b*strength+24)//48;diff=np.abs(c.astype(np.int16)-expected.astype(np.int16));assert diff.max()<=1 and diff.mean()<=.01
    Image.fromarray(np.fromfile(out/'frame.bgr',np.uint8).reshape(480,800,3)[:,:,::-1]).save(out/'lcd_readback.png')
    (out/'verified.json').write_text(json.dumps(dict(photo=photo,strength=strength/48,decode_unchanged=True,pixel_max_abs=int(diff.max()),sd_written=False),indent=2),encoding='utf-8')
    print('FIXED_PHOTO_READY',photo,'strength',strength/48,flush=True)
if __name__=='__main__':main()
