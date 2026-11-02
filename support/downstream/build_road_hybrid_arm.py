"""Cross-compile full-network ARM+PL candidate after all R2 physical shape gates pass."""
from pathlib import Path
import hashlib,importlib.util,json,re,shutil,struct,subprocess
ROOT=Path('E:/FPGA_Enhance_Work/road_hybrid_20261027_r1')
BOARD=Path('E:/FPGA_Enhance_Work/road_conv_burst_board_20261027')
CAM=Path('E:/FPGA_Enhance_Work/road_camera_20261027')
HERE=Path(__file__).resolve().parent
BSP=Path('E:/FPGA_Enhance_Work/multinex_static_20261025/vitis_ws/static_platform/export/static_platform/sw/static_platform/standalone_domain')
TOOLS=Path('E:/Xilinx/Vitis/2020.2/gnu/aarch32/nt/gcc-arm-none-eabi/bin')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    physical=json.loads((BOARD/'physical_readback_r2_retry1/validated.json').read_text());assert len(physical['results'])==15
    fixtures=json.loads((BOARD/'future_board_test/fixtures.json').read_text());shapes={}
    for r in physical['results']:
        assert r['byte_exact_cpu'] and r['byte_exact_pl']
        if r['name'].startswith('real_'):
            f=next(c for c in fixtures if c['name']==r['name']);shape=tuple(f[k] for k in ['h','w','ic4','oc4','stride'])
            shapes[shape]=dict(selected=r['single_layer_speedup']>1.10,measurement=r)
    assert len(shapes)==10
    g=json.loads(Path('E:/FPGA_Enhance_Work/road_arm_prototype_20261026/graph.json').read_text());selected=[];policy=[]
    for t in g['tensors'][1:]:
        if t['kind']!=1 or t['k']!=3:continue
        inp=g['tensors'][t['inputs'][0]];shape=(inp['h'],inp['w'],inp['c4'],t['c4'],t['s']);entry=shapes[shape]
        if entry['selected']:selected.append(t['id'])
        policy.append(dict(node=t['id'],shape=shape,selected=entry['selected'],shape_speedup=entry['measurement']['single_layer_speedup']))
    assert selected
    evidence=ROOT/'evidence';evidence.mkdir(exist_ok=False)
    shutil.copy2(ROOT/'source/road_pl_layout.h',evidence/'host_all17_layout.h')
    spec=importlib.util.spec_from_file_location('prep',HERE/'prepare_road_hybrid.py');prep=importlib.util.module_from_spec(spec);spec.loader.exec_module(prep)
    (ROOT/'source/road_pl_layout.h').write_text(prep.layout_header(set(selected)),encoding='ascii')
    src=ROOT/'source';main=(src/'road_camera_main.c').read_text()
    main=main.replace('#include "road_fp32.h"','#include "road_fp32.h"\n#include "road_pl.h"',1)
    main=main.replace('m[M_VERSION]=10;','m[M_VERSION]=11;((volatile uint32_t *)RC_MAIL)[72]=1U;')
    main=main.replace('m[M_WEIGHT_READY]=0x57475453U;','if(road_pl_prepare((const float *)RC_WEIGHT))fatal(30);\n    m[M_WEIGHT_READY]=0x57475453U;')
    main=main.replace('n0=now();if(road_forward','road_pl_begin();n0=now();if(road_forward')
    main=main.replace('ROAD_CAMERA_READY V10','ROAD_HYBRID_CAMERA_READY V11');(src/'road_camera_main.c').write_text(main,encoding='ascii')
    driver=Path('E:/FPGA_Enhance_Work/road_conv_burst_hls_20261027/conv_project/solution_100mhz/impl/ip/drivers/road_conv3_fp32_v1_0/src/xroad_conv3_fp32_hw.h');shutil.copy2(driver,src/driver.name)
    for before,after in [('road_conv.bit','display.bit'),('road_conv.xsa','display.xsa'),('future_board_test/ps7_init.tcl','ps7_init.tcl')]:shutil.copy2(BOARD/before,ROOT/after)
    shutil.copy2(CAM/'Xilinx.spec',ROOT/'Xilinx.spec')
    obj=ROOT/'obj';obj.mkdir(exist_ok=False);objects=[];commands=[];logs=[]
    flags=['-mcpu=cortex-a9','-mfpu=neon-vfpv3','-mfloat-abi=hard','-O3','-std=c99','-ffp-contract=off','-fno-fast-math','-fno-common','-Wall','-g','-fstack-usage','-I'+str(src),'-I'+str(BSP/'bspinclude/include')]
    files=[src/n for n in ['road_fp32.c','road_pl.c','road_conv3_pack.c','road_camera_main.c','road_camera_io.c','road_camera_draw.c','road_camera_average.c']]+[p for d in ['display_ctrl','clk_wiz','vdma_api','emio_sccb_cfg','ov5640'] for p in sorted((src/d).glob('*.c'))]
    def run(cmd):
        commands.append(list(map(str,cmd)));p=subprocess.run(commands[-1],capture_output=True,text=True);logs.append(p.stdout+p.stderr);(ROOT/'arm_build.log').write_text('\n'.join(logs));assert p.returncode==0,p.stderr
    for p in files:
        target=obj/('_'.join(p.relative_to(src).parts)+'.o');strict=['-Wextra','-Werror'] if p.parent==src else []
        run([TOOLS/'arm-none-eabi-gcc.exe',*flags,*strict,'-c',p,'-o',target]);objects.append(target)
    elf=ROOT/'road_hybrid.elf'
    run([TOOLS/'arm-none-eabi-gcc.exe',*flags[:3],'-Wl,-build-id=none','-specs='+str(ROOT/'Xilinx.spec'),'-Wl,-T,'+str(src/'lscript.ld'),'-Wl,-Map,'+str(ROOT/'road_hybrid.map'),'-L'+str(BSP/'bsplib/lib'),'-o',elf,*objects,'-Wl,--start-group','-lxil','-lgcc','-lc','-lm','-Wl,--end-group'])
    raw=elf.read_bytes();phoff=struct.unpack_from('<I',raw,28)[0];ent,n=struct.unpack_from('<HH',raw,42);loads=[]
    for i in range(n):
        kind,off,va,pa,fs,mem,fl,al=struct.unpack_from('<8I',raw,phoff+i*ent)
        if kind==1 and mem:assert 0x100000<=pa<pa+mem<=0x1000000;loads.append([pa,pa+mem])
    previous=json.loads((CAM/'offline_complete.json').read_text())['memory'];regions=[tuple(r) for r in previous]+[('packed_conv_weights',0x18000000,4346176)]
    for i,(name,a,n) in enumerate(regions):
        assert a+n<=0x40000000
        for name2,b,m in regions[:i]:assert a+n<=b or b+m<=a,(name,name2)
        for b,e in loads:assert a+n<=b or e<=a
    proof=dict(status='FULL_NETWORK_OFFLOAD_CANDIDATE_COMPILED_NOT_BOARD_TESTED',selected_layers=selected,selection='R2 same-shape single-layer median speedup >1.10; provisional until end-to-end camera test',policy=policy,elf_sha256=sha(elf),bit_sha256=sha(ROOT/'display.bit'),source_sha256={str(p.relative_to(src)):sha(p) for p in src.rglob('*') if p.is_file()},commands=commands,regions=regions,elf_loads=loads,mailbox_version=11,mode_mailbox_address=0x13800120,mode0='CPU only',mode1='provisional measured selected layers',mode2='all17 for diagnostic only',calls_address=0x13800124,error_address=0x13800128,packed_ready_address=0x13800134,weights_path='E:/FPGA_Enhance_Work/road_arm_prototype_20261026/weights.f32',hardware_access=False,sd_written=False)
    (ROOT/'arm_complete.json').write_text(json.dumps(proof,indent=2),encoding='utf-8');print('ROAD_HYBRID_ARM_COMPILED_SELECTED',selected,flush=True)
if __name__=='__main__':main()
