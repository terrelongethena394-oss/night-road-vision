"""Build a self-contained ABI30 boot application. Does not access SD or hardware."""
from pathlib import Path
import hashlib,importlib.util,json,re,shutil,struct,subprocess,zipfile
from car_roi_delivery_common import BASE,read,write,sha
from camera_snapshot_tools import fnv
from photo_station_core import APP,STAGING

ROOT=BASE/'photo_station_sd_20261031_r1'
TOOLS=Path('E:/Xilinx/Vitis/2020.2/gnu/aarch32/nt/gcc-arm-none-eabi/bin')

def main():
    assert not ROOT.exists();ROOT.mkdir();app=ROOT/'firmware';app.mkdir();shutil.copytree(APP/'source',app/'source');(app/'obj').mkdir();blobs=ROOT/'blobs';blobs.mkdir()
    for n in ['Xilinx.spec','display.bit','display.xsa','ps7_init.tcl']:shutil.copy2(APP/n,app/n)
    proof=read(APP/'arm_complete.json');assert sha(APP/'road_detail.elf')==proof['elf_sha256']
    record=read(STAGING/'actual_roundtrip_verified.json');packet=Path(record['packet_evidence']);assert sha(packet/'source800.bgr')==record['source_sha256']
    payloads=[('main',APP/'runtime/weights.f32',0x11000000,proof['weight_fnv']['detector']),
              ('roi',APP/'runtime/roi_weights.f32',0x1B000000,proof['roi_weight_fnv']),
              ('refiner',APP/'runtime/refiner_weights.f32',0x1C200000,proof['weight_fnv']['refiner']),
              ('photo',packet/'source800.bgr',0x1A300000,fnv((packet/'source800.bgr').read_bytes()))]
    manifest=[];commands=[];logs=[]
    def run(cmd,cwd=None):
        p=subprocess.run(cmd,cwd=cwd,capture_output=True,text=True);commands.append(cmd);logs.append(p.stdout+p.stderr);(ROOT/'build.log').write_text('\n'.join(logs),encoding='utf-8');assert p.returncode==0,p.stderr;return p
    objects=[]
    for name,p,address,digest in payloads:
        assert fnv(p.read_bytes())==digest
        shutil.copy2(p,blobs/(name+'.bin'));obj=app/'obj'/('sd_'+name+'.o')
        cmd=[str(TOOLS/'arm-none-eabi-objcopy.exe'),'-I','binary','-O','elf32-littlearm','-B','arm',
             '--rename-section','.data=.rodata.sd_'+name+',alloc,load,readonly,data,contents',
             '--redefine-sym',f'_binary_{name}_bin_start=sd_{name}_start','--redefine-sym',f'_binary_{name}_bin_end=sd_{name}_end',name+'.bin',str(obj)]
        run(cmd,blobs);objects.append(str(obj));manifest.append(dict(name=name,bytes=p.stat().st_size,destination=address,fnv=digest,sha256=sha(p)))
    mainfile=app/'source/road_camera_main.c';code=mainfile.read_text(encoding='ascii')
    declarations='\n'.join(f'extern const uint8_t sd_{r["name"]}_start[],sd_{r["name"]}_end[];' for r in manifest)
    code=code.replace('int main(void){',declarations+'\nint main(void){')
    needle=' for(;;){\n  service(0);';assert code.count(needle)==1
    lines=[' /* Self-contained data loaded as ELF sections; no runtime SD writes. */',' m[266]=0x53443330U;m[267]=1;']
    for i,r in enumerate(manifest):
        n=r['name'];address=r['destination'];size=r['bytes'];digest=r['fnv']
        lines+= [f' if((uint32_t)(sd_{n}_end-sd_{n}_start)!={size}U || hash(sd_{n}_start,{size}U)!={digest}U)fatal({300+i}U);',
                 f' memcpy((void *)0x{address:08X}U,sd_{n}_start,{size}U);Xil_DCacheFlushRange(0x{address:08X}U,{size}U);',
                 f' if(hash((const void *)0x{address:08X}U,{size}U)!={digest}U)fatal({310+i}U);']
    lines+=[' m[27]=m[28]=m[136]=m[137]=m[138]=0;',f' m[157]={manifest[-1]["fnv"]}U;',
            ' m[46]=1;m[175]=0;m[72]=2;m[80]=2;m[94]=2;m[M_COMMAND]=5;barrier();']
    code=code.replace(needle,'\n'.join(lines)+'\n'+needle).replace('ROAD_NATIVE_ROI_READY V30 raw_preview_enhanced_detection no_sd','ROAD_NATIVE_ROI_SD_READY V30 embedded_photo_and_models')
    mainfile.write_text(code,encoding='ascii')
    lscript=app/'source/lscript.ld';text=lscript.read_text();assert text.count('LENGTH = 0x00F00000')==1
    lscript.write_text(text.replace('LENGTH = 0x00F00000','LENGTH = 0x01F00000'),encoding='ascii')
    def relocate(s):return s.replace(str(APP),str(app)).replace(APP.as_posix(),app.as_posix())
    for old in proof['commands']:
        cmd=[relocate(s) for s in old]
        if '-c' not in cmd:
            at=cmd.index('-Wl,--start-group');cmd[at:at]=objects
        run(cmd)
    elf=app/'road_detail.elf';raw=elf.read_bytes();phoff=struct.unpack_from('<I',raw,28)[0];ents,n=struct.unpack_from('<HH',raw,42);segments=[]
    for i in range(n):
        typ,off,va,pa,fs,mem,flags,align=struct.unpack_from('<8I',raw,phoff+i*ents)
        if typ==1 and mem:
            assert 0x100000<=pa<pa+mem<=0x02000000,(hex(pa),hex(pa+mem));segments.append((pa,raw[off:off+fs],mem))
    symbols=run([str(TOOLS/'arm-none-eabi-nm.exe'),str(elf)]).stdout
    for r in manifest:
        n=r['name'];start=int(re.search(r'^([0-9a-fA-F]+)\s+\w\s+sd_'+n+'_start$',symbols,re.M)[1],16);end=int(re.search(r'^([0-9a-fA-F]+)\s+\w\s+sd_'+n+'_end$',symbols,re.M)[1],16)
        original=(blobs/(n+'.bin')).read_bytes();assert end-start==len(original)
        assert any(a<=start and end<=a+len(d) and d[start-a:end-a]==original for a,d,mem in segments)
        r['embedded_start']=start;r['embedded_end']=end
    for name,address,size in proof['regions']:
        assert all(pa+mem<=address or address+size<=pa for pa,d,mem in segments),(name,hex(address))
    old=BASE/'camera_nn_sd_20261018';prior=read(old/'boot_image_validation.json');assert sha(old/'fsbl.elf')==prior['sha256']['fsbl.elf']
    with zipfile.ZipFile(app/'display.xsa') as z:
        for name in ['ps7_init.c','ps7_init.h']:
            matches=[n for n in z.namelist() if Path(n).name==name];assert len(matches)==1
            current=z.read(matches[0]);previous=(old/'vitis_ws/nn_fsbl/src'/name).read_bytes()
            # Generated timestamps/comments may differ; hardware initialization code must match.
            clean=lambda b:re.sub(rb'\s+',b'',re.sub(rb'/\*.*?\*/|//[^\r\n]*',b'',b,flags=re.S))
            assert clean(current)==clean(previous),'FSBL PS configuration mismatch: '+name
    shutil.copy2(old/'fsbl.elf',ROOT/'fsbl.elf');shutil.copy2(app/'display.bit',ROOT/'display.bit');shutil.copy2(elf,ROOT/'photo_station_sd.elf')
    (ROOT/'boot.bif').write_text('the_ROM_image:\n{\n [bootloader] fsbl.elf\n display.bit\n photo_station_sd.elf\n}\n',encoding='ascii')
    p=run(['E:/Xilinx/Vitis/2020.2/bin/bootgen.bat','-arch','zynq','-image','boot.bif','-o','BOOT.BIN'],ROOT)
    boot=(ROOT/'BOOT.BIN').read_bytes();assert len(boot)<32*1024*1024
    spec=importlib.util.spec_from_file_location('sd_parser',old/'verify_nn_sd.py');parser=importlib.util.module_from_spec(spec);spec.loader.exec_module(parser)
    word=lambda off:struct.unpack_from('<I',boot,off)[0]
    assert word(0x20)==0xAA995566 and word(0x24)==0x584c4e58 and sum(struct.unpack_from('<11I',boot,0x20))&0xffffffff==0xffffffff
    iht,pht=word(0x98),word(0x9c);assert word(iht+4)==3;parts=[]
    for i,name in enumerate(['fsbl.elf','display.bit','photo_station_sd.elf']):
        ph=struct.unpack_from('<16I',boot,pht+64*i);assert sum(ph)&0xffffffff==0xffffffff
        length,load,entry,offset=ph[2]*4,ph[3],ph[4],ph[5]*4;payload=boot[offset:offset+length];assert len(payload)==length
        if name.endswith('.elf'):
            expected,ss=parser.elf_segments(ROOT/name);assert entry==expected
            for addr,data in ss:assert addr>=load and payload[addr-load:addr-load+len(data)]==data
        else:
            b=parser.bit_payload(ROOT/name);swap=b''.join(b[j:j+4][::-1] for j in range(0,len(b),4));assert payload[:len(b)] in [b,swap]
        parts.append(dict(name=name,load=load,entry=entry,bytes=length,source_bytes_exact=True))
    write(ROOT/'build_verified.json',dict(status='SELF_CONTAINED_ABI30_SD_IMAGE_BUILT_NOT_YET_BOARD_TESTED',boot_bytes=len(boot),boot_sha256=sha(ROOT/'BOOT.BIN'),
        elf_sha256=sha(elf),bit_sha256=sha(app/'display.bit'),payloads=manifest,partitions=parts,elf_regions=[[a,a+mem] for a,d,mem in segments],
        baseline_elf_sha256=proof['elf_sha256'],expected_packet=str(packet),source_sha256={p.name:sha(p) for p in (app/'source').iterdir() if p.is_file()},
        arm_commands=commands,sd_written=False,physical_cold_boot_verified=False))
    print('PHOTO_STATION_SD_BOOT_BUILT_AND_BYTE_VERIFIED',len(boot),sha(ROOT/'BOOT.BIN'),flush=True)

if __name__=='__main__':main()
