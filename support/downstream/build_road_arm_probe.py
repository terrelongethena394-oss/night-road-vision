"""Cross-compile the verified host kernel; audit exact DDR regions and NEON code.
No hardware connection, SD access, boot image creation or board writes.
"""
from pathlib import Path
import os,struct,shutil,subprocess,re,sys
from road_arm_common import ROOT,read,write,sha
HERE=Path(__file__).resolve().parent
PLATFORM=Path('E:/FPGA_Enhance_Work/multinex_static_20261025/vitis_ws/static_platform/export/static_platform/sw/static_platform/standalone_domain')
TOOLS=Path('E:/Xilinx/Vitis/2020.2/gnu/aarch32/nt/gcc-arm-none-eabi/bin')
def fnv(data):
    h=2166136261
    for v in data:h=((h^v)*16777619)&0xffffffff
    return h
def main():
    revision=('_'+sys.argv[1]) if len(sys.argv)>1 and sys.argv[1] in ['r1','r2'] else ''
    source_revision=revision if revision else '_r1'
    proof=read(ROOT/('host_complete'+source_revision+'.json'));g=read(ROOT/'graph.json');arm=ROOT/('arm_probe'+revision);arm.mkdir(exist_ok=False)
    src=arm/'source';src.mkdir()
    for name in ['road_fp32.h','road_fp32.c','road_graph.h']:
        assert sha(ROOT/('source'+source_revision)/name)==proof['source_sha256'][name]
        shutil.copy2(ROOT/('source'+source_revision)/name,src/name)
    shutil.copy2(HERE/'road_arm_probe.c',src/'road_arm_probe.c')
    h=fnv((ROOT/'weights.f32').read_bytes());(src/'road_probe_config.h').write_text(f'#define ROAD_EXPECTED_WEIGHT_FNV 0x{h:08x}U\n',encoding='ascii')
    old=Path('E:/FPGA_Enhance_Work/camera_plate_guarded_20261026')
    shutil.copy2(old/'Xilinx.spec',arm/'Xilinx.spec');linker=(old/'app_src/lscript.ld').read_text()
    linker=linker.replace(': 0x2000;',': 0x10000;');(src/'lscript.ld').write_text(linker,encoding='ascii')
    flags=['-mcpu=cortex-a9','-mfpu=neon-vfpv3','-mfloat-abi=hard','-O3','-std=c99','-ffp-contract=off','-fno-fast-math','-fno-common',
           '-Wall','-Wextra','-Werror','-g','-fstack-usage','-I'+str(src),'-I'+str(PLATFORM/'bspinclude/include')]
    gcc=TOOLS/'arm-none-eabi-gcc.exe';commands=[];log=[];objects=[]
    for name in ['road_fp32.c','road_arm_probe.c']:
        target=arm/(name+'.o');cmd=[str(gcc),*flags,'-c',str(src/name),'-o',str(target)]
        p=subprocess.run(cmd,capture_output=True,text=True);commands.append(cmd);log.append(p.stdout+p.stderr)
        (arm/'build.log').write_text('\n'.join(log));assert p.returncode==0,p.stderr;objects.append(str(target))
    elf=arm/'road_probe.elf';cmd=[str(gcc),*flags[:3],'-Wl,-build-id=none','-specs='+str(arm/'Xilinx.spec'),'-Wl,-T,'+str(src/'lscript.ld'),
         '-Wl,-Map,'+str(arm/'road_probe.map'),'-L'+str(PLATFORM/'bsplib/lib'),'-o',str(elf),*objects,'-Wl,--start-group','-lxil','-lgcc','-lc','-lm','-Wl,--end-group']
    p=subprocess.run(cmd,capture_output=True,text=True);commands.append(cmd);log.append(p.stdout+p.stderr);(arm/'build.log').write_text('\n'.join(log));assert p.returncode==0,p.stderr
    raw=elf.read_bytes();assert raw[:7]==b'\x7fELF\x01\x01\x01' and struct.unpack_from('<H',raw,18)[0]==40
    phoff=struct.unpack_from('<I',raw,28)[0];ent,n=struct.unpack_from('<HH',raw,42);loads=[]
    for i in range(n):
        kind,off,va,pa,sz,ms,fl,al=struct.unpack_from('<8I',raw,phoff+i*ent)
        if kind==1 and ms:
            assert 0x100000<=pa<pa+ms<=0x1000000;loads.append(dict(start=pa,end=pa+ms,file_bytes=sz,flags=fl))
    xparams=(PLATFORM/'bspinclude/include/xparameters.h').read_text();ddr_high=int(re.search(r'#define XPAR_PS7_DDR_0_S_AXI_HIGHADDR\s+(0x\w+)',xparams)[1],16)
    trace_bytes=sum(t['elements']*4 for t in g['tensors']);assert trace_bytes<0x04000000
    areas=[('raw400',0x10000000,400*240*4),('weights',0x11000000,g['weights_floats']*4),('arena',0x12000000,g['arena_floats']*4),
           ('decoded',0x13000000,6300*9*4),('rgb320',0x13200000,320*320*3),('candidates',0x13400000,6300*28),
           ('keep_structs',0x13500000,300*28),('boxes400',0x13600000,300*6*4),('boxes320',0x13610000,300*6*4),('mailbox',0x13800000,4096),('all_layer_traces',0x14000000,trace_bytes)]
    for i,(name,start,bytes_) in enumerate(areas):
        assert 0x10000000<=start<start+bytes_<=ddr_high+1
        for name2,a,b in areas[:i]:assert start+bytes_<=a or start>=a+b,(name,name2)
        for load in loads:assert start+bytes_<=load['start'] or start>=load['end']
    dis=subprocess.run([str(TOOLS/'arm-none-eabi-objdump.exe'),'-d',str(elf)],capture_output=True,text=True,check=True).stdout;(arm/'disassembly.txt').write_text(dis)
    neon=re.findall(r'\bvmla\.f32\s+q\d+',dis);assert neon,'NEON vector multiply-accumulate absent'
    attrs=subprocess.run([str(TOOLS/'arm-none-eabi-readelf.exe'),'-h','-A',str(elf)],capture_output=True,text=True,check=True).stdout;(arm/'elf_attributes.txt').write_text(attrs)
    assert 'Cortex-A9' in attrs or '7-A' in attrs
    assert 'VFP registers' in attrs
    trace=[];offset=0
    for t in g['tensors']:trace.append(dict(id=t['id'],name=t['name'],address=0x14000000+offset,bytes=t['elements']*4));offset+=t['elements']*4
    write(arm/'trace_map.json',trace)
    stacks=[]
    for p in arm.glob('*.su'):
        for line in p.read_text().splitlines():
            pieces=line.split('\t')
            if len(pieces)>=2 and pieces[1].isdigit():stacks.append(dict(function=pieces[0],bytes=int(pieces[1]),kind=pieces[-1]))
    assert stacks and max(x['bytes'] for x in stacks)<32768
    write(ROOT/('arm_compile_complete'+revision+'.json'),dict(status='CORTEX_A9_NEON_ELF_CROSS_COMPILED_AND_STATIC_MEMORY_AUDITED_NOT_BOARD_RUN',
          elf=str(elf),elf_bytes=elf.stat().st_size,elf_sha256=sha(elf),source_sha256={p.name:sha(p) for p in src.iterdir() if p.is_file()},
          host_verified_kernel_sha256=proof['source_sha256']['road_fp32.c'],commands=commands,elf_loads=loads,ddr_high=ddr_high,
          work_regions=[dict(name=n,start=a,end=a+b,bytes=b) for n,a,b in areas],trace_bytes=trace_bytes,neon_vmla_sites=len(neon),
          weight_fnv32=h,weights_sha256=sha(ROOT/'weights.f32'),function_stack_usage=stacks,configured_stack_bytes=65536,
          host_probe_framework_tested=False,arm_executed=False,board_downloaded=False,sd_written=False))
    print('ROAD_CORTEX_A9_NEON_PROBE_COMPILED',elf.stat().st_size,'NEON sites',len(neon),flush=True)
if __name__=='__main__':main()
