"""Prepare reviewed local demo entries; package only after entry checks pass."""
from pathlib import Path
import datetime, hashlib, json, shutil, sys, zipfile

HERE=Path(__file__).resolve().parent
ROOT=Path('E:/FPGA_Enhance_Work/road_retinex_noiseguard_arm_20261029_r1')
OFFLINE=Path('E:/FPGA_Enhance_Work/road_retinex_noiseguard_20261029_r2')
APP=ROOT/'firmware'
STABLE=Path('E:/FPGA_Enhance_Work/road_conv13_p16_runtime_20261028_r1/firmware')
WORK=HERE.parent.parent
PY='E:\\FPGA_Enhance_Work\\nn_env312\\Scripts\\python.exe'

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def prepare():
    proof=read(ROOT/'board_verified.json');assert proof['elf_sha256']==sha(APP/'road_detail.elf')
    assert all(r['pixel_max_abs']==0 and r['decode_byte_exact'] and r['boxes_byte_exact'] and r['frame_byte_exact'] for r in proof['results'])
    write(ROOT/'visual_review.json',dict(date='2026-10-29',reviewer='assistant',method='Viewed actual board framebuffer for both clear-night photos and rainy-night photo, plus same-input offline comparisons.',approved_for_experimental_demo=True,final_quality_accepted=False,physical_panel_rechecked=False,judgment='Modest subjective improvement: more restrained dark areas and less grain. Rain scene still noisy; no recovered optical detail. Lower brightness explains part of the apparent improvement.',limitations=['Known development photos, not blind testing','Paired20 reference metrics decreased; not a universal enhancement improvement','Detector still reads raw pixels; no recognition accuracy improvement claim','Fixed-photo mode, not realtime detection'],sd_written=False))
    baseline=read(ROOT/'actual_abi18_baseline.json')
    for c in read(APP/'cases.json'):
        old=Path(baseline['evidence'])/c['name'];f=APP/'runtime/cases'/c['name']
        shutil.copy2(old/'decoded.f32',f/'abi18_decoded.f32');shutil.copy2(old/'boxes.f32',f/'abi18_boxes.f32')
    shutil.copy2(HERE/'retinex_fixed_entry.py',ROOT/'retinex_fixed_entry.py')
    src=ROOT/'algorithm_source';src.mkdir(exist_ok=True)
    for name in ['road_retinex_noiseguard.py','road_retinex_project.py','road_local_enhance_v2.py','road_retinex_noiseguard_c.c','road_retinex_detail_c.h','road_retinex_wrapper.c','prepare_noiseguard_arm.py','verify_noiseguard_arm.py','validate_retinex_c.py','build_retinex_arm.py','verify_retinex_arm_board.py','study_retinex_noiseguard.py','compare_noiseguard_board.py','package_noiseguard.py']:
        shutil.copy2(HERE/name,src/name)
    # The frozen protocol and source are retained, including rejected r1.
    for name in ['protocol.json','paired20_regression.json','complete.json']:
        shutil.copy2(OFFLINE/name,ROOT/('offline_'+name))
    previous=Path('E:/FPGA_Enhance_Work/road_retinex_noiseguard_20261029_r1')
    shutil.copy2(previous/'protocol.json',ROOT/'rejected_smoothstep_protocol.json')
    shutil.copy2(previous/'road_retinex_noiseguard.py',src/'rejected_smoothstep_reference.py')
    cmdmap={
      '01_start_fixed_photo.cmd':['start','1','full'],
      '02_show_photo2.cmd':['show','2','full'],
      '03_show_rain_photo3.cmd':['show','3','full'],
      '04_raw_bypass_photo1.cmd':['show','1','raw'],
      '05_restore_enhanced_photo1.cmd':['show','1','full'],
    }
    for name,args in cmdmap.items():
        text='@echo off\r\n"'+PY+'" "%~dp0retinex_fixed_entry.py" '+' '.join(args)+'\r\nset "demo_exit=%errorlevel%"\r\npause\r\nexit /b %demo_exit%\r\n'
        (ROOT/name).write_text(text,encoding='ascii',newline='')
    (ROOT/'00_restore_camera.cmd').write_text('@echo off\r\n"'+PY+'" "'+str(STABLE/'user_start.py')+'"\r\nset "demo_exit=%errorlevel%"\r\npause\r\nexit /b %demo_exit%\r\n',encoding='ascii',newline='')
    checks={str(p.relative_to(APP)):sha(p) for p in APP.rglob('*') if p.is_file() and p.name!='runtime_checksums.json' and 'obj' not in p.relative_to(APP).parts and p.suffix not in ['.log','.map','.su']}
    write(APP/'runtime_checksums.json',checks)
    print('NOISEGUARD_ENTRIES_PREPARED',flush=True)

