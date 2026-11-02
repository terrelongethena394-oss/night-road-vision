"""Syntax/ABI precheck using register offset extracted from synthesized RTL.
No executable is linked or downloaded; actual exported driver is used later.
"""
from pathlib import Path
import subprocess,re
from prepare_fp32_cpu_pack import CURRENT,read,write,sha
from prepare_road_conv13 import ROOT as HLS
from prepare_road_conv13_runtime import ROOT

def main():
    d=ROOT/'arm_precheck';d.mkdir();app=ROOT/'firmware';src=app/'source'
    rtl=HLS/'conv_project/solution_100mhz/syn/verilog/road_conv3_fp32_control_s_axi.v'
    match=re.search(r'ADDR_KERNEL_DATA_0\s*=\s*\d+\x27h([0-9a-f]+)',rtl.read_text());assert match
    off=int(match[1],16);header=(src/'xroad_conv3_fp32_hw.h').read_text()+f'\n#define XROAD_CONV3_FP32_CONTROL_ADDR_KERNEL_DATA 0x{off:x}\n#define XROAD_CONV3_FP32_CONTROL_BITS_KERNEL_DATA 32\n'
    (d/'xroad_conv3_fp32_hw.h').write_text(header,encoding='ascii')
    c=(src/'road_pl.c').read_text();(d/'road_pl.c').write_text(c,encoding='ascii')
    old=read(CURRENT/'arm_complete.json');origin=Path(next(v for cmd in old['commands'] for v in cmd if Path(v).name=='road_fp32.c')).parent.parent
    commands=[];logs=[]
    for command in old['commands']:
        if '-c' not in command:continue
        cmd=[v.replace(str(origin),str(app)).replace(origin.as_posix(),app.as_posix()) for v in command]
        cmd.insert(1,'-I'+str(d))
        cmd[cmd.index('-o')+1]=str(d/Path(cmd[cmd.index('-o')+1]).name)
        cmd=[str(d/'road_pl.c') if v==str(src/'road_pl.c') else v for v in cmd]
        p=subprocess.run(cmd,capture_output=True,text=True);commands.append(cmd);logs.append(p.stdout+p.stderr);(d/'build.log').write_text('\n'.join(logs));assert p.returncode==0,p.stderr
    write(d/'complete.json',dict(status='ARM_SYNTAX_PRECHECK_ONLY_NO_ELF_OR_HARDWARE',kernel_offset=off,control_rtl_sha256=sha(rtl),commands=commands,sd_written=False))
    print('CONV13_ARM_PRECHECK_PASS',hex(off),len(commands),flush=True)

if __name__=='__main__':main()
