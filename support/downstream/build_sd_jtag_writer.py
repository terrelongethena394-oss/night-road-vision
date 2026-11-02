from pathlib import Path
import json,shutil,subprocess,hashlib,zlib
HERE=Path(__file__).resolve().parent
BASE=Path('E:/FPGA_Enhance_Work')
OUT=BASE/'plate_sd_20261026/jtag_writer'
BSP=BASE/'camera_nn_sd_20261018/vitis_ws/nn_sd_platform/export/nn_sd_platform/sw/nn_sd_platform/standalone_domain'
GCC=Path('E:/Xilinx/Vitis/2020.2/gnu/aarch32/nt/gcc-arm-none-eabi/bin/arm-none-eabi-gcc.exe')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    OUT.mkdir(exist_ok=False)
    for p in [HERE/'sd_jtag_writer.c',BASE/'camera_plate_guarded_20261026/app_src/lscript.ld',BASE/'camera_plate_guarded_20261026/Xilinx.spec']:
        shutil.copy2(p,OUT/p.name)
    cmd=[str(GCC),'-mcpu=cortex-a9','-mfpu=vfpv3','-mfloat-abi=hard','-O2','-g','-Wall','-Wextra','-Werror',
         '-I'+str(BSP/'bspinclude/include'),'-L'+str(BSP/'bsplib/lib'),'-specs='+str(OUT/'Xilinx.spec'),
         '-Wl,-T,'+str(OUT/'lscript.ld'),str(OUT/'sd_jtag_writer.c'),'-o',str(OUT/'sd_jtag_writer.elf'),
         '-Wl,--start-group','-lxilffs','-lxil','-lgcc','-lc','-Wl,--end-group']
    p=subprocess.run(cmd,capture_output=True,text=True);(OUT/'build.log').write_text(p.stdout+p.stderr)
    assert p.returncode==0,p.stdout+p.stderr
    data=(OUT.parent/'BOOT.BIN').read_bytes()
    metadata=dict(status='COMPILED_NOT_YET_RUN',elf_sha256=sha(OUT/'sd_jtag_writer.elf'),boot_sha256=sha(OUT.parent/'BOOT.BIN'),boot_bytes=len(data),boot_crc32=zlib.crc32(data),commands=cmd,
                  upload=0x10000000,readback=0x12000000,old_backup=0x14000000,limit=16*1024*1024,mailbox=0x03000000)
    (OUT/'writer.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    (OUT/'boot_transfer.tcl').write_text(f'set boot_bytes {len(data)}\nset boot_crc {zlib.crc32(data)}\n',encoding='ascii')
    print('SD_JTAG_WRITER_COMPILED',metadata['elf_sha256'],flush=True)
if __name__=='__main__':main()
