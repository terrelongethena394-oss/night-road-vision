"""Build a separate DDR image-input ARM application against the existing BSP."""
from pathlib import Path
import hashlib,json,shutil,struct,subprocess

HERE=Path(__file__).resolve().parent
ROOT=Path('E:/FPGA_Enhance_Work/fixed_image_test_20261025')
CAMERA=Path('E:/FPGA_Enhance_Work/camera_nn_digit_20261023')
BSP=CAMERA/'vitis_ws/digit_platform/export/digit_platform/sw/digit_platform/standalone_domain'
TOOL=Path('E:/Xilinx/Vitis/2020.2/gnu/aarch32/nt/gcc-arm-none-eabi/bin')

def main():
    ROOT.mkdir(exist_ok=True)
    app=ROOT/'app_src'
    if not app.exists():
        shutil.copytree(CAMERA/'app_src',app)
    else:
        assert 'IMAGE_TEST_READY no_camera no_s2mm' in (app/'main.c').read_text(encoding='ascii')
    shutil.copy2(HERE/'fixed_image_main.c',app/'main.c')
    path=app/'vdma_api/vdma_api.c'
    text=path.read_bytes()
    anchor=b'vdma_context->ReadCfg.EnableSync = 1;'
    if text.count(anchor)==1:
        path.write_bytes(text.replace(anchor,b'vdma_context->ReadCfg.EnableSync = 0;'))
    else:assert text.count(b'vdma_context->ReadCfg.EnableSync = 0;')==1
    shutil.copy2(CAMERA/'vitis_ws/digit_app/Debug/Xilinx.spec',app/'Xilinx.spec')
    objdir=ROOT/'obj';objdir.mkdir(exist_ok=True)
    objects=[]
    common=['-mcpu=cortex-a9','-mfpu=vfpv3','-mfloat-abi=hard']
    with (ROOT/'build_app.log').open('w',encoding='utf-8') as log:
        for source in app.rglob('*.c'):
            obj=objdir/(source.relative_to(app).as_posix().replace('/','_')+'.o')
            cmd=[str(TOOL/'arm-none-eabi-gcc.exe'),*common,'-Wall','-Wextra','-O2','-g','-c',
                 '-I'+str(BSP/'bspinclude/include'),'-I'+str(app),str(source),'-o',str(obj)]
            subprocess.run(cmd,check=True,stdout=log,stderr=subprocess.STDOUT);objects.append(str(obj))
        cmd=[str(TOOL/'arm-none-eabi-gcc.exe'),*common,'-Wl,-build-id=none','-specs='+str(app/'Xilinx.spec'),
             '-Wl,-T,'+str(app/'lscript.ld'),'-L'+str(BSP/'bsplib/lib'),'-o',str(ROOT/'image_test.elf'),
             *objects,'-Wl,--start-group','-lxil','-lgcc','-lc','-Wl,--end-group']
        subprocess.run(cmd,check=True,stdout=log,stderr=subprocess.STDOUT)
    elf=(ROOT/'image_test.elf').read_bytes()
    assert b'IMAGE_TEST_READY no_camera no_s2mm' in elf
    entry,phoff=struct.unpack_from('<II',elf,24);phsize,phnum=struct.unpack_from('<HH',elf,42)
    regions=[]
    for i in range(phnum):
        kind,_,_,paddr,_,memsz,_,_=struct.unpack_from('<8I',elf,phoff+i*phsize)
        if kind==1 and memsz:
            assert 0x100000<=paddr<paddr+memsz<0x02000000
            regions.append([hex(paddr),hex(paddr+memsz)])
    status=dict(stage='ARM_BUILT_NOT_DOWNLOADED',same_fpga_bitstream=True,camera_initialized=False,
        s2mm_started=False,genlock_disabled=True,frame_bytes=1152000,
        slots=[hex(0x02000000),hex(0x02000000+1152000)],mailbox=hex(0x03000000),elf_regions=regions,
        elf_sha256=hashlib.sha256(elf).hexdigest(),entry=hex(entry),sd_written=False)
    (ROOT/'app_build_status.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
    for name in ('start_fixed_image.tcl','run_fixed_image.tcl'):
        shutil.copy2(HERE/name,ROOT/name)
    (ROOT/'board').mkdir(exist_ok=True)
    candidate=Path('E:/FPGA_Enhance_Work/camera_nn_digit_candidate_20261023')
    for name in ('system_wrapper.bit','camera_digit.xsa','ps7_init.tcl'):
        shutil.copy2(candidate/name,ROOT/'board'/name)
    print('FIXED_IMAGE_ARM_BUILD_PASS',json.dumps(status),flush=True)

if __name__=='__main__':main()
