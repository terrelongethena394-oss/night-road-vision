"""Package an offline candidate while the user has paused physical board work."""
from pathlib import Path
import hashlib, json, shutil, zipfile

ROOT=Path('E:/FPGA_Enhance_Work/multinex_fast_static_r4d_20261026')
HLS=ROOT.parent/'multinex_hls_r4d_20261026'
HERE=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    accepted=json.loads((ROOT/'offline_acceptance.json').read_text(encoding='utf-8'))
    hls=json.loads((HLS/'completion.json').read_text(encoding='utf-8'))
    rtl=json.loads((HLS/'rtl_dump_audit.json').read_text())
    assert accepted['status']=='OFFLINE_ACCEPTED_FOR_VOLATILE_JTAG_TEST_NOT_BOARD_VERIFIED'
    assert rtl['status']=='ALL_CHECKED_RTL_OUTPUTS_EXACT'
    assert not (ROOT/'board_full/readback_validation.json').exists(), 'Use separate verified-release flow after board tests'
    assert sha(ROOT/'multinex_static.bit')==accepted['bit_sha256']
    assert sha(ROOT/'multinex_static.elf')==accepted['elf_sha256']
    for item in accepted['old_preserved']:assert sha(Path(item['path']))==item['sha256']
    resources=accepted['resources']
    status=dict(status='OFFLINE_CANDIDATE_READY_HARDWARE_PAUSED_BY_USER',
        hardware_paused_by_user=True,jtag_connected_in_this_stage=False,downloaded=False,sd_written=False,
        csim_cases=9,csim_pixels=627908,rtl_cases=len(rtl['cases']),rtl_pixels=rtl['pixels'],
        rtl_scratch_values=rtl['scratch_values'],resources=resources,
        setup_slack_ns=accepted['setup_slack_ns'],hold_slack_ns=accepted['hold_slack_ns'],
        bus_skew_min_slack_ns=accepted['bus_skew_min_slack_ns'],clock_mhz=100,
        bit_sha256=accepted['bit_sha256'],elf_sha256=accepted['elf_sha256'],
        parameters_sha256=hls['parameters_sha256'],
        restriction='No new board correctness or speed claim. User will turn off the board; wait for explicit return/power-on before any JTAG operation. All model weights and reference outputs unchanged.',
        remaining=['Resume only after user returns and powers board',
            'Volatile JTAG launch using start_multinex_static.tcl',
            'Run ten static-image cases and independently validate actual DDR readback',
            'Compare actual complete-frame latency with saved r3b baseline',
            'Leave real-photo RAW/ENH display, then release only if exact and faster'])
    (ROOT/'handoff_status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    doc=f'''# 新版离线完成，等待上电验证

用户已要求暂停板卡工作、准备关闭电源。本阶段没有重新连接JTAG，没有下载新版，也没有操作SD卡。只有收到用户回来并重新上电的消息后，才能开始实板步骤。

已完成同一Multinex-Nano增强模型的硬件优化：并行点卷积、通道分组行缓存、像素循环流水、空间部分和，以及宽位乘法的多级流水。权重和参考结果未改，不把它称为重新训练或识别准确率提升。模型和来源许可随包保存。

## 电脑端已通过

- C测试9例、627908像素，含真实照片和800×480，输出精确。
- 真正Verilog RTL联合仿真4例、{rtl['pixels']}像素，输出、48个均值/门控和{rtl['scratch_values']}个保留特征整数精确；另外独立解析RTL输出核对。
- 实际整机布局布线和位流生成成功；100MHz，setup余量{accepted['setup_slack_ns']:.3f}ns、hold余量{accepted['hold_slack_ns']:.3f}ns，总线偏斜最小余量{accepted['bus_skew_min_slack_ns']:.3f}ns。
- 实际整机资源：LUT {resources['Slice LUTs']:g}/53200、FF {resources['Slice Registers']:g}/106400、BRAM Tile {resources['Block RAM Tile']:g}/140、DSP {resources['DSPs']:g}/220。
- AXI控制/缓冲接口、PS初始化均与已验证基线相同，复用SHA一致的ARM程序。仍继承部分外部IO delay缺失等板级约束限制，不宣称完整外部接口签核。

## 尚未完成

新版没有实板结果，也没有实际速度数字。上一轮已验证基线800×480为3.671899秒；不能把这个旧数值或小图RTL周期当成新版速度。本候选需上板逐字节验证和整帧计时后，才决定是否替换。

新版使用静态真实照片，不运行摄像头采集或数字识别。PL负责全部整数增强网络；ARM负责缓冲、控制、计时、校验和LCD左右对比。后续识别收益需另外验证，当前不能宣称普遍优于现有识别模型。

## 回来后的步骤

由助手在你确认重新上电后执行：start_multinex_static.tcl→run_multinex_static.tcl（十项输入）→validate_multinex_readback.py→显示08_full真实照片并再次验证。无需先写SD。电脑中的旧r3b已验证恢复包、此前旧模型和旧SD文件都保留。

位流：multinex_static.bit；ARM程序：multinex_static.elf；PS初始化：ps7_init.tcl。handoff_status.json和offline_acceptance.json记录本阶段边界。计算核心源码和IP在E:/FPGA_Enhance_Work/multinex_hls_r4d_20261026/。本包是待实板验证候选，不是已验证新版发布包。
'''
    (ROOT/'待上板说明.md').write_text(doc,encoding='utf-8')
    shutil.copy2(HERE/'package_multinex_fast_offline.py',ROOT/'package_multinex_fast_offline.py')
    selected=[p for p in ROOT.iterdir() if p.is_file() and p.suffix in
        ('.bit','.elf','.xsa','.tcl','.py','.json','.md','.rpt','.txt') and
        p.name not in ('candidate_manifest.json','offline_release.json')]
    for name in ('inputs','expected','app_src'):
        selected.extend(p for p in (ROOT/name).rglob('*') if p.is_file())
    selected=sorted(set(selected))
    manifest=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in selected]
    (ROOT/'candidate_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    archive=ROOT.parent/'multinex_fast_r4d_offline_candidate_20261026.zip'
    assert not archive.exists(), 'Preserve existing candidate archive'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in selected:z.write(p,p.relative_to(ROOT).as_posix())
        z.write(ROOT/'candidate_manifest.json','candidate_manifest.json')
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    (ROOT/'offline_release.json').write_text(json.dumps(dict(archive=str(archive),bytes=archive.stat().st_size,
        sha256=sha(archive),crc_ok=True,downloaded=False),indent=2),encoding='utf-8')
    print('OFFLINE_CANDIDATE_PACKAGED_NOT_DOWNLOADED',sha(archive),flush=True)

if __name__=='__main__':main()
