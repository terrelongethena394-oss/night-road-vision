"""Archive the actually verified r3b board baseline before speed experiments."""
from pathlib import Path
import json,hashlib,zipfile,shutil
ROOT=Path('E:/FPGA_Enhance_Work/multinex_static_20261025')
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    acceptance=json.loads((ROOT/'offline_acceptance.json').read_text(encoding='utf-8'))
    board=json.loads((ROOT/'board_full/readback_validation.json').read_text())
    final=json.loads((ROOT/'display_final/readback_validation.json').read_text())
    assert board['status']=='ACTUAL_BOARD_NUMERICAL_PASS' and board['all_prepared_cases_covered'] and board['full_480x800_tested']
    assert final['status']=='ACTUAL_BOARD_NUMERICAL_PASS'
    assert sha(ROOT/'multinex_static.bit')==acceptance['bit_sha256']
    assert sha(ROOT/'multinex_static.elf')==acceptance['elf_sha256']
    for r in acceptance['old_preserved']:assert sha(Path(r['path']))==r['sha256']
    pixels=sum(c['height']*c['width'] for c in board['cases'])
    full=next(c for c in board['cases'] if c['height']==480 and c['width']==800)
    native=next(c for c in board['cases'] if c['height']==400 and c['width']==600)
    result=dict(status='DEPLOYED_STATIC_IMAGE_BOARD_NUMERICAL_VERIFIED',input_cases=len(board['cases']),pixels=pixels,
        full_frame_seconds=full['kernel_wall_seconds'],native_frame_seconds=native['kernel_wall_seconds'],resources=acceptance['resources'],
        setup_slack_ns=acceptance['setup_slack_ns'],hold_slack_ns=acceptance['hold_slack_ns'],bus_skew_min_slack_ns=acceptance['bus_skew_min_slack_ns'],
        bit_sha256=acceptance['bit_sha256'],elf_sha256=acceptance['elf_sha256'],camera_enabled=False,sd_written=False,
        display='08_full: actual real-photo RAW/ENH side-by-side in LCD DDR. Panel appearance not independently photographed.',
        restriction='Static numerical success, not realtime camera or improved recognition accuracy. 800x480 about3.67s. Keep as fallback while optimizing speed.')
    (ROOT/'verified_baseline.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    doc=f'''# 已上板验证的静态图增强基线（2026-10-26）

新增强模型已真正生成位流、通过JTAG下载，并完成实板回读。当前包保留为速度优化前的可恢复基线；后续候选使用独立目录，不覆盖它。

- 实板测试{len(board['cases'])}项、共{pixels}像素（含重复/边界测试），输入校验正确，全部输出逐字节匹配冻结整数参考；控制图的均值、gate和保留特征也精确，VDMA错误为0。
- 包括400x600真实暗光图、完整480x800图、黑白随机/1x1/奇数/宽窄图，并在大图后重复小图验证状态复用。最后又单独显示并回读480x800真实照片。
- 实际内核起止墙钟：400x600为{native['kernel_wall_seconds']:.6f}秒，480x800为{full['kernel_wall_seconds']:.6f}秒。计时排除电脑传图和ARM显示合成，包含轮询粒度及实际DDR/显示竞争。不能宣称实时，不能以小图耗时外推摄像头FPS。
- 整机已布线资源：LUT30471/53200、FF36574/106400、BRAM Tile77.5/140、DSP120/220。100MHz、WNS0.094ns、WHS0.006ns，5项总线偏斜约束均满足。现有板级约束仍缺部分外部IO延迟，并继承摄像头像素时钟布线警告；不宣称完整的外部接口时序签核。

PL执行全部Multinex整数增强算子；ARM负责DDR地址、启动/完成、计时、校验和LCD左右对比。这版没有运行数字识别核，也没有修改识别器的训练结果。摄像头采集DMA未启动，SD卡未写入。

板上当前版本靠独立电源维持运行；JTAG只用于加载及传图片。它是易失下载，断电后不会自动启动这份新程序；此前SD版本和旧成功包均保留。不要把当前bit直接当作SD启动镜像。

入口文件：multinex_static.bit、multinex_static.elf、ps7_init.tcl；手动恢复脚本start_multinex_static.tcl，批量数值测试run_multinex_static.tcl，验证validate_multinex_readback.py。实际记录位于board_full/、display_final/。actual_board_comparison.png是直接由真实DDR回读绘制，非软件预期图或LCD拍照。

继续改进的重点是计算调度和速度。原模型权重/舍入不改；新加速候选必须再通过C/RTL、整机时序、实板逐字节与实测耗时，才替换这份基线。
'''
    (ROOT/'实板基线说明.md').write_text(doc,encoding='utf-8')
    shutil.copy2(HERE/'finish_multinex_static.py',ROOT/'finish_multinex_static.py')
    selected=[]
    for p in ROOT.iterdir():
        if p.is_file() and p.suffix in ('.bit','.elf','.xsa','.tcl','.py','.json','.md','.png','.rpt','.txt') and p.name not in ('release.json','runtime_manifest.json'):
            selected.append(p)
    for d in ('inputs','expected','app_src','board_full','display_final'):
        selected.extend(p for p in (ROOT/d).rglob('*') if p.is_file())
    manifest=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(set(selected))]
    (ROOT/'runtime_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    archive=ROOT.parent/'multinex_static_verified_20261026.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(set(selected)):z.write(p,p.relative_to(ROOT).as_posix())
        z.write(ROOT/'runtime_manifest.json','runtime_manifest.json')
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    (ROOT/'release.json').write_text(json.dumps(dict(archive=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),crc_ok=True),indent=2),encoding='utf-8')
    print('VERIFIED_STATIC_BASELINE_ARCHIVED',pixels,full['kernel_wall_seconds'],sha(archive),flush=True)
if __name__=='__main__':main()
