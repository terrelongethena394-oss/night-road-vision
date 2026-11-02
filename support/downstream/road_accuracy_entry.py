"""Checked local start/switch entry, enabled only after real ABI23 acceptance."""
from pathlib import Path
import datetime,hashlib,json,struct,subprocess,sys
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parent
APP=ROOT/'firmware'
XSCT='E:/Xilinx/Vitis/2020.2/bin/xsct.bat'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    args=sys.argv[1:];assert len(args)==2 and args[0] in ['start','show']
    proof=read(ROOT/'board_verified.json');assert proof['status']=='ABI23_FOUR_PASS_QUALITY_AND_BOARD_NUMERICS_VERIFIED'
    assert proof['elf_sha256']==sha(APP/'road_detail.elf')
    assert all(sha(APP/n)==h for n,h in read(APP/'runtime_checksums.json').items())
    cases=read(APP/'cases.json');photo=int(args[1]);assert 1<=photo<=len(cases);c=cases[photo-1]
    reference=Path(proof['evidence'])/'candidate23'/str(next(r['visit'] for r in proof['results'] if r['name']==c['name']))
    gold=Path(proof['evidence'])/'baseline22'/c['name']
    out=ROOT/'user_runs'/datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f');out.mkdir(parents=True)
    def run(script,label,marker):
        with (out/(label+'.log')).open('w',encoding='utf-8') as log:p=subprocess.run([XSCT,str(script)],stdout=log,stderr=subprocess.STDOUT,timeout=350)
        text=(out/(label+'.log')).read_text(encoding='utf-8');print(text,flush=True);assert p.returncode==0 and marker in text
    if args[0]=='start':run(APP/'start_idle.tcl','start','ROAD_RETINEX_IDLE_READY')
    a=APP.as_posix();d=out.as_posix();v=c['views'];script=out/'show.tcl'
    script.write_text(f'''source {a}/camera_common.tcl
connect -url tcp:127.0.0.1:3121
if {{[catch {{
 targets -set -filter {{name =~ "ARM*#0"}} -timeout 10
 mwr 0x1380000c 0
 after 350
 rc_check
 if {{[word 0x13800008] ni {{1 5}}}} {{error "Not injected idle"}}
 for {{set j 0}} {{$j<3}} {{incr j}} {{dow -data $root/runtime/cases/{c['name']}/tile$j/input400.u32 [expr {{0x1A000000+$j*0x60000}}]}}
 catch {{con}}
 mwr 0x13800220 {v[1]['expected_fnv']}
 mwr 0x13800224 {v[2]['expected_fnv']}
 mwr 0x13800228 {v[3]['expected_fnv']}
 mwr 0x13800140 2
 mwr 0x13800144 48
 mwr 0x13800178 2
 rc_test {c['name']} {photo} {v[0]['expected_fnv']} 0
 mrd -bin -file {d}/mail.bin 0x13800000 144
 mrd -bin -file {d}/ui.u32 0x16500000 17
 mrd -bin -file {d}/raw.u32 0x16700000 96000
 mrd -bin -file {d}/enhanced.u32 0x16100000 96000
 mrd -bin -file {d}/decoded0.f32 0x17100000 56700
 for {{set j 0}} {{$j<3}} {{incr j}} {{mrd -bin -file {d}/decoded[expr {{$j+1}}].f32 [expr {{0x1A120000+$j*0x40000}}] 56700}}
 set n [word 0x138000d0]
 set bn [word 0x13800238]
 if {{$n>300 || $bn>300}} {{error "Invalid counts"}}
 if {{$n>0}} {{mrd -bin -file {d}/boxes.f32 0x16200000 [expr {{$n*6}}]}} else {{close [open {d}/boxes.f32 w]}}
 if {{$bn>0}} {{mrd -bin -file {d}/baseline.f32 0x1A200000 [expr {{$bn*6}}]}} else {{close [open {d}/baseline.f32 w]}}
 set frame [word 0x13800080]
 if {{$frame!=0x02000000 && $frame!=0x02119400}} {{error "Invalid frame"}}
 mrd -bin -file {d}/frame.bgr $frame 288000
 disconnect
 puts "ACCURACY_USER_PACKET_READY"
}} why opts]}} {{puts stderr "ACCURACY_USER_FAILED $why";catch {{disconnect}};exit 1}}
exit 0
''',encoding='ascii')
    run(script,'show','ACCURACY_USER_PACKET_READY')
    m=struct.unpack('<144I',(out/'mail.bin').read_bytes())
    assert m[1]==23 and m[2]==3 and m[56]==m[57]==1 and m[93]==m[99]==2 and m[104]==204
    assert m[6]==m[35]==m[41]==m[74]==0
    assert sha(out/'raw.u32')==v[0]['input_sha256'] and (out/'enhanced.u32').read_bytes()==(APP/'runtime/cases'/c['name']/'enhanced400.u32').read_bytes()
    for i in range(4):assert (out/('decoded'+str(i)+'.f32')).read_bytes()==(gold/str(i)/'decoded.f32').read_bytes()
    assert (out/'boxes.f32').read_bytes()==(reference/'boxes.f32').read_bytes()
    assert (out/'baseline.f32').read_bytes()==(reference/'baseline_boxes.f32').read_bytes()
    p=subprocess.run([str(APP/'host/render.exe'),str(out/'raw.u32'),str(out/'enhanced.u32'),str(out/'boxes.f32'),str(out/'baseline.f32'),str(out/'ui.u32'),str(out/'expected.bgr')],capture_output=True,text=True,timeout=30)
    assert p.returncode==0 and 'GUARDS_PASS' in p.stdout and (out/'expected.bgr').read_bytes()==(out/'frame.bgr').read_bytes()
    Image.fromarray(np.fromfile(out/'frame.bgr',np.uint8).reshape(480,800,3)[:,:,::-1]).save(out/'lcd_readback.png')
    (out/'verified.json').write_text(json.dumps(dict(photo=photo,name=c['name'],neural_all4_byte_exact=True,fusion_boxes_byte_exact=True,display_byte_exact=True,sd_written=False),indent=2),encoding='utf-8')
    print('ACCURACY_PHOTO_READY',photo,c['name'],flush=True)
if __name__=='__main__':main()
