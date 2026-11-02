"""Self-contained road SD image: FSBL + known bit + embedded-weight/photo app.
PC build only. No card, Flash or boot-switch access.
"""
from pathlib import Path
import importlib.util,shutil,struct,subprocess,re,json
from road_arm_common import ROOT as NN,read,write,sha
from prepare_road_lcd_static import ROOT as LCD
from build_road_arm_probe import fnv
ROOT=Path('E:/FPGA_Enhance_Work/road_sd_20261027')
TOOLS=Path('E:/Xilinx/Vitis/2020.2/gnu/aarch32/nt/gcc-arm-none-eabi/bin')
PLATFORM=Path('E:/FPGA_Enhance_Work/multinex_static_20261025/vitis_ws/static_platform/export/static_platform/sw/static_platform/standalone_domain')
def main():
    verified=read(LCD/'release.json');assert verified['physical_panel_visually_confirmed']
    assert sha(LCD/'road_lcd.elf')==verified['elf_sha256']
    ROOT.mkdir(exist_ok=False);source=ROOT/'source';shutil.copytree(LCD/'source',source)
    first=read(NN/'export_complete.json')['fixtures'][0]['name'];weights=NN/'weights.f32';image=NN/'cases'/first/'input400.u32'
    blobs=ROOT/'blobs';blobs.mkdir();shutil.copy2(weights,blobs/'autoweights.bin');shutil.copy2(image,blobs/'autophoto.bin')
    p=source/'road_lcd_main.c';code=p.read_text(encoding='ascii');needle='int main(void){'
    assert code.count(needle)==1
    code=code.replace(needle,'extern const uint8_t road_sd_weights_start[],road_sd_weights_end[],road_sd_photo_start[],road_sd_photo_end[];\n'+needle)
    needle='  for(;;){\n    mail[M_HEARTBEAT]++;';assert code.count(needle)==1
    auto=f'''  /* Self-contained SD entry: FSBL loads these read-only blobs with the ELF. */
  mail[M_STATE]=2;barrier();
  if((uint32_t)(road_sd_weights_end-road_sd_weights_start)!=ROAD_WEIGHT_FLOATS*4U ||
     (uint32_t)(road_sd_photo_end-road_sd_photo_start)!=400U*240U*4U){{mail[M_ERROR]=300;mail[M_STATE]=4;barrier();for(;;){{mail[M_HEARTBEAT]++;usleep(1000);}}}}
  memcpy((void *)WEIGHT_ADDR,road_sd_weights_start,ROAD_WEIGHT_FLOATS*4U);
  memcpy((void *)INPUT_ADDR,road_sd_photo_start,400U*240U*4U);
  Xil_DCacheFlushRange(WEIGHT_ADDR,ROAD_WEIGHT_FLOATS*4U);Xil_DCacheFlushRange(INPUT_ADDR,400U*240U*4U);
  mail[M_INPUT_EXPECTED_FNV]=0x{fnv(image.read_bytes()):08x}U;mail[M_CASE_ID]=1;mail[M_TRACE_ENABLE]=0;
  mail[39]=0x53444231U;mail[M_COMMAND]=1;barrier();
'''
    code=code.replace(needle,auto+needle);p.write_text(code,encoding='ascii')
    assert sha(source/'road_fp32.c')==read(LCD/'offline_complete.json')['kernel_sha256']
    shutil.copy2(LCD/'Xilinx.spec',ROOT/'Xilinx.spec');obj=ROOT/'obj';obj.mkdir();commands=[];logs=[];objects=[]
    for name,prefix in [('autoweights','road_sd_weights'),('autophoto','road_sd_photo')]:
        cmd=[str(TOOLS/'arm-none-eabi-objcopy.exe'),'-I','binary','-O','elf32-littlearm','-B','arm',
             '--rename-section','.data=.rodata.'+name+',alloc,load,readonly,data,contents',
             '--redefine-sym','_binary_'+name+'_bin_start='+prefix+'_start','--redefine-sym','_binary_'+name+'_bin_end='+prefix+'_end',name+'.bin',str(obj/(name+'.o'))]
        p=subprocess.run(cmd,cwd=blobs,capture_output=True,text=True);commands.append(cmd);assert p.returncode==0,p.stderr;objects.append(str(obj/(name+'.o')))
    flags=['-mcpu=cortex-a9','-mfpu=neon-vfpv3','-mfloat-abi=hard','-O3','-std=c99','-ffp-contract=off','-fno-fast-math','-fno-common','-Wall','-g','-I'+str(source),'-I'+str(PLATFORM/'bspinclude/include')]
    files=[source/n for n in ['road_fp32.c','road_lcd.c','road_lcd_draw.c','road_lcd_main.c']]+[p for d in ['display_ctrl','clk_wiz','vdma_api'] for p in sorted((source/d).glob('*.c'))]
    for p in files:
        target=obj/('_'.join(p.relative_to(source).parts)+'.o');strict=['-Wextra','-Werror'] if p.parent==source else []
        cmd=[str(TOOLS/'arm-none-eabi-gcc.exe'),*flags,*strict,'-c',str(p),'-o',str(target)]
        run=subprocess.run(cmd,capture_output=True,text=True);commands.append(cmd);logs.append(run.stdout+run.stderr);(ROOT/'build.log').write_text('\n'.join(logs));assert run.returncode==0,run.stderr;objects.append(str(target))
    elf=ROOT/'road_sd.elf';cmd=[str(TOOLS/'arm-none-eabi-gcc.exe'),*flags[:3],'-Wl,-build-id=none','-specs='+str(ROOT/'Xilinx.spec'),'-Wl,-T,'+str(source/'lscript.ld'),'-Wl,-Map,'+str(ROOT/'road_sd.map'),'-L'+str(PLATFORM/'bsplib/lib'),'-o',str(elf),*objects,'-Wl,--start-group','-lxil','-lgcc','-lc','-lm','-Wl,--end-group']
    run=subprocess.run(cmd,capture_output=True,text=True);commands.append(cmd);logs.append(run.stdout+run.stderr);(ROOT/'build.log').write_text('\n'.join(logs));assert run.returncode==0,run.stderr
    raw=elf.read_bytes();phoff=struct.unpack_from('<I',raw,28)[0];ent,n=struct.unpack_from('<HH',raw,42);regions=[];segments=[]
    for i in range(n):
        kind,off,va,pa,fs,ms,fl,al=struct.unpack_from('<8I',raw,phoff+i*ent)
        if kind==1 and ms:assert 0x100000<=pa<pa+ms<=0x1000000;regions.append([pa,pa+ms]);segments.append((pa,raw[off:off+fs]))
    symbols=subprocess.run([str(TOOLS/'arm-none-eabi-nm.exe'),str(elf)],capture_output=True,text=True,check=True).stdout
    for prefix,name in [('road_sd_weights','autoweights'),('road_sd_photo','autophoto')]:
        start=int(re.search(r'^([0-9a-fA-F]+)\s+\w\s+'+prefix+r'_start$',symbols,re.M)[1],16)
        end=int(re.search(r'^([0-9a-fA-F]+)\s+\w\s+'+prefix+r'_end$',symbols,re.M)[1],16)
        original=(blobs/(name+'.bin')).read_bytes();assert end-start==len(original)
        assert any(addr<=start and end<=addr+len(data) and data[start-addr:end-addr]==original for addr,data in segments)
    old=Path('E:/FPGA_Enhance_Work/camera_nn_sd_20261018');prior=read(old/'boot_image_validation.json')
    assert sha(old/'fsbl.elf')==prior['sha256']['fsbl.elf']
    for name in ['ps7_init.c','ps7_init.h']:
        assert sha(old/'vitis_ws/nn_fsbl/src'/name)==sha(Path('E:/FPGA_Enhance_Work/camera_plate_guarded_20261026')/name)
    shutil.copy2(old/'fsbl.elf',ROOT/'fsbl.elf');shutil.copy2(LCD/'display.bit',ROOT/'display.bit');shutil.copy2(LCD/'display.xsa',ROOT/'display.xsa');shutil.copy2(LCD/'ps7_init.tcl',ROOT/'ps7_init.tcl')
    (ROOT/'boot.bif').write_text('the_ROM_image:\n{\n [bootloader] fsbl.elf\n display.bit\n road_sd.elf\n}\n',encoding='ascii')
    p=subprocess.run(['E:/Xilinx/Vitis/2020.2/bin/bootgen.bat','-arch','zynq','-image','boot.bif','-o','BOOT.BIN'],cwd=ROOT,capture_output=True,text=True)
    (ROOT/'bootgen.log').write_text(p.stdout+p.stderr);assert p.returncode==0 and (ROOT/'BOOT.BIN').exists(),p.stderr
    spec=importlib.util.spec_from_file_location('road_sd_parser',old/'verify_nn_sd.py');parser=importlib.util.module_from_spec(spec);spec.loader.exec_module(parser)
    boot=(ROOT/'BOOT.BIN').read_bytes();word=lambda off:struct.unpack_from('<I',boot,off)[0]
    assert len(boot)<16*1024*1024 and word(0x20)==0xAA995566 and word(0x24)==0x584C4E58
    assert sum(struct.unpack_from('<11I',boot,0x20))&0xffffffff==0xffffffff
    iht,pht=word(0x98),word(0x9c);assert word(iht+4)==3;partitions=[]
    for i,name in enumerate(['fsbl.elf','display.bit','road_sd.elf']):
        ph=struct.unpack_from('<16I',boot,pht+64*i);assert sum(ph)&0xffffffff==0xffffffff
        length,load,entry,offset=ph[2]*4,ph[3],ph[4],ph[5]*4;payload=boot[offset:offset+length];assert len(payload)==length
        if name.endswith('.elf'):
            expected,ss=parser.elf_segments(ROOT/name);assert entry==expected
            for addr,data in ss:assert addr>=load and payload[addr-load:addr-load+len(data)]==data
        else:
            b=parser.bit_payload(ROOT/name);swap=b''.join(b[j:j+4][::-1] for j in range(0,len(b),4));assert payload[:len(b)] in [b,swap]
        partitions.append(dict(name=name,load=load,entry=entry,bytes=length,source_bytes_exact=True))
    assert partitions[0]['load']==0 and partitions[0]['bytes']<0x30000 and partitions[2]['load']==0x100000
    report=dict(status='SELF_CONTAINED_ROAD_SD_BOOT_HEADERS_PARTITIONS_AND_EMBEDDED_BLOBS_VERIFIED',boot_bytes=len(boot),boot_sha256=sha(ROOT/'BOOT.BIN'),
         elf_sha256=sha(elf),bit_sha256=sha(ROOT/'display.bit'),weights_sha256=sha(weights),photo_sha256=sha(image),first_fixture=first,
         elf_regions=regions,partitions=partitions,commands=commands,auto_boot_flag=0x53444231,sd_written=False,physical_sd_cold_boot=False)
    write(ROOT/'boot_image_validation.json',report)
    # Same numerical/framebuffer validator, parameterized to this embedded app.
    o=read(LCD/'offline_complete.json');o.update(elf_sha256=sha(elf),status='SELF_CONTAINED_APP_COMPILED_NOT_YET_PHYSICAL_AUTOSTART_TESTED');write(ROOT/'offline_complete.json',o)
    write(ROOT/'download_tools.json',read(LCD/'download_tools.json'));(ROOT/'host').mkdir();shutil.copy2(LCD/'host/render.exe',ROOT/'host/render.exe')
    print('ROAD_SELF_CONTAINED_SD_BOOT_IMAGE_VERIFIED',len(boot),sha(ROOT/'BOOT.BIN'),flush=True)
if __name__=='__main__':main()
