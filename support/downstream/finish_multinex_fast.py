"""Release only a physically implemented, numerically verified speed improvement."""
from pathlib import Path
import json, hashlib, zipfile, shutil
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path('E:/FPGA_Enhance_Work/multinex_fast_static_r4d_20261026')
OLD = ROOT.parent / 'multinex_static_20261025'
HERE = Path(__file__).resolve().parent

def read(p):
    return json.loads(p.read_text(encoding='utf-8'))

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    acceptance = read(ROOT/'offline_acceptance.json')
    old = read(OLD/'board_full/readback_validation.json')
    board = read(ROOT/'board_full/readback_validation.json')
    final = read(ROOT/'display_final/readback_validation.json')
    assert all(r['status']=='ACTUAL_BOARD_NUMERICAL_PASS' for r in (old, board, final))
    assert board['all_prepared_cases_covered'] and board['full_480x800_tested']
    assert len(final['cases'])==1 and final['cases'][0]['id']=='08_full'
    assert sha(ROOT/'multinex_static.bit')==acceptance['bit_sha256']
    assert sha(ROOT/'multinex_static.elf')==acceptance['elf_sha256']==sha(OLD/'multinex_static.elf')
    for item in acceptance['old_preserved']:
        assert sha(Path(item['path']))==item['sha256']
    comparisons=[]
    previous={r['id']:r for r in old['cases']}
    for row in board['cases']:
        before=previous[row['id']]
        assert row['output_sha256']==before['output_sha256']
        comparisons.append(dict(id=row['id'],height=row['height'],width=row['width'],
            before_seconds=before['kernel_wall_seconds'],after_seconds=row['kernel_wall_seconds'],
            speedup=before['kernel_wall_seconds']/row['kernel_wall_seconds'],output_unchanged=True))
    full=next(r for r in comparisons if r['id']=='08_full')
    native=next(r for r in comparisons if r['id']=='07_native_real')
    assert full['speedup']>1 and native['speedup']>1, 'Do not release a slower candidate as an optimization'
    result=dict(status='DEPLOYED_FASTER_STATIC_IMAGE_BOARD_VERIFIED',comparisons=comparisons,
        cases=len(board['cases']),pixels=sum(r['height']*r['width'] for r in board['cases']),
        full_frame_seconds=full['after_seconds'],full_frame_speedup=full['speedup'],
        native_frame_seconds=native['after_seconds'],resources=acceptance['resources'],
        setup_slack_ns=acceptance['setup_slack_ns'],hold_slack_ns=acceptance['hold_slack_ns'],
        bus_skew_min_slack_ns=acceptance['bus_skew_min_slack_ns'],clock_mhz=100,
        bit_sha256=acceptance['bit_sha256'],elf_sha256=acceptance['elf_sha256'],
        camera_enabled=False,recognizer_enabled=False,sd_written=False,
        note='Same frozen enhancement model and output. Speed is actual ARM start-to-done wall time; host image transfer and display composition excluded. Not camera FPS or a recognition accuracy claim.')
    (ROOT/'board_deployed.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    handoff=ROOT/'handoff_status.json'
    if handoff.exists() and not (ROOT/'offline_handoff_status.json').exists():
        shutil.copy2(handoff,ROOT/'offline_handoff_status.json')
    handoff.write_text(json.dumps(dict(result,hardware_paused_by_user=False,downloaded=True,
        remaining=['Camera and recognition evaluation are separate future work; SD remains unchanged']),
        ensure_ascii=False,indent=2),encoding='utf-8')
    # The right image must come from a genuine DDR dump, never a PC expected file.
    raw=np.fromfile(ROOT/'inputs/08_full.rgba32',dtype=np.uint8).reshape(480,800,4)[:,:,:3]
    enhanced=np.fromfile(ROOT/'display_final/08_full.output32',dtype=np.uint8).reshape(480,800,4)[:,:,:3]
    picture=Image.new('RGB',(1600,520),'white')
    picture.paste(Image.fromarray(raw),(0,40));picture.paste(Image.fromarray(enhanced),(800,40))
    draw=ImageDraw.Draw(picture)
    draw.text((12,12),'RAW: actual input',fill='black')
    draw.text((812,12),'ENH: actual FPGA DDR readback',fill='black')
    picture.save(ROOT/'actual_board_comparison.png')
    resources=acceptance['resources']
    doc=f'''# 加速版实板结果（2026-10-26）

已完成同一增强网络的硬件调度优化、C/RTL验证、整机布局布线、JTAG下载和实板回读。原权重、舍入规则和图像输出保持不变。

网络来自公开Multinex-Nano（696参数），本次完成定点硬件映射和调度优化，不宣称自行提出原网络。加速方式包括通道分组行缓存、并行点卷积、空间部分和、像素循环流水和乘法流水。计算核心源码与IP在E:/FPGA_Enhance_Work/multinex_hls_r4d_20261026/；C验证9例627908像素，RTL联合仿真4例1860像素且独立核对7440个保留特征整数。完整480×800数值正确性由下面的实板回读补充验证。

实板{result['cases']}项输入、{result['pixels']}像素全部逐字节匹配参考和旧基线；控制图的均值/gate/保留特征精确，VDMA错误为0。涵盖黑白随机、奇数尺寸、宽窄边界、400×600真实照片、480×800及大图后小图重复。

| 实际输入 | 旧版内核耗时 | 新版内核耗时 | 加速比 |
|---|---:|---:|---:|
| 400×600 | {native['before_seconds']:.6f} s | {native['after_seconds']:.6f} s | {native['speedup']:.2f}× |
| 480×800 | {full['before_seconds']:.6f} s | {full['after_seconds']:.6f} s | {full['speedup']:.2f}× |

计时为ARM启动IP到完成的实际墙钟，包含DDR/LCD竞争与轮询，排除电脑JTAG传图、校验及ARM显示合成。这不是摄像头端到端帧率。

实际整机资源：LUT {resources['Slice LUTs']:g}/53200、FF {resources['Slice Registers']:g}/106400、BRAM Tile {resources['Block RAM Tile']:g}/140、DSP {resources['DSPs']:g}/220。100MHz，setup余量{acceptance['setup_slack_ns']:.3f}ns、hold余量{acceptance['hold_slack_ns']:.3f}ns；总线偏斜约束满足。沿用板级约束仍缺部分外部IO delay，不能声称完整外部接口签核。

PL负责全部整数神经网络增强；ARM负责DDR缓冲、控制、计时、校验和LCD左右显示。本版采用静态真实照片，不运行摄像头采集或数字识别。速度优化不会自动提高识别准确率，也不代表所有场景的噪声/细节均改善。

当前屏幕保留真实暗光照片，左RAW右ENH。actual_board_comparison.png直接使用实板DDR回读绘制，不是LCD拍照。JTAG加载易失，断电后不自动启动新程序；SD卡没有写入。旧版位流、ARM程序和旧SD镜像均保留。

恢复入口：start_multinex_static.tcl；验证入口：run_multinex_static.tcl、validate_multinex_readback.py。实测数据见board_full/、display_final/和board_deployed.json。
'''
    (ROOT/'加速版实板结果.md').write_text(doc,encoding='utf-8')
    old_note=ROOT/'待上板说明.md'
    if old_note.exists():
        text=old_note.read_text(encoding='utf-8')
        prefix='> 上板前的历史记录。当前已完成JTAG下载及实板验证，最新状态见[加速版实板结果](加速版实板结果.md)。\n\n'
        if not text.startswith('> 上板前的历史记录。'):
            old_note.write_text(prefix+text,encoding='utf-8')
    (ROOT/'README.md').write_text('# 加速版已上板验证\n\n详见[加速版实板结果](加速版实板结果.md)。\n\n'
        f'800×480实际内核耗时{full["after_seconds"]:.6f}秒，对旧版加速{full["speedup"]:.2f}倍；十项实板输出全精确。'
        '\n\n当前为静态照片增强，摄像头和识别未启用。SD卡未写入；JTAG加载断电后失效。'
        '\n\n待上板说明.md、offline_handoff_status.json和offline_release.json为此前离线阶段历史记录。\n',encoding='utf-8')
    shutil.copy2(HERE/'finish_multinex_fast.py',ROOT/'finish_multinex_fast.py')
    selected=[p for p in ROOT.iterdir() if p.is_file() and p.suffix in
        ('.bit','.elf','.xsa','.tcl','.py','.json','.md','.png','.rpt','.txt') and
        p.name not in ('runtime_manifest.json','release.json')]
    for name in ('inputs','expected','app_src','board_full','display_final'):
        selected.extend(p for p in (ROOT/name).rglob('*') if p.is_file())
    selected=sorted(set(selected))
    manifest=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in selected]
    (ROOT/'runtime_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    archive=ROOT.parent/'multinex_fast_verified_20261026.zip'
    assert not archive.exists(), 'Preserve any existing verified release'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in selected:z.write(p,p.relative_to(ROOT).as_posix())
        z.write(ROOT/'runtime_manifest.json','runtime_manifest.json')
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    (ROOT/'release.json').write_text(json.dumps(dict(archive=str(archive),bytes=archive.stat().st_size,
        sha256=sha(archive),crc_ok=True),indent=2),encoding='utf-8')
    print('FAST_BOARD_RELEASED',json.dumps(full),sha(archive),flush=True)

if __name__=='__main__':
    main()
