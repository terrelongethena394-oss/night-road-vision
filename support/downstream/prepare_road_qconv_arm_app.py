"""Prepare experimental ARM app sources, then compile only against the exported real driver."""
from pathlib import Path
import hashlib,json,shutil,struct,subprocess
ROOT=Path('E:/FPGA_Enhance_Work/road_qconv_app_20261027')
QAT=Path('E:/FPGA_Enhance_Work/road_realtime_20261027')
NN=Path('E:/FPGA_Enhance_Work/road_arm_prototype_20261026')
HERE=Path(__file__).resolve().parent
BSP=Path('E:/FPGA_Enhance_Work/multinex_static_20261025/vitis_ws/static_platform/export/static_platform/sw/static_platform/standalone_domain')
TOOLS=Path('E:/Xilinx/Vitis/2020.2/gnu/aarch32/nt/gcc-arm-none-eabi/bin')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def fnv(data):
    h=2166136261
    for v in data:h=((h^v)*16777619)&0xffffffff
    return h
def prepare():
    assert (ROOT/'host_complete.json').exists();src=ROOT/'source';evidence=ROOT/'evidence';evidence.mkdir(exist_ok=False)
    shutil.copy2(ROOT/'host_complete.json',evidence/'host_integration_before_main_patch.json')
    s=json.loads((QAT/'selection_complete.json').read_text());quant=QAT/'exports'/f'epoch{s["selected_epoch"]}'
    (src/'road_probe_config.h').write_text('#define ROAD_EXPECTED_WEIGHT_FNV 0x%08xU\n'%fnv((quant/'qmodel.bin').read_bytes()),encoding='ascii')
    main=(src/'road_camera_main.c').read_text();main=main.replace('#include "road_fp32.h"','#include "road_fp32.h"\n#include "road_qconv_arm.h"',1)
    assert 'm[M_VERSION]=10;' in main
    main=main.replace('m[M_VERSION]=10;','m[M_VERSION]=12;((volatile uint32_t *)RC_MAIL)[72]=1U;')
    main=main.replace('m[M_WEIGHT_READY]=0x57475453U;','if(qhw_prepare((const unsigned char *)RC_WEIGHT))fatal(30);\n    m[M_WEIGHT_READY]=0x57475453U;')
    main=main.replace('n0=now();if(road_forward','qhw_begin();n0=now();if(road_forward')
    main=main.replace('ROAD_CAMERA_READY V10','ROAD_QCONV_EXPERIMENTAL_READY V12')
    main=main.replace('infer(injected);','/* Do not count repeated inference on the same live snapshot as new frames. */\n   if(!injected&&has_result&&live_id==result_id){usleep(1000);continue;}\n   infer(injected);')
    main=add_live_counters(main)
    (src/'road_camera_main.c').write_text(main,encoding='ascii')
    # Keep timing comparable with the existing preview period (150ms).
    draw=(src/'road_camera_draw.c').read_text();draw=draw.replace('FP32','Q8 EXP').replace('BOXES APPLY TO RIGHT IMAGE ONLY','EXPERIMENTAL / BOXES APPLY TO RIGHT IMAGE ONLY');(src/'road_camera_draw.c').write_text(draw,encoding='ascii')
    (ROOT/'arm_prepared.json').write_text(json.dumps(dict(status='EXPERIMENTAL_ARM_SOURCE_READY_NO_HARDWARE_ACCESS',quant_folder=str(quant),model_sha256=sha(quant/'qmodel.bin'),model_fnv32=fnv((quant/'qmodel.bin').read_bytes()),mailbox_version=12,trace_bytes=sum(t['elements']*(4 if t['id'] in [83,84,85] else 1) for t in json.loads((NN/'graph.json').read_text())['tensors']),fresh_accuracy_gate_passed=False,default_promotion_allowed=False,hardware_access=False),indent=2),encoding='utf-8')
    print('ROAD_QCONV_ARM_SOURCE_PREPARED_EXPERIMENT_ONLY',flush=True)
def add_live_counters(main):
    needle='present(0);m[M_STATE]=injected?5:1;barrier();'
    replacement='''present(0);
 if(!injected&&!paused_flag){
  volatile uint32_t *v=(volatile uint32_t *)RC_MAIL;XTime done=now();
  if(!v[80]){v[81]=(uint32_t)done;v[82]=(uint32_t)(done>>32);v[85]=source_id;}
  v[80]++;v[83]=(uint32_t)done;v[84]=(uint32_t)(done>>32);v[86]=source_id;v[87]=ms(done-input_ticks);
 }
 m[M_STATE]=injected?5:1;barrier();'''
    assert main.count(needle)==1
    return main.replace(needle,replacement)

