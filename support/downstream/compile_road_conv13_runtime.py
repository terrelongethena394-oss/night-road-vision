"""Compile against generated shared-core driver after routed PS/BSP checks."""
from pathlib import Path
import subprocess,struct,shutil,zipfile,hashlib
from prepare_fp32_cpu_pack import BASE,CURRENT,read,write,sha
from prepare_road_conv13_runtime import ROOT
from prepare_road_conv13 import ROOT as HLS
from build_road_conv13 import ROOT as BOARD
VERSION=17
PE=8
SELECT_BEST_POLICY=False

def main():
    assert read(BOARD/'offline_complete.json')['status']=='SHARED13_ROUTED_AND_TIMING_PASSED_NOT_BOARD_TESTED'
    assert read(ROOT/'host_complete.json')['status']=='BOTH_MODES_ALL16_ALL86_AND_PACKING_BYTE_EXACT'
    app=ROOT/'firmware';src=app/'source';old=read(CURRENT/'arm_complete.json')
    driver=Path(read(HLS/'checked.json')['driver_path']);assert sha(driver)==read(HLS/'checked.json')['driver_sha256'];shutil.copy2(driver,src/driver.name)
    for a,b in [('road_conv.bit','display.bit'),('road_conv.xsa','display.xsa'),('ps7_init.tcl','ps7_init.tcl')]:shutil.copy2(BOARD/a,app/b)
    # XSCT loadhw extracts the embedded bit beside the XSA. Keep that mirror
    # identical before freezing checksums; never inherit the old cloned bit.
    with zipfile.ZipFile(app/'display.xsa') as z:
        names=[n for n in z.namelist() if n.endswith('.bit')];assert len(names)==1
        raw_bit=z.read(names[0]);assert hashlib.sha256(raw_bit).hexdigest()==sha(app/'display.bit')
        (app/Path(names[0]).name).write_bytes(raw_bit)
    (app/'obj').mkdir();commands=[];logs=[]
    origin=Path(next(v for cmd in old['commands'] for v in cmd if Path(v).name=='road_fp32.c')).parent.parent
    for command in old['commands']:
        cmd=[v.replace(str(origin),str(app)).replace(origin.as_posix(),app.as_posix()) for v in command]
        assert '-o' in cmd and Path(cmd[cmd.index('-o')+1]).is_relative_to(app)
        assert all(Path(v).is_relative_to(src) for v in cmd if v.endswith('.c'))
        p=subprocess.run(cmd,capture_output=True,text=True);commands.append(cmd);logs.append(p.stdout+p.stderr);(app/'build.log').write_text('\n'.join(logs),encoding='utf-8');assert p.returncode==0,p.stderr
    elf=app/'road_detail.elf';raw=elf.read_bytes();assert f'ROAD_CONV13_READY V{VERSION}'.encode() in raw
    phoff=struct.unpack_from('<I',raw,28)[0];ent,n=struct.unpack_from('<HH',raw,42);loads=[]
    for i in range(n):
        typ,off,va,pa,fs,mem,fl,al=struct.unpack_from('<8I',raw,phoff+i*ent)
        if typ==1 and mem:assert 0x100000<=pa<pa+mem<=0x1000000;loads.append([pa,pa+mem])
    pb=read(ROOT/'host_complete.json')['packed_bytes'];regions=[list(r) for r in old['regions']]
    match=[r for r in regions if r[1]==0x18000000];assert len(match)==1;match[0][2]=pb
    regions.append(['layer_profile',0x17400000,696])
    for i,(name,a,n) in enumerate(regions):
        for name2,b,l in regions[i+1:]:assert a+n<=b or b+l<=a,(name,name2)
        for b,e in loads:assert a+n<=b or e<=a
    c=(app/'camera_common.tcl').read_text().replace('!=15',f'!={VERSION}').replace('0x13800000 96','0x13800000 144').replace('0x16500000 15','0x16500000 16')
    import re
    c=re.sub(r'elf_sha256=[0-9a-f]{64}','elf_sha256='+sha(elf),c);c=re.sub(r'bit_sha256=[0-9a-f]{64}','bit_sha256='+sha(app/'display.bit'),c)
    (app/'camera_common.tcl').write_text(c,encoding='ascii')
    c=(app/'start_default.tcl').read_text().replace('==15',f'=={VERSION}').replace('mwr 0x13800120 1','mwr 0x13800120 2').replace('ROAD_DETAIL_EXPERIMENT_LIVE_READY','ROAD_CONV13_LIVE_READY')
    if SELECT_BEST_POLICY:
        c='set selectedMode 2\nif {$argc>0} {set selectedMode [lindex $argv 0]}\nif {$selectedMode ni {1 2}} {error "Expected PL mode1 or2"}\n'+c
        c=c.replace('mwr 0x13800120 2','mwr 0x13800120 $selectedMode')
    (app/'start_default.tcl').write_text(c,encoding='ascii')
    c=(app/'experiment.py').read_text().replace('ROAD_DETAIL_EXPERIMENT_LIVE_READY','ROAD_CONV13_LIVE_READY')
    if SELECT_BEST_POLICY:c=c.replace("if args[0]=='start':command=[str(root/'start_default.tcl')]","if args[0]=='start' and (len(args)==1 or len(args)==2 and args[1] in ['1','2']):command=[str(root/'start_default.tcl'),*args[1:]]")
    (app/'experiment.py').write_text(c,encoding='ascii')
    # Existing ROI switch checks refer to17, while their semantic0/1 remains ROI.
    for name in ['switch_mode.tcl','test_static.tcl']:
        p=app/name;c=p.read_text().replace('!=15',f'!={VERSION}').replace('==15',f'=={VERSION}');p.write_text(c,encoding='ascii')
    proof=dict(old);proof.update(status='SHARED13_ARM_COMPILED_NATIVE_EXACT_NOT_BOARD_TESTED',version=VERSION,pe=PE,bit_unchanged=False,elf_sha256=sha(elf),bit_sha256=sha(app/'display.bit'),commands=commands,regions=regions,elf_loads=loads,default_pl_mode=2,pl_mode1_layers=12,pl_mode2_layers=51,weights_unchanged=True)
    proof.update(source_sha256={str(p.relative_to(src)):sha(p) for p in src.rglob('*') if p.is_file()},hls_checked_sha256=sha(HLS/'checked.json'),routed_board_proof_sha256=sha(BOARD/'offline_complete.json'))
    write(app/'arm_complete.json',proof)
    user='from pathlib import Path\nimport json,subprocess,sys\nr=Path(__file__).resolve().parent\np=r.parent/"alternating_speed.json"\nassert p.exists() and json.loads(p.read_text())["status"]=="CONV13_BYTE_EXACT_ALTERNATING_CONFIRMED_AND_LIVE", "Candidate not accepted; use ABI15 recovery"\nraise SystemExit(subprocess.call([sys.executable,str(r/"experiment.py"),"start"]))\n'
    user=user.replace('assert p.exists()', 'visual=r.parent/"manual_display_status.json"\nassert not visual.exists() or json.loads(visual.read_text(encoding="utf-8")).get("stable_promotion_allowed") is True, "Display issue unresolved; use 00_restore_ABI15.cmd"\nassert p.exists()')
    if SELECT_BEST_POLICY:user=user.replace('"start"]))','"start",str(json.loads(p.read_text())["selected_pl_mode"])]))')
    (app/'user_start.py').write_text(user,encoding='ascii')
    (app/'01_start_shared_core.cmd').write_bytes(b'@echo off\r\ncd /d "%~dp0"\r\n"E:\\FPGA_Enhance_Work\\nn_env312\\Scripts\\python.exe" "%~dp0user_start.py"\r\npause\r\n')
    (app/'00_restore_ABI15.cmd').write_bytes(b'@echo off\r\n"E:\\FPGA_Enhance_Work\\nn_env312\\Scripts\\python.exe" "E:\\FPGA_Enhance_Work\\road_detail_board_20261028_r1\\firmware\\experiment.py" start\r\npause\r\n')
    for p in app.glob('*.py'):compile(p.read_text(encoding='utf-8'),str(p),'exec')
    checks={str(p.relative_to(app)):sha(p) for p in app.rglob('*') if p.is_file() and (p.parent==app and p.suffix in ['.tcl','.py','.cmd','.elf','.bit','.xsa'] or 'runtime' in p.relative_to(app).parts or 'source' in p.relative_to(app).parts)}
    checks['arm_complete.json']=sha(app/'arm_complete.json');write(app/'runtime_checksums.json',checks)
    print('SHARED13_ARM_READY',sha(elf),pb,flush=True)

if __name__=='__main__':main()
