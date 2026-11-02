"""Offline Cortex-A9 candidate and portable JTAG RAM test package. Never runs XSCT."""
import os,re,shutil,subprocess,struct,tkinter
from pathlib import Path
from road_integer_common import ROOT,FLOAT,read,write,sha
from build_road_arm_probe import fnv
from prepare_road_lcd_static import ROOT as LCD,PLATFORM,TOOLS
from verify_road_integer_host import GCC
HERE=Path(__file__).resolve().parent

def main():
    folder=ROOT/'m125';fast=read(folder/'fast_r1/complete.json');assert fast['no_accuracy_change']
    out=folder/'arm_lcd_r1';out.mkdir(exist_ok=False);source=out/'source';shutil.copytree(LCD/'source',source)
    selected=folder/'fast_r1/source' if fast['host_only_median_cpu_seconds']['q8fast']<fast['host_only_median_cpu_seconds']['q8plain'] else folder/'source'
    for name in ['road_graph.h','road_q8_tables.h','road_q8_fast.h']:
        if (selected/name).exists():shutil.copy2(selected/name,source/name)
    shutil.copy2(selected/'road_q8.c',source/'road_fp32.c');qfnv=fnv((folder/'qmodel.bin').read_bytes())
    (source/'road_probe_config.h').write_text(f'#define ROAD_EXPECTED_WEIGHT_FNV 0x{qfnv:08x}U\n',encoding='ascii')
    p=source/'road_lcd_main.c';code=p.read_text();assert code.count('mail[M_VERSION]=2;')==1;code=code.replace('mail[M_VERSION]=2;','mail[M_VERSION]=3;')
    code=code.replace('ROAD_LCD_STATIC_READY V2','ROAD_LCD_Q8_READY V3');p.write_text(code,encoding='ascii')
    p=source/'road_lcd_draw.c';code=p.read_text();assert 'STATIC ROAD TEST' in code;code=code.replace('STATIC ROAD TEST','ROAD TEST Q8 CONV');p.write_text(code,encoding='ascii')
    for name in ['display.bit','display.xsa','ps7_init.tcl','Xilinx.spec']:shutil.copy2(LCD/name,out/name)
    obj=out/'obj';obj.mkdir();commands=[];logs=[];objects=[]
    flags=['-mcpu=cortex-a9','-mfpu=neon-vfpv3','-mfloat-abi=hard','-O3','-std=c99','-ffp-contract=off','-fno-fast-math','-fno-common','-Wall','-g','-fstack-usage','-I'+str(source),'-I'+str(PLATFORM/'bspinclude/include')]
    files=[source/n for n in ['road_fp32.c','road_lcd.c','road_lcd_draw.c','road_lcd_main.c']]+[p for d in ['display_ctrl','clk_wiz','vdma_api'] for p in sorted((source/d).glob('*.c'))]
    for p in files:
        target=obj/('_'.join(p.relative_to(source).parts)+'.o');strict=['-Wextra','-Werror'] if p.parent==source else []
        cmd=[str(TOOLS/'arm-none-eabi-gcc.exe'),*flags,*strict,'-c',str(p),'-o',str(target)]
        run=subprocess.run(cmd,capture_output=True,text=True);commands.append(cmd);logs.append(run.stdout+run.stderr);(out/'build.log').write_text('\n'.join(logs));assert run.returncode==0,run.stderr;objects.append(str(target))
    elf=out/'road_lcd.elf';cmd=[str(TOOLS/'arm-none-eabi-gcc.exe'),*flags[:3],'-Wl,-build-id=none','-specs='+str(out/'Xilinx.spec'),'-Wl,-T,'+str(source/'lscript.ld'),'-Wl,-Map,'+str(out/'road_lcd.map'),'-L'+str(PLATFORM/'bsplib/lib'),'-o',str(elf),*objects,'-Wl,--start-group','-lxil','-lgcc','-lc','-lm','-Wl,--end-group']
    run=subprocess.run(cmd,capture_output=True,text=True);commands.append(cmd);logs.append(run.stdout+run.stderr);(out/'build.log').write_text('\n'.join(logs));assert run.returncode==0,run.stderr
    raw=elf.read_bytes();phoff=struct.unpack_from('<I',raw,28)[0];ent,n=struct.unpack_from('<HH',raw,42);regions=[]
    for i in range(n):
        kind,off,va,pa,fs,ms,fl,al=struct.unpack_from('<8I',raw,phoff+i*ent)
        if kind==1 and ms:assert 0x100000<=pa<pa+ms<=0x1000000;regions.append([pa,pa+ms])
    asm=subprocess.run([str(TOOLS/'arm-none-eabi-objdump.exe'),'-d',str(obj/'road_fp32.c.o')],capture_output=True,text=True,check=True).stdout
    (out/'kernel_assembly.txt').write_text(asm);assert 'vmlal.s16' in asm
    host=out/'host';host.mkdir();env=os.environ.copy();env['PATH']=str(GCC.parent)+os.pathsep+env.get('PATH','')
    cmd=[str(GCC),'-O2','-std=c99','-Wall','-Wextra','-Werror','-I'+str(source),str(source/'road_lcd_draw.c'),str(source/'road_lcd_draw_host.c'),'-o',str(host/'render.exe'),'-lm']
    run=subprocess.run(cmd,env=env,capture_output=True,text=True);commands.append(cmd);assert run.returncode==0,run.stderr
    fixtures=read(FLOAT/'export_complete.json')['fixtures'];runtime=out/'runtime';runtime.mkdir();shutil.copy2(folder/'qmodel.bin',runtime/'model.bin')
    for fixture in fixtures:
        name=fixture['name'];case=runtime/'cases'/name;case.mkdir(parents=True);shutil.copy2(FLOAT/'cases'/name/'input400.u32',case/'input400.u32')
    first=fixtures[0]['name'];subprocess.run([str(host/'render.exe'),str(runtime/'cases'/first/'input400.u32'),str(folder/'host'/first/'boxes400.f32'),str(host/'preview.bgr'),'0','1'],capture_output=True,text=True,check=True)
    from PIL import Image
    import numpy as np
    Image.fromarray(np.fromfile(host/'preview.bgr',np.uint8).reshape(480,800,3)[:,:,::-1]).save(out/'host_preview.png')
    tcl=(LCD/'install_ram.tcl').read_text();tcl=tcl.replace('[word 0x13800004]==2','[word 0x13800004]==3').replace('1483844061',str(qfnv)).replace('$nn/weights.f32','$nn/model.bin')
    tcl=tcl.replace(read(LCD/'offline_complete.json')['elf_sha256'],sha(elf)).replace(sha(FLOAT/'weights.f32'),sha(folder/'qmodel.bin'))
    tcl=tcl.replace('physical_lcd_framebuffer_jtag_readback','physical_q8_lcd_framebuffer_jtag_readback').replace('ROAD_LCD_PHYSICAL_READBACK_COMPLETE','ROAD_Q8_PHYSICAL_READBACK_COMPLETE')
    tcl=tcl.replace('mwr 0x13800070 0','mwr 0x13800070 1')
    needle=' mrd -bin -file $out/mailbox.bin 0x13800000 39';assert tcl.count(needle)==1
    tcl=tcl.replace(needle,needle+'\n set trace_bytes [word 0x13800038]\n if {$trace_bytes<=0 || $trace_bytes>20000000 || $trace_bytes%4!=0} {error "Invalid integer trace length"}\n mrd -bin -file $out/trace.bin 0x14000000 [expr {$trace_bytes/4}]')
    assert int(tkinter.Tcl().call('info','complete',tcl))==1
    (out/'install_ram.tcl').write_text(tcl,encoding='ascii')
    cmd='@echo off\r\ncd /d "%~dp0"\r\ncall "E:\\Xilinx\\Vitis\\2020.2\\bin\\xsct.bat" "%~dp0install_ram.tcl" %*\r\necho Check ROAD_Q8_PHYSICAL_READBACK_COMPLETE; exit code alone is insufficient.\r\npause\r\n'
    (out/'00_install_ram.cmd').write_text(cmd,encoding='ascii')
    meta=dict(status='OFFLINE_ARM_NEON_Q8_LCD_COMPILED_HOST_PROVEN_WAITING_FOR_BOARD',elf_sha256=sha(elf),bit_sha256=sha(out/'display.bit'),model_sha256=sha(folder/'qmodel.bin'),
      model_bytes=(folder/'qmodel.bin').stat().st_size,weight_fnv32=qfnv,mail_version=3,source_sha256={str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()},
      kernel_source=str(selected),elf_regions=regions,commands=commands,neon_s16_long_mac_present=True,full_trace_default=True,known_good_rollback=str(LCD/'00_install_ram.cmd'),
      board_run=False,board_speedup_unknown=True,camera_enabled=False,sd_written=False)
    write(out/'offline_complete.json',meta);print('Q8_ARM_LCD_READY_OFFLINE',sha(elf),regions,flush=True)
if __name__=='__main__':main()