def compile_arm(board,ip):
    board=Path(board) if board else None;ip=Path(ip);src=ROOT/'source'
    if board:assert (board/'offline_complete.json').exists()
    driver=ip/'drivers/road_qconv_v1_0/src/xroad_qconv_hw.h';assert driver.exists();shutil.copy2(driver,src/driver.name)
    if board:
        for a,b in [('road_qconv.bit','display.bit'),('road_qconv.xsa','display.xsa'),('ps7_init.tcl','ps7_init.tcl')]:shutil.copy2(board/a,ROOT/b)
    shutil.copy2('E:/FPGA_Enhance_Work/road_camera_20261027/Xilinx.spec',ROOT/'Xilinx.spec')
    tag='arm' if board else 'arm_sourcecheck';obj=ROOT/('obj' if board else 'obj_sourcecheck');obj.mkdir(exist_ok=False);commands=[];objects=[];logs=[]
    flags=['-mcpu=cortex-a9','-mfpu=neon-vfpv3','-mfloat-abi=hard','-O3','-std=c99','-ffp-contract=off','-fno-fast-math','-fno-common','-Wall','-g','-fstack-usage','-I'+str(src),'-I'+str(BSP/'bspinclude/include')]
    files=[src/n for n in ['road_fp32.c','road_qconv_arm.c','road_qconv_pack.c','road_camera_main.c','road_camera_io.c','road_camera_draw.c','road_camera_average.c']]+[p for d in ['display_ctrl','clk_wiz','vdma_api','emio_sccb_cfg','ov5640'] for p in sorted((src/d).glob('*.c'))]
    def run(cmd):
        commands.append(list(map(str,cmd)));p=subprocess.run(commands[-1],capture_output=True,text=True);logs.append(p.stdout+p.stderr);(ROOT/(tag+'_build.log')).write_text('\n'.join(logs));assert p.returncode==0,p.stderr
    for p in files:
        target=obj/('_'.join(p.relative_to(src).parts)+'.o');strict=['-Wextra','-Werror'] if p.parent==src else []
        run([TOOLS/'arm-none-eabi-gcc.exe',*flags,*strict,'-c',p,'-o',target]);objects.append(target)
    elf=ROOT/('road_qconv.elf' if board else 'road_qconv_sourcecheck.elf')
    run([TOOLS/'arm-none-eabi-gcc.exe',*flags[:3],'-Wl,-build-id=none','-specs='+str(ROOT/'Xilinx.spec'),'-Wl,-T,'+str(src/'lscript.ld'),'-Wl,-Map,'+str(ROOT/'road_qconv.map'),'-L'+str(BSP/'bsplib/lib'),'-o',elf,*objects,'-Wl,--start-group','-lxil','-lgcc','-lc','-lm','-Wl,--end-group'])
    raw=elf.read_bytes();phoff=struct.unpack_from('<I',raw,28)[0];ent,n=struct.unpack_from('<HH',raw,42);loads=[]
    for i in range(n):
        kind,off,va,pa,fs,mem,fl,al=struct.unpack_from('<8I',raw,phoff+i*ent)
        if kind==1 and mem:assert 0x100000<=pa<pa+mem<=0x1000000;loads.append([pa,pa+mem])
    old=json.loads(Path('E:/FPGA_Enhance_Work/road_camera_20261027/offline_complete.json').read_text())['memory']
    regions=[tuple(v) for v in old]+[('qpacked',0x18000000,1764864),('qmetadata',0x18800000,int((src/'road_qconv_layout.h').read_text().split('#define QCONV_METADATA_BYTES ')[1].split('U')[0])),('raw_heads',0x19000000,65536*16)]
    for i,(name,a,n) in enumerate(regions):
        assert a+n<=0x40000000
        for name2,b,m in regions[:i]:assert a+n<=b or b+m<=a,(name,name2)
        for b,e in loads:assert a+n<=b or e<=a
    proof=dict(status='Q8_EXPERIMENTAL_ARM_COMPILED_NOT_BOARD_RUN' if board else 'ARM_SOURCE_COMPILES_WITH_REAL_IP_DRIVER_BOARD_BUILD_STILL_PENDING',elf_sha256=sha(elf),bit_sha256=sha(ROOT/'display.bit') if board else None,commands=commands,source_sha256={str(p.relative_to(src)):sha(p) for p in src.rglob('*') if p.is_file()},regions=regions,elf_loads=loads,all60_convs_in_fpga_mode=True,accuracy_gate_passed=False,default_promotion_allowed=False,hardware_access=False,sd_written=False)
    (ROOT/(tag+'_complete.json')).write_text(json.dumps(proof,indent=2),encoding='utf-8');print('ROAD_QCONV_ARM_COMPILED_EXPERIMENT_ONLY',tag,flush=True)
if __name__=='__main__':prepare()
