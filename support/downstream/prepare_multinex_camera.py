"""Separate camera application on unchanged, board-verified r4d hardware/BSP."""
from pathlib import Path
import hashlib,json,shutil,subprocess,struct,sys
ROOT=Path('E:/FPGA_Enhance_Work/multinex_camera_20261026')
BASE=ROOT.parent
OLD=BASE/'multinex_fast_static_r4d_20261026'
HERE=Path(__file__).resolve().parent
PLATFORM=BASE/'multinex_static_20261025/vitis_ws/static_platform/export/static_platform/sw/static_platform/standalone_domain'
CAM=BASE/'camera_lcd_20261017/vitis_ws/camera_app/src'
GCC=Path('E:/Xilinx/Vitis/2020.2/gnu/aarch32/nt/gcc-arm-none-eabi/bin/arm-none-eabi-gcc.exe')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    global ROOT
    upgrade=len(sys.argv)>1 and sys.argv[1]=='recognition_upgrade'
    recognition=upgrade or len(sys.argv)>1 and sys.argv[1] in ('recognition','recognition_fast')
    protected=upgrade or len(sys.argv)>1 and sys.argv[1] in ('protected','protected_fast','recognition','recognition_fast')
    cached=upgrade or len(sys.argv)>1 and sys.argv[1] in ('cached','protected','protected_fast','recognition','recognition_fast')
    if upgrade:ROOT=BASE/'multinex_camera_digit_upgrade_20261026'
    elif len(sys.argv)>1 and sys.argv[1]=='recognition_fast':ROOT=BASE/'multinex_camera_digit_fast_20261026'
    elif recognition:ROOT=BASE/'multinex_camera_digit_20261026'
    elif len(sys.argv)>1 and sys.argv[1]=='protected_fast':ROOT=BASE/'multinex_camera_protected_fast_20261026'
    elif protected:ROOT=BASE/'multinex_camera_protected_20261026'
    elif cached:ROOT=BASE/'multinex_camera_cached_20261026'
    assert not (ROOT/'camera.elf').exists(),'Preserve existing camera candidate'
    state=json.loads((OLD/'board_deployed.json').read_text(encoding='utf-8'))
    assert state['status']=='DEPLOYED_FASTER_STATIC_IMAGE_BOARD_VERIFIED'
    assert sha(OLD/'multinex_static.bit')==state['bit_sha256']
    ROOT.mkdir(exist_ok=True);src=ROOT/'app_src';src.mkdir(exist_ok=True)
    if protected:
        policy=BASE/'camera_quality_mean_20261026/complete.json'
        q=json.loads(policy.read_text());assert q['accepted'] and q['selected']['percentile']==0
        assert q['selected']['dark']==32 and q['selected']['normal']==48
        shutil.copy2(policy,ROOT/'quality_policy.json')
    for name in ('display_ctrl','vdma_api','clk_wiz'):
        shutil.copytree(OLD/'app_src'/name,src/name,dirs_exist_ok=True)
    for name in ('ov5640','emio_sccb_cfg'):
        shutil.copytree(CAM/name,src/name,dirs_exist_ok=True)
    shutil.copy2(HERE/'multinex_camera_main.c',src/'main.c')
    if recognition:
        if upgrade:
            selected=json.loads((BASE/'recognition_upgrade_20261026/deployment_candidate.json').read_text())
            reference=Path(selected['native']);frozen=json.loads(Path(selected['freeze']).read_text())
            accepted=json.loads(Path(selected['heldout_results']).read_text())
            assert accepted['accepted'] and accepted['model_sha256']==frozen['sha256']==sha(Path(frozen['model']))
        else:reference=BASE/('digit_arm_reference_i32_20261026' if sys.argv[1]=='recognition_fast' else 'digit_arm_reference_20261026')
        proof=json.loads((reference/'complete.json').read_text())
        assert proof['status']=='NATIVE_C_NUMPY_ALL_LOGITS_EXACT'
        assert sha(reference/'cnn_weights.h')==proof['weights_header_sha256']
        assert sha(reference/'digit_arm_kernel.h' if upgrade else HERE/'digit_arm_kernel.h')==proof['kernel_sha256']
        for p in (reference/'cnn_weights.h',reference/'digit_arm_kernel.h' if upgrade else HERE/'digit_arm_kernel.h',HERE/'digit_camera_adapter.h'):shutil.copy2(p,src/p.name)
        if upgrade:
            assert proof['model_sha256']==frozen['sha256']
            norm=json.loads((BASE/'recognition_upgrade_20261026/normalization_proof/complete.json').read_text())
            assert norm['status']=='C_NUMPY_NORMALIZATION_EXACT' and norm['header_sha256']==sha(HERE/'digit_normalization.h')
            shutil.copy2(HERE/'digit_normalization.h',src/'digit_normalization.h')
            adapter=(src/'digit_camera_adapter.h').read_text()
            needle='gray[y*28U+x]=(u8)((sum+count/2U)/count);\n }\n}'
            assert adapter.count(needle)==1
            adapter='#include "digit_normalization.h"\n'+adapter.replace(needle,needle[:-1]+' digit_normalize(gray);\n}')
            adapter=adapter.replace('mail[M_D_VERSION]=1;','mail[M_D_VERSION]=2;')
            (src/'digit_camera_adapter.h').write_text(adapter,encoding='ascii')
            shutil.copy2(BASE/'recognition_upgrade_20261026/deployment_candidate.json',ROOT/'classifier_candidate.json')
            shutil.copy2(Path(selected['heldout_results']),ROOT/'classifier_heldout_results.json')
            shutil.copy2(Path(selected['freeze']),ROOT/'classifier_frozen.json')
            shutil.copy2(Path(frozen['model']),ROOT/'classifier.pth')
            shutil.copy2(reference/'integer_weights.npz',ROOT/'classifier_integer_weights.npz')
            shutil.copy2(BASE/'recognition_upgrade_20261026/training_protocol.json',ROOT/'classifier_training_protocol.json')
            shutil.copy2(BASE/'recognition_upgrade_20261026/chars74k_sources.json',ROOT/'classifier_data_sources.json')
            shutil.copy2(BASE/'recognition_upgrade_20261026/split_audit.json',ROOT/'classifier_split_audit.json')
            shutil.copy2(BASE/'recognition_upgrade_20261026/normalization_proof/complete.json',ROOT/'classifier_normalization_proof.json')
            revision=Path(frozen['model']).parent/'training_revision.json'
            if revision.exists():shutil.copy2(revision,ROOT/'classifier_training_revision.json')
            shutil.copy2(BASE/'recognition_upgrade_20261026/run02/test/results.json',ROOT/'classifier_prior_rejected.json')
        shutil.copy2(reference/'complete.json',ROOT/'classifier_numeric_proof.json')
    for name in ('lscript.ld','xmultinex_hls_hw.h'):shutil.copy2(OLD/'app_src'/name,src/name)
    for old,new in [('multinex_static.bit','camera.bit'),('multinex_static.xsa','camera.xsa'),('ps7_init.tcl','ps7_init.tcl')]:
        shutil.copy2(OLD/old,ROOT/new)
    for n in ('LICENSE','NOTICE','MODEL_CARD.md','THIRD_PARTY_NOTICES.md'):shutil.copy2(OLD/n,ROOT/n)
    flags=['-mcpu=cortex-a9','-mfpu=vfpv3','-mfloat-abi=hard','-O2','-g','-fno-common','-Wall',
           '-DUSE_DDR_CACHE='+str(int(cached)),'-DNORMAL_PROTECTION='+str(int(protected)),'-DDIGIT_RECOGNITION='+str(int(recognition)),
           '-I'+str(PLATFORM/'bspinclude/include'),'-I'+str(src)]
    objects=[];commands=[];log=[]
    obj=ROOT/'obj';obj.mkdir(exist_ok=True)
    for p in sorted(src.rglob('*.c')):
        out=obj/('_'.join(p.relative_to(src).parts)+'.o')
        cmd=[str(GCC),*flags,*(['-Wextra','-Werror'] if p.name=='main.c' else []),'-c',str(p),'-o',str(out)]
        run=subprocess.run(cmd,capture_output=True,text=True,errors='replace');commands.append(cmd);log.append(run.stdout+run.stderr)
        if run.returncode:
            (ROOT/'build.log').write_text('\n'.join(log),encoding='utf-8');raise RuntimeError(log[-1])
        objects.append(str(out))
    specs=BASE/'multinex_static_20261025/vitis_ws/static_app/Debug/Xilinx.spec'
    shutil.copy2(specs,ROOT/'Xilinx.spec')
    cmd=[str(GCC),*flags[:3],'-Wl,-build-id=none','-specs='+str(ROOT/'Xilinx.spec'),'-Wl,-T,'+str(src/'lscript.ld'),
         '-L'+str(PLATFORM/'bsplib/lib'),'-o',str(ROOT/'camera.elf'),*objects,
         '-Wl,--start-group','-lxil','-lgcc','-lc','-Wl,--end-group']
    run=subprocess.run(cmd,capture_output=True,text=True,errors='replace');commands.append(cmd);log.append(run.stdout+run.stderr)
    (ROOT/'build.log').write_text('\n'.join(log),encoding='utf-8');assert run.returncode==0,log[-1]
    elf=(ROOT/'camera.elf').read_bytes();assert elf[:5]==b'\x7fELF\x01'
    phoff=struct.unpack_from('<I',elf,28)[0];ent,num=struct.unpack_from('<HH',elf,42);regions=[]
    for i in range(num):
        kind,off,va,pa,sz,ms,fl,al=struct.unpack_from('<8I',elf,phoff+i*ent)
        if kind==1 and ms:
            assert 0x100000<=pa<pa+ms<=0x1000000;regions.append([pa,pa+ms])
    memory=dict(lcd=[0x02000000,0x02000000+3*800*480*3],mailbox=[0x03000000,0x03001000],
        input=[0x04000000,0x04000000+400*240*4],output=[0x04200000,0x04200000+400*240*4],
        scratch=[0x04400000,0x04400000+400*240*16],diagnostics=[0x04b00000,0x04b00060],
        capture=[0x06000000,0x06000000+3*800*480*3])
    if protected:memory['protected_output']=[0x04c00000,0x04c00000+400*240*4]
    if recognition:memory['digit_diagnostics']=[0x04e00000,0x04e02000]
    ordered=sorted(memory.values());assert all(a[1]<=b[0] for a,b in zip(ordered,ordered[1:]))
    assert sha(ROOT/'camera.bit')==state['bit_sha256']
    for n in ('start_multinex_camera.tcl','snapshot_multinex_camera.tcl','validate_multinex_camera.py'):
        shutil.copy2(HERE/n,ROOT/n)
    result=dict(status='CAMERA_ARM_COMPILED_NOT_BOARD_VERIFIED',bit_sha256=sha(ROOT/'camera.bit'),
        elf_sha256=sha(ROOT/'camera.elf'),xsa_sha256=sha(ROOT/'camera.xsa'),ps_init_sha256=sha(ROOT/'ps7_init.tcl'),
        commands=commands,elf_regions=regions,memory=memory,camera_shape=[480,800],enhancement_shape=[240,400],
        capture='Separate parked buffers; switch writer, copy completed old frame with 2x2 RGB averaging.',
        cache='Mailbox noncacheable; cache enabled; capture/output invalidated, input/LCD flushed at ownership transitions.' if cached else 'D-cache disabled; volatile capture read, barriers before PL start.',sd_written=False,
        normal_protection=protected,recognition=recognition,
        warning='No measured camera throughput or image correctness yet. Same bit/PS/BSP as verified static candidate, only ARM program changes.')
    if upgrade:result['classifier_input_contract']=2
    (ROOT/'offline_camera.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('CAMERA_ARM_COMPILED',len(elf),regions,flush=True)
if __name__=='__main__':main()
