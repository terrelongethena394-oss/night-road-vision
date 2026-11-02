"""Freeze verified running hybrid version, write handoff, and create a checked archive."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys,zipfile
ROOT=Path('E:/FPGA_Enhance_Work/road_hybrid_20261027_r1')
BOARD=Path('E:/FPGA_Enhance_Work/road_conv_burst_board_20261027')
HLS=Path('E:/FPGA_Enhance_Work/road_conv_burst_hls_20261027')
NN=Path('E:/FPGA_Enhance_Work/road_arm_prototype_20261026')
CAM=Path('E:/FPGA_Enhance_Work/road_camera_20261027')
HERE=Path(__file__).resolve().parent
WORKSPACE=HERE.parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):Path(p).write_text(json.dumps(d,indent=2,ensure_ascii=False),encoding='utf-8')
def main():
    live=json.loads((ROOT/'live_session_r1.json').read_text());assert live['status']=='HYBRID_CAMERA_LIVE_VALIDATED_AND_LEFT_RUNNING'
    full=json.loads((ROOT/'physical_full_r1/validated.json').read_text());assert full['performance_gate_passed']
    original=json.loads((ROOT/'original_elf_same_bit/validated.json').read_text());assert original['output_bytes_exact']
    proof=json.loads((ROOT/'arm_complete.json').read_text());assert sha(ROOT/'road_hybrid.elf')==proof['elf_sha256']==live['elf_sha256']
    assert sha(ROOT/'display.bit')==proof['bit_sha256']==live['bit_sha256']
    write(ROOT/'user_visual_confirmation.json',dict(status='USER_CONFIRMED_CURRENT_HYBRID_DISPLAY',answer='左右更新正常，颜色正常',question='左侧是否持续更新、颜色正常，右侧是否仍隔几秒更新检测快照',source='Direct user reply in this chat',sd_written=False))
    # The user restart entry uses the already-validated initialization sequence,
    # without the one-time packet collection that would overwrite old evidence.
    start=(CAM/'start_camera_live.tcl').read_text().replace('==10','==11').replace('$root/road_camera.elf','$root/road_hybrid.elf').replace('ROAD_CAMERA_LIVE_READY','ROAD_HYBRID_CAMERA_LIVE_READY')
    start=start.replace('mwr 0x1380000c 3','mwr 0x13800120 1\n mwr 0x1380000c 3')
    (ROOT/'start_hybrid_camera_only.tcl').write_text(start,encoding='ascii')
    shutil.copy2(CAM/'verify_runtime.py',ROOT/'verify_runtime.py')
    launcher='''from pathlib import Path
import argparse,json,hashlib,subprocess,sys
p=argparse.ArgumentParser();p.add_argument('--verify-only',action='store_true');args=p.parse_args()
root=Path(__file__).resolve().parent
for name,digest in json.loads((root/'runtime_checksums.json').read_text()).items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,name
print('ROAD_HYBRID_RUNTIME_HASHES_PASS',flush=True)
if not args.verify_only:
    result=subprocess.run(['E:/Xilinx/Vitis/2020.2/bin/xsct.bat',str(root/'start_hybrid_camera_only.tcl')],capture_output=True,text=True)
    print(result.stdout+result.stderr)
    (root/'last_start.log').write_text(result.stdout+result.stderr,encoding='utf-8')
    assert result.returncode==0 and 'ROAD_HYBRID_CAMERA_LIVE_READY' in result.stdout,'Startup failed: see last_start.log'
'''
    (ROOT/'start_hybrid_ram.py').write_text(launcher,encoding='ascii')
    (ROOT/'00_start_hybrid_ram.cmd').write_text('@echo off\ncd /d "%~dp0"\n"E:\\FPGA_Enhance_Work\\nn_env312\\Scripts\\python.exe" "%~dp0start_hybrid_ram.py"\nif errorlevel 1 echo Startup failed. Check last_start.log.\npause\n',encoding='ascii')
    essentials=['road_hybrid.elf','display.bit','display.xsa','ps7_init.tcl','camera_common.tcl','start_hybrid_camera_only.tcl','start_hybrid_ram.py','verify_runtime.py','runtime/weights.f32']
    write(ROOT/'runtime_checksums.json',{n:sha(ROOT/n) for n in essentials})
    subprocess.run([sys.executable,str(ROOT/'start_hybrid_ram.py'),'--verify-only'],check=True)
    cpu=full['timing']['cpu']['median_total_seconds'];hybrid=full['timing']['hybrid']['median_total_seconds'];reduction=100*(1-hybrid/cpu)
    budget=json.loads(Path('E:/FPGA_Enhance_Work/road_conv_hls_20261027/layer_budget.json').read_text());mac=sum(r['mac'] for r in budget['layers'] if r['id'] in proof['selected_layers'])
    report=f'''# ARM + FPGA 道路检测实板验收（2026-10-27）

**当前已上板并继续运行**。用户已确认“左右更新正常，颜色正常”。SD 卡与 Flash 未写入；旧 ARM 版本、旧 bit、旧 SD 内容均保留。

## 本轮完成的功能

模型仍为原 FP32 YOLOv5n 四类道路检测器（行人、汽车、卡车、公交车），权重未重新训练。本轮将 12 个 3×3 卷积层交给 FPGA，ARM 负责其余网络算子、SiLU 激活、解码/NMS、摄像头配置和显示内容组织。PL 同时承担原来的采集、VDMA 与 LCD 输出。

实际调用层：`{', '.join(map(str,proof['selected_layers']))}`。这 12 层占卷积 MAC 的约 {100*mac/budget['total_conv_mac']:.1f}%；这是静态运算量比例，不是耗时比例，也不是整网都在 FPGA 上执行。

HLS 核心为 8 路 FP32 乘加、16 个位置交错累加，使用连续 DDR 突发读取。另 5 个收益不足的 3×3 层继续由 ARM 执行。没有使用量化或更换权重来换速度，未启用图像增强支路。

## 实测结果

| 检查 | 结果 |
|---|---|
| 单层实板 | 15 组：5 组边界/合成数据，10 组真实中间特征，覆盖 17 个 3×3 层的全部不同尺寸；CPU、FPGA、独立参考逐字节一致 |
| 整网接入主机检查 | 8 张图、每图全部 86 层、解码与 NMS 均一致；使用独立的打包权重标量模拟，不冒充硬件测试 |
| 整网实板 | 首张夜景全部 86 层与原 ARM 实板数据逐字节一致；8 张图的三个检测头、解码、检测框与原 ARM 实板数据逐字节一致 |
| 采集与显示 | 实拍源图的 2×2 平均、检测输入对应关系、完整 800×480 帧缓冲通过校验，VDMA 错误为 0；用户视觉确认通过 |
| 同一 ELF/同一 bit、同一夜景 | CPU 模式中位数 **{cpu:.3f} s**，12 层 FPGA 模式 **{hybrid:.3f} s**，处理耗时减少 **{reduction:.1f}%**，约 **{cpu/hybrid:.2f} 倍**；各 1 次预热、3 次计时 |
| 原程序独立复核 | 未修改的原摄像头 ELF 在相同新 bit 上，三次中位数 **{original['median_seconds']:.3f} s**，输出保持一致；与混合版比较约减少 {100*(1-hybrid/original['median_seconds']):.1f}%，存在运行波动，因此以上同一 ELF 模式对照作为主要结果 |
| 当前实时摄像头样本 | 预览约 **{live['preview_hz']:.2f} Hz**，检测结果约 **{live['detection_updates_hz']:.2f} Hz**，本次快照处理约 **{live['active_detection_seconds']:.2f} s**；预览帧率与检测更新率分别报告 |

计时口径：预处理 + 网络 + 解码/NMS，包含期间的协作预览服务；不含 JTAG 传输、首次权重打包、推理开始前的输入快照复制以及最终结果复制/显示提交。它不是摄像头曝光到屏幕的完整延迟。当前摄像头与固定夜景数据不同，不能把旧实时样本与本次实时样本直接用于精确加速比计算。

整网跨 Windows 主机与 ARM 的原始结果本来就存在少量浮点差异。本轮最初的主机逐字节检查因此拒绝了连 CPU 基线在内的结果。独立复核证明，新 CPU/FPGA 输出与已有 ARM 实板基线逐字节一致；跨平台仍按原先固定的 `1e-4 + 1e-4*abs(reference)` 逐层容差检查，没有修改硬件、权重或数据来迎合检查。初始失败日志与差异审计均保留。

## 硬件与文件入口

工作目录：`{ROOT.as_posix()}`。

- `00_start_hybrid_ram.cmd`：断电后的 JTAG RAM 启动入口，先核对哈希，再启动；此精简入口复用已执行验证的初始化序列，未为测试它而再次中断当前画面。
- `road_hybrid.elf` / `display.bit` / `display.xsa`：当前程序与硬件。
- `source/road_pl.c`：ARM 调度、缓存维护、FPGA 配置及 SiLU；`source/road_fp32.c`：其余网络；`source/road_pl_layout.h`：层偏移与选择策略。
- `{HLS.as_posix()}/road_conv3_hls.cpp`：HLS 卷积核心。
- `{BOARD.as_posix()}/prj/road_conv.xpr`：已完成实现的 Vivado 2020.2 工程。
- `physical_full_r1/validated.json`、`live_snapshot_01/validated.json`、`live_session_r1.json`：固定图和实际摄像头的实板证据。
- `runtime/weights.f32`：原模型权重；ELF SHA256 `{proof['elf_sha256']}`；bit SHA256 `{proof['bit_sha256']}`。

完整硬件资源：LUT 16,427 / 53,200，寄存器 25,252 / 106,400，DSP 68 / 220，BRAM36 等效块 50.5 / 140。卷积工作时钟 100 MHz；WNS +0.952 ns，WHS +0.031 ns。外部视频 I/O 仍沿用官方工程，有 13 个输入、27 个输出未指定外部延时，不宣称完成全部外部接口时序签核。

板卡保持独立供电时，可拔下载器继续运行。当前为 RAM 版，断电会丢失，需重新运行入口。SD 自启动此次没有更改。

## 结论边界与下一步

本轮证明了 FPGA 已承担实际神经网络计算，并在同图测试中减少处理耗时、保留原输出。检测仍是每几秒更新，不能当成高帧率跟踪。模型权重未变，先前的误检没有因此被证明解决，也没有证明暗光识别精度或增强画质提高。

接下来应做带标注的实际行人/车辆同场景明暗评测，统计漏检、误检和耗时，再决定训练或增强策略；通过后再处理 SD 启动和展示视频。

旧版恢复入口：`{CAM.as_posix()}/00_start_camera_ram.cmd`。源码沿用原 YOLOv5 GPL-3.0 及官方外围文件声明。归档中的重建/评测脚本保留本机 E:/ 路径，迁移电脑时需要调整工具及资料路径。
'''
    doc=WORKSPACE/'ARM与FPGA协同检测验收_20261027.md';doc.write_text(report,encoding='utf-8');(ROOT/'README_验收.md').write_text(report,encoding='utf-8')
    checkpoint=WORKSPACE/'当前运行检查点_摄像头道路检测_20261027.md';backup=WORKSPACE/'当前运行检查点_旧ARM版_20261027.md'
    if not backup.exists():shutil.copy2(checkpoint,backup)
    checkpoint.write_text(f'''# 当前运行检查点（2026-10-27）

当前运行：**ARM + FPGA 混合道路检测**，目录 `{ROOT.as_posix()}`。ELF SHA256 `{proof['elf_sha256']}`，bit SHA256 `{proof['bit_sha256']}`。

12 个 3×3 卷积层由 FPGA 计算，其余网络、SiLU、解码/NMS 和界面组织由 ARM 执行。模型权重保持原版，未启用增强。用户已确认“左右更新正常，颜色正常”。程序在实拍数据读回后已恢复连续运行。

同图、同 ELF/bit 的 CPU/FPGA 模式对照：{cpu:.3f}s → {hybrid:.3f}s，处理耗时减少约 {reduction:.1f}%。当前摄像头样本预览约 {live['preview_hz']:.2f}Hz，检测更新约 {live['detection_updates_hz']:.2f}Hz；计时口径及适用范围见验收文档。

实板首张图全部 86 层、8 张图检测头/解码/检测框与旧 ARM 数据逐字节一致。真实相机采集与完整帧缓冲通过校验，VDMA 错误为 0。跨主机浮点使用原有容差，初始严格检查失败及独立审计已保留。

此次 SD/Flash 均未写。当前为 RAM 版，断电后运行 `{ROOT.as_posix()}/00_start_hybrid_ram.cmd`。旧版恢复：`{CAM.as_posix()}/00_start_camera_ram.cmd`。

尚未完成同场景明暗标注评测；先前 CAR 误检和实时性限制仍是待解决问题，不能宣称画质/精度改善。SD 自启动未在本轮处理。当前用户已确认显示，不要无必要再次重置板卡。

详情：[ARM 与 FPGA 协同检测验收](ARM与FPGA协同检测验收_20261027.md)。
''',encoding='utf-8')
    # Evidence points to the same immutable original ARM references, all hashed.
    baseline={}
    for f in json.loads((NN/'export_complete.json').read_text())['fixtures']:
        for name in ['head0.f32','head1.f32','head2.f32','decoded.f32','boxes400.f32']:
            p=NN/'board_batch_r2'/f['name']/name;baseline[str(p)]=sha(p)
    baseline[str(CAM/'board_fixed_first/all_layers.f32')]=sha(CAM/'board_fixed_first/all_layers.f32')
    release=dict(status='PHYSICAL_HYBRID_CAMERA_VERIFIED_USER_VISUAL_CONFIRMED_LEFT_RUNNING',elf_sha256=proof['elf_sha256'],bit_sha256=proof['bit_sha256'],weights_sha256=sha(ROOT/'runtime/weights.f32'),selected_layers=proof['selected_layers'],fixed_photo_cpu_seconds=cpu,fixed_photo_hybrid_seconds=hybrid,processing_reduction_percent=reduction,original_elf_same_bit_median=original['median_seconds'],preview_hz=live['preview_hz'],detection_updates_hz=live['detection_updates_hz'],live_active_detection_seconds=live['active_detection_seconds'],source_sha256=proof['source_sha256'],original_arm_reference_sha256=baseline,sd_written=False,flash_written=False,accuracy_gain_claimed=False,current_program=str(ROOT/'road_hybrid.elf'),rollback=str(CAM/'00_start_camera_ram.cmd'))
    write(ROOT/'release.json',release)
    files={}
    def add(p,name):
        p=Path(p);assert p.is_file(),p;assert name not in files;files[name]=p
    for name in essentials+['runtime_checksums.json','00_start_hybrid_ram.cmd','release.json','README_验收.md','arm_complete.json','host_complete.json','user_visual_confirmation.json','difference_audit.json','full_session_r1.json','live_session_r1.json','live_samples_times.txt','start_hybrid_live.tcl','test_full_ram.tcl','test_context.json','validate_live_v11.py']:
        add(ROOT/name,'app/'+name)
    for p in (ROOT/'source').rglob('*'):
        if p.is_file():add(p,'app/source/'+p.relative_to(ROOT/'source').as_posix())
    scripts=['prepare_road_conv_burst.py','check_road_conv_burst.py','expand_road_conv_burst_fixtures.py','build_road_conv_burst_board.py','retry_road_burst_jtag.py','prepare_road_hybrid.py','build_road_hybrid_arm.py','prepare_road_hybrid_test.py','run_road_hybrid_full.py','audit_road_hybrid_differences.py','validate_road_hybrid.py','benchmark_original_camera_on_burst.py','install_road_hybrid_live.py','finalize_road_hybrid.py','road_pl.c','road_pl.h','road_conv3_pack.c']
    for name in scripts:add(HERE/name,'scripts/'+name)
    for name in ['road_conv3_hls.cpp','road_conv3_hls.h','tb_road_conv3.cpp','checked.json','expanded_complete.json','burst_inference.json','protocol.json','YOLOv5_LICENSE','csim.tcl','synth.tcl','cosim.tcl','export.tcl']:
        add(HLS/name,'hls/'+name)
    ip=json.loads((HLS/'checked.json').read_text());add(ip['archive'],'hls/'+Path(ip['archive']).name)
    for name in ['build_board.tcl','system_road_conv_bd.tcl','utilization.rpt','timing_summary.rpt','timing_acceptance.txt','drc.rpt','offline_complete.json']:
        add(BOARD/name,'hardware/'+name)
    add(BOARD/'physical_readback_r2_retry1/validated.json','hardware/unit_test_validated.json')
    add(BOARD/'physical_session_r2_retry1.json','hardware/unit_session.json')
    # Preserve full fixed-photo evidence. Live images remain in the local folder;
    # only live validation receipts/telemetry are duplicated in this code archive.
    for p in (ROOT/'physical_full_r1').rglob('*'):
        if p.is_file():add(p,'evidence/fixed/'+p.relative_to(ROOT/'physical_full_r1').as_posix())
    for p in (ROOT/'original_elf_same_bit').iterdir():
        if p.is_file():add(p,'evidence/original_same_bit/'+p.name)
    for name in ['validated.json','mailbox.bin','mailbox80.bin','context.txt','ui.u32','vdma_regs.bin']:
        add(ROOT/'live_snapshot_01'/name,'evidence/live/'+name)
    for j in range(3):add(ROOT/f'live_sample{j}.bin',f'evidence/live/sample{j}.bin')
    for name in ['full_test_console.log','full_pipeline.log','full_validator_final.log','difference_audit.log','live_install_console.log','live_install_pipeline.log']:
        add(ROOT/name,'evidence/logs/'+name)
    manifest={name:dict(bytes=p.stat().st_size,sha256=sha(p)) for name,p in sorted(files.items())};write(ROOT/'archive_manifest.json',manifest)
    archive=ROOT.parent/'road_hybrid_verified_20261027_r1.zip';assert not archive.exists()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,p in sorted(files.items()):z.write(p,name)
        z.write(ROOT/'archive_manifest.json','archive_manifest.json')
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name,meta in manifest.items():assert hashlib.sha256(z.read(name)).hexdigest()==meta['sha256']
    receipt=dict(status='ALL_ARCHIVE_MEMBERS_CRC_AND_SHA256_VERIFIED',archive=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),files=len(files)+1)
    write(ROOT/'archive_complete.json',receipt);print(json.dumps(receipt,indent=2),flush=True)
if __name__=='__main__':main()