def finish():
    proof=read(ROOT/'board_verified.json');runs=[read(p) for p in (ROOT/'user_runs').glob('*/verified.json')]
    assert any(r['photo']==2 and r['mode']=='full' for r in runs)
    assert any(r['photo']==1 and r['mode']=='raw' for r in runs)
    assert any(r['photo']==1 and r['mode']=='full' for r in runs)
    latest=max((ROOT/'user_runs').glob('*/verified.json'),key=lambda p:p.parent.name)
    assert read(latest)['photo']==1 and read(latest)['mode']=='full'
    c=read(ROOT/'c_complete.json');reg=read(ROOT/'offline_paired20_regression.json')
    report=f'''# 夜间道路增强实验版 ABI22（2026-10-29）

当前为固定图片模式：左侧原图，右侧自编 Retinex 增强显示及车辆框。车辆检测读取原图。移动手掌不会改变当前照片。

## 使用

本地工作目录：`{ROOT.as_posix()}`。开发板保持独立供电，JTAG 与 OV5640 连接，使用此前已验证的 JTAG 启动配置。

- `01_start_fixed_photo.cmd`：重新下载实验程序，显示第一张晴夜图。
- `02_show_photo2.cmd`：显示第二张晴夜图；先启动本版。
- `03_show_rain_photo3.cmd`：显示雨夜失败样例；先启动本版。
- `04_raw_bypass_photo1.cmd`：第一张图关闭增强，用于对照。
- `05_restore_enhanced_photo1.cmd`：恢复第一张图增强显示。
- `00_restore_camera.cmd`：恢复原 ABI18 摄像头版本。

切图、原图旁路及恢复增强入口经过本轮实测；启动入口使用本轮已验证的同一下载流程，恢复摄像头入口调用此前已验证的 ABI18 启动器。依赖现有 E 盘 Python、Xilinx 2020.2 和 ABI18 回退目录，并非免安装、可任意移动的独立软件。没有生成或改写 SD 启动文件；本版断电后需重新通过 JTAG 启动。

构建和评测脚本也保留了本机绝对路径及外部实验数据目录依赖。算法实现保存在 `algorithm_source`，实际固件源代码保存在 `firmware/source`；本包主要用于本机复现和保存证据。

## 改动与画质判断

保留原 Retinex 光照估计，限制增益并对极暗像素使用平缓的亮度保护；相似图块滤波对亮度最多混合 30%，颜色混合最多 60%。没有使用检测框选择增强区域，也没有训练新的增强神经网络。NN 车辆检测权重和 P16 卷积硬件保持原样。

助手直接查看三张开发板帧缓存，并按同图与 ABI21 对比。主观判断为小幅改善：暗部更收敛，路面颗粒有所减轻，窗户与标线结构保留；部分观感变化来自亮度降低。雨夜仍有颗粒和色块，400×240 工作图及原图已有模糊没有恢复。本版只作为夜间道路实验候选，不提升为最终稳定版，正式摄像头回退仍为 ABI18。未重新进行实物屏幕人工验收。

## 验证与边界

- 32 个 C／Python 用例通过像素容差、输入不变和缓冲区边界检查；最大差异 {max(r['max_abs'] for r in c['cases'])} 个灰度级。
- 板上两张晴夜图、一张雨夜图、纯黑图及首图复测共 5 次：增强像素与 C 参考逐字节一致；检测解码、NMS 框与相同输入的实际 ABI18 基准逐字节一致；屏幕帧与独立绘图器逐字节一致。
- 基准是前次实际 ABI18 测量，逐一核对输入、硬件、权重和输出哈希后复用；本轮没有伪称重新测量基准。
- 逐次处理约 {min(r['processing_seconds'] for r in proof['results']):.2f}–{max(r['processing_seconds'] for r in proof['results']):.2f} 秒，增强阶段约 {min(r['enhancement_stage_seconds'] for r in proof['results']):.2f}–{max(r['enhancement_stage_seconds'] for r in proof['results']):.2f} 秒。包含预览回调，不含 JTAG 传输／读回，不能当实时检测帧率。
- 已有 20 张配对参考图的描述性回归：PSNR {reg['psnr']:.3f} dB，SSIM {reg['ssim']:.4f}，低于 ABI21 的 12.949 dB／0.5495。该组不是新盲测，结果说明本版不能宣称对极暗照片普遍更好。
- 原图识别路径保持一致，不能宣称增强提升识别准确率；预测框数量不等于正确车辆数量。

ELF SHA256：`{proof['elf_sha256']}`。

纸面算法来源：Upadhyay 与 Sarawadekar，2024，DOI 10.1109/TCSII.2024.3361561。光照估计为独立实现；暗部保护和滤波为本工程改造，不能宣称完全独创 Retinex 理论。
'''
    (ROOT/'使用与验证说明.md').write_text(report,encoding='utf-8')
    (WORK/'道路增强新版上板记录_20261029.md').write_text(report,encoding='utf-8')
    current=WORK/'当前增强候选_20261029.json';archive=WORK/'历史增强候选_论文强增益_20261029.json'
    if current.exists() and not archive.exists():shutil.copy2(current,archive)
    write(current,dict(status='ABI22_ROAD_SPECIFIC_EXPERIMENT_BOARD_VERIFIED_NOT_FINAL_STABLE',date='2026-10-29',directory=str(ROOT),source=str(HERE/'road_retinex_noiseguard.py'),preset='guard_light',enhancer_is_neural_network=False,enhancement_pretrained_weights_used=False,detector_input='raw RGB888',board_verified=True,visual_review='assistant framebuffer review; modest improvement, residual rain noise; physical panel not rechecked',paired_psnr=reg['psnr'],paired_ssim=reg['ssim'],paired_metrics_regressed_vs_abi21=True,sd_written=False,formal_camera_fallback=str(STABLE),report=str(WORK/'道路增强新版上板记录_20261029.md')))
    checkpoint=WORK/'固定图片展示当前状态_20261029.md'
    old=checkpoint.read_text(encoding='utf-8') if checkpoint.exists() else ''
    marker='# 当前：ABI22 道路专用实验版已上板'
    if not old.startswith(marker):checkpoint.write_text(marker+'\n\n当前屏幕为第一张晴夜固定图；左原图、右增强及原图检测框。详见《道路增强新版上板记录_20261029.md》。正式摄像头回退仍为 ABI18，SD 卡未修改。\n\n以下为历史记录，不能作为当前版本参数：\n\n'+old,encoding='utf-8')
    files=[p for p in ROOT.rglob('*') if p.is_file() and 'obj' not in p.relative_to(ROOT).parts and p.name!='package_manifest.json']
    manifest={p.relative_to(ROOT).as_posix():sha(p) for p in files};write(ROOT/'package_manifest.json',manifest)
    target=ROOT.with_name('road_noiseguard_ABI22_verified_20261029.zip');assert not target.exists()
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files+[ROOT/'package_manifest.json']:z.write(p,ROOT.name+'/'+p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        for name,h in manifest.items():assert hashlib.sha256(z.read(ROOT.name+'/'+name)).hexdigest()==h
    write(ROOT.parent/'road_noiseguard_ABI22_package_20261029.json',dict(path=str(target),bytes=target.stat().st_size,sha256=sha(target),crc_and_manifest_verified=True,sd_written=False))
    print('NOISEGUARD_PACKAGE_COMPLETE',target,sha(target),flush=True)

if __name__=='__main__':
    {'prepare':prepare,'finish':finish}[sys.argv[1]]()
