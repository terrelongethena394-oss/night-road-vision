"""Freeze measured plate runtime and preserve every preselected replay result."""
from pathlib import Path
import csv, json, shutil, urllib.request, zipfile
import numpy as np
from PIL import Image
from plate_common import BASE, ROOT, sha, write

BOARD = BASE / 'camera_plate_guarded_20261026'
PREVIOUS = BASE / 'camera_plate_neon_20261026'
HERE = Path(__file__).resolve().parent

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def summarize(rows):
    return [dict(gain=g, n=len(rs), correct=[sum(r['displayed'][i] == r['truth'] for r in rs) for i in range(3)])
            for g in [1., .25] for rs in [[r for r in rows if r['truth'] is not None and r['gain'] == g]]]

def main():
    offline = read(BOARD/'offline_camera.json')
    held = read(BOARD/'plate_offline_results.json')
    proof = read(BOARD/'plate_numeric_proof.json')
    assert held['accepted'] and offline['consistency_guard']
    assert sha(BOARD/'camera.elf') == offline['elf_sha256']
    assert sha(BOARD/'camera.bit') == offline['bit_sha256']
    assert sha(BOARD/'plate_model.pth') == proof['model_sha256'] == offline['model_sha256']
    assert sha(BOARD/'app_src/plate_weights.h') == proof['weights_header_sha256']
    assert sha(BOARD/'app_src/plate_native_kernel.h') == proof['kernel_sha256']
    assert sha(BOARD/'app_src/plate_arm_kernel.h') == offline['arm_optimized_header_sha256']
    assert read(BOARD/'batch_validation_complete.json')['n'] == 14
    rows, baseline, checks = [], [], []
    for c in read(BOARD/'plate_cases.json'):
        folder = BOARD/'board_plate'/c['id']
        a, b = read(folder/'plate_validation.json'), read(folder/'validation.json')
        assert all(a[k] for k in ['gray_exact','normalized_exact','scores_exact','ctc_tokens_exact','display_glyphs_exact','decision_exact'])
        assert a['model_sha256'] == proof['model_sha256']
        assert b['rgb_output_exact'] and b['lcd_pixels_exact'] and b['source_kind'] == 'host_photo'
        assert sha(folder/'input32.bin') == c['input_sha256']
        checks.append(a)
        rows.append(dict(id=c['id'], truth=c['truth'], gain=c['gain'], displayed=a['displayed'],
                         initial_candidate=a['candidate_word'], fallback=a['consistency_fallback'], protection=b['protection']))
        old = read(PREVIOUS/'board_plate'/c['id']/'plate_validation.json')
        assert sha(PREVIOUS/'board_plate'/c['id']/'input32.bin') == c['input_sha256']
        baseline.append(dict(id=c['id'], truth=c['truth'], gain=c['gain'], displayed=old['displayed']))
    live = read(BOARD/'live_snapshot/plate_validation.json')
    lv = read(BOARD/'live_snapshot/validation.json')
    assert all(live[k] for k in ['gray_exact','normalized_exact','scores_exact','ctc_tokens_exact','display_glyphs_exact','decision_exact'])
    assert live['model_sha256'] == proof['model_sha256']
    assert lv['source_kind'] == 'live_camera' and lv['capture_reduction_exact'] and lv['rgb_output_exact'] and lv['lcd_pixels_exact']
    assert live['displayed'] == ['--']*3  # Observed no-plate live control, not a positive camera accuracy test.
    checks.append(live)
    with (BOARD/'live_cadence.csv').open() as f:
        cadence = list(csv.DictReader(f))
    assert len(cadence) == 11 and all(int(r[k]) == 0 for r in cadence for k in ['read_error','write_error','error'])
    seconds = (int(cadence[-1]['elapsed_ms'])-int(cadence[0]['elapsed_ms']))/1000
    frames = int(cadence[-1]['sequence'])-int(cadence[0]['sequence'])
    hz = frames/seconds
    assert seconds >= 9.5 and hz >= offline['performance_acceptance_hz']
    assert 'CAMERA_SNAPSHOT_CAPTURED_AND_RESUMED' in (BOARD/'live_snapshot.log').read_text()
    assert 'CONTINUOUS_CAMERA_CADENCE_MEASURED' in (BOARD/'live_cadence.log').read_text()
    photo = [r for r in rows if r['truth'] is not None]
    negatives = [r for r in rows if r['truth'] is None]
    assert all(r['displayed'] == ['--']*3 for r in negatives)
    assert all(r['displayed'][2] == r['truth'] for r in photo if r['displayed'][0] == r['truth'])
    summary, before = summarize(rows), summarize(baseline)
    wins_losses = {label:dict(wins=sum(r['displayed'][0] != r['truth'] and r['displayed'][i] == r['truth'] for r in photo),
                                  losses=sum(r['displayed'][0] == r['truth'] and r['displayed'][i] != r['truth'] for r in photo))
                   for i,label in [(1,'NET'),(2,'AUTO')]}
    result = dict(status='PLATE_GUARDED_OFFLINE_ACCEPTED_AND_BOARD_VERIFIED',model_sha256=proof['model_sha256'],
                  elf_sha256=offline['elf_sha256'],bit_sha256=offline['bit_sha256'],live_update_hz=hz,
                  completed_updates=frames,measured_seconds=seconds,dma_errors=0,
                  photo_summary=summary,previous_without_consistency_guard=before,cases=rows,
                  enhancement_wins_losses=wins_losses,live=live,numeric_cases=len(checks),
                  gray_bytes=sum(a['gray_bytes'] for a in checks),normalized_bytes=sum(a['normalized_bytes'] for a in checks),
                  score_count=sum(a['scores'] for a in checks),sd_written=False,live_restored=True,
                  camera_positive_plate_tested=False,automatic_plate_localization=False,
                  recognition_processor='ARM Cortex-A9 NEON',enhancement_processor='PL Multinex unchanged r4d',
                  scope='Given rectangular ROI, seven-character blue plate recognition. Not eight-character green plate recognition.',
                  enhancement_general_benefit_established=False)
    write(BOARD/'board_deployed.json',result)
    # Keep the original predeployment build record; current status is board_deployed.json.
    credits = BOARD/'source_records'; credits.mkdir(exist_ok=True)
    for name,url in {
        'CCPD_LICENSE.txt':'https://raw.githubusercontent.com/detectRecog/CCPD/master/LICENSE',
        'FASHION_MNIST_LICENSE.txt':'https://raw.githubusercontent.com/zalandoresearch/fashion-mnist/master/LICENSE',
    }.items():
        if not (credits/name).exists():
            data = urllib.request.urlopen(url, timeout=30).read()
            assert b'MIT License' in data
            (credits/name).write_bytes(data)
    for name,path in {
        'data_protocol.json':ROOT/'data/protocol.json','data_complete.json':ROOT/'data/complete.json',
        'data_manifest.json':ROOT/'data/manifest.json','training_protocol.json':ROOT/'tiny_student01/protocol.json',
        'negative_source_credits.json':ROOT/'negatives/source_credits.json',
        'pre_guard_external_ocr.json':PREVIOUS/'external_ocr/results.json',
    }.items():
        shutil.copy2(path,credits/name)
    for p in (ROOT/'tiny_student01').glob('*.json*'):
        shutil.copy2(p,credits/('training_'+p.name))
    shutil.copy2(BASE/'multinex_camera_digit_upgrade_20261026/download_jtag.cmd',BOARD/'download_jtag.cmd')
    source = BOARD/'experiment_source'; source.mkdir(exist_ok=True)
    names = ['plate_common.py','tiny_plate_model.py','tiny_plate_integer.py','train_tiny_plate.py',
             'evaluate_tiny_plate.py','prepare_plate_camera.py','stage_plate_cases.py','stage_plate_runtime_tools.py',
             'validate_plate_batch.py','validate_plate_camera.py','validate_multinex_camera.py','finish_plate_camera.py']
    for name in names:
        shutil.copy2(HERE/name,source/name)
    # Public source-photo card: no camera/private content, no synthetic drawing.
    a = np.fromfile(BOARD/'board_plate/plate_00_gain1000/input32.bin',np.uint8).reshape(240,400,4)
    Image.fromarray(a[72:168,8:392,:3]).save(BOARD/'车牌对准测试图.png')
    table = '\n'.join(f'| {r["gain"]:g} | {r["n"]} | '+ ' | '.join(map(str,r['correct']))+' |' for r in summary)
    oldtable = '\n'.join(f'| {r["gain"]:g} | {r["n"]} | '+ ' | '.join(map(str,r['correct']))+' |' for r in before)
    offline_rows = '\n'.join(f'| {gain} | 1200 | {held["results"][str(gain)]["student_integer"]["correct"]}/1200 ({100*held["results"][str(gain)]["student_integer"]["full_plate_accuracy"]:.2f}%) | {held["results"][str(gain)]["teacher"]["correct"]}/1200 |' for gain in [1.,.25,.125])
    case_rows = '\n'.join('| '+r['id']+' | '+str(r['truth'] or '非车牌')+' | '+' | '.join(r['displayed'])+f' | {int(r["fallback"])} |' for r in rows)
    report = f'''# 七位蓝牌识别：训练与实板验证（2026-10-26）

车牌版已通过JTAG部署，并已恢复实时摄像头。旧工程、旧权重和SD卡内容保留，本轮未写SD。当前启动包：camera_plate_guarded_20261026。

## 已完成的功能

在指定长方形区域内识别完整七位车牌，包括首位省份汉字、字母和数字。约9.3万参数的TinyPlate序列CNN，24时间步CTC解码，输入96×32灰度；整数化并使用ARM NEON提速。FPGA PL仍运行原来的Multinex图像增强网络，ARM完成ROI、灰度/对比度归一化、车牌识别、保护和界面。不能描述成车牌识别核心也已部署到PL。

屏幕左侧RAW原图，右侧AUTO最终图。底部RAW、NET、AUTO分别是原图、纯增强、最终保护图的识别；格式不合格显示“--”。格式合格不等于一定识别正确。默认处理画面400×240，ROI为(8,72,384,96)，屏幕图像显示区域y=120到359；需将车牌放入对应绿框。尚无整幅场景自动车牌定位，也不支持八位新能源绿牌。

## 数据与离线训练结果

使用[CCPD作者项目](https://github.com/detectRecog/CCPD)的数字文件名标注，实际下载为[社区裁剪镜像](https://huggingface.co/datasets/zenitsu09/ccpd-ocr-recognition)，不是作者官方上传。镜像版本a859a9f1180675b69ee7fcbc884758406900b5b7，只下载一个约226MB分片，源文件SHA256记录于source_records/data_complete.json。训练5946张（5379种号码），验证1200张，测试1200张（1085种号码），按完整号码分组，主训练/验证/测试号码不交叉。另有600张难例辅助集，不作为此报告主准确率。

模型参考[开源LPRNet](https://github.com/sirius-ai/LPRNet_Pytorch)，以其固定模型作训练集教师；教师正确的训练样本才使用蒸馏。训练标签来自CCPD真实标注。12000步训练，按验证集选权重，固定后做测试。独立目录安装CUDA依赖，用电脑RTX4060训练；板上运行不依赖电脑GPU。整数卷积每图2,761,728 MAC，教师约144,411,264 MAC，这不是板上速度比值。

| 人工RGB亮度乘数 | 裁剪图数 | TinyPlate整数整牌正确 | 固定开源教师整牌正确 |
|---|---:|---:|---:|
{offline_rows}

三个亮度档是同一批1200张图片的变体，不是3600个独立场景，也不等于真实夜景；该表检验识别器，不经过FPGA增强。1600个独立非车牌控制输入未产生合法格式车牌输出，但不证明所有未知场景都能拒识。数据省份严重偏向皖牌，苏牌等覆盖有限。教师公开预训练集与测试来源的重叠未知；不能称为全新盲测或由此宣称优于所有现有模型。归一化、轻量网络和暗化训练一起起作用，不能将差异全部归因于FPGA图像增强。

## 实板照片回放与一致性保护

预先按元数据顺序选择两张苏牌、两张皖牌、一张沪牌、一张京牌，每张原亮度与0.25倍亮度，共12输入，另加两种非车牌输入。全部是已裁剪的真实车牌照片回放；六个源图不是十二个独立场景。真值仅在电脑统计，固件只收到图像。全部结果保留，未挑选成功样本计算准确率。

原先只有全局亮度保护的版本：

| 亮度乘数 | 数量 | RAW正确 | NET正确 | AUTO正确 |
|---|---:|---:|---:|---:|
{oldtable}

观察到原图读对、增强后读错后，加入保守规则：RAW已有合法七位结果，而候选AUTO号码不同或无效，则最终图回退RAW，AUTO张量和号码也采用RAW。该规则不读取真值，不能判断RAW本身是否读错；可能阻止增强纠正一个格式合法的错误号码。这是工程保护策略，未重新训练增强网络。以下是同批工程回归，不能当作保护策略的新盲测。

当前带一致性保护的版本：

| 亮度乘数 | 数量 | RAW正确 | NET正确 | AUTO正确 |
|---|---:|---:|---:|---:|
{table}

两组非车牌三路均显示“--”。NET相对RAW新增正确{wins_losses['NET']['wins']}例、损失{wins_losses['NET']['losses']}例，AUTO新增正确{wins_losses['AUTO']['wins']}例、损失{wins_losses['AUTO']['losses']}例。此前用固定开源教师在电脑上复核相同板上缓存，正常组各3/6、暗化组各2/6，NET新增/损失各2例，原AUTO新增/损失各1例。因此**尚未建立增强在真实暗光下普遍提高车牌识别率的证据**；保护的价值是减少识别退化，画质及任务收益仍需真实场景验证。

| 输入 | 标注 | RAW | NET | AUTO | 回退 |
|---|---|---|---|---|---:|
{case_rows}

## 实板数值与速度

14个固定输入加一个真实摄像头帧，共{result['gray_bytes']}字节灰度输入、{result['normalized_bytes']}字节Q10张量、{result['score_count']}个CTC分数，与独立NumPy整数参考逐项完全相同，CTC token、三路显示字形、增强输出、最终保护像素和一致性决策均通过。额外保留第四路保护前候选张量，检查回退没有掩盖候选错误。摄像头帧采集降采样与LCD缓存也已核对。

连续{seconds:.3f}秒完成{frames}次画面更新，约**{hz:.2f}次/秒**，DMA错误0，超过预设4次/秒门槛。这是该现场场景下的完成更新频率，不是传感器帧率、最低速度保证或镜头到屏幕延迟；根据是否需要第三次推理和场景亮度会变化。实拍帧未放置清晰车牌，三路均“--”；目前没有完成真实摄像头正车牌验证。

## 使用与下一步

重新启动可双击download_jtag.cmd，或在PowerShell执行 `& 'E:\\Xilinx\\Vitis\\2020.2\\bin\\xsct.bat' 'E:\\FPGA_Enhance_Work\\camera_plate_guarded_20261026\\start_multinex_camera.tcl'`。需独立供电、JTAG连接、此前已验证的JTAG启动配置；本包与7020 V3.9、OV5640及800×480屏对应。下载完成以日志MULTINEX_CAMERA_STARTED为准，不能只看XSCT进程退出码。

JTAG下载内容断电失效；保持独立供电可运行，本次没有为车牌版写入SD。车牌对准测试图.png来自本轮公开回归照片，仅作摄像头正例通路检查，不算新泛化测试。将其显示在另一屏幕或打印，正对摄像头并让牌照填入绿框，先核对正常光，再固定相机改变照明；后续使用未参加训练和回放的新车牌场景，记录整牌正确率、拒识率、增强新增正确/损失、更新频率及真实延迟。自动车牌定位与绿牌应独立立项，避免把给定ROI识别描述成完整停车场系统。

训练和量化源码、协议、来源许可、全部回放缓存和失败结果已保存。恢复包不包含大型原始数据、CUDA安装器或完整Vitis工具链；重训还依赖原始数据目录与教师源码，重新编译还依赖本机已验证BSP。包内Python脚本保留本机绝对路径，异机复现实验需调整；JTAG启动入口使用相对包目录。原始模型和PL工程仍保存在原工作目录。
'''
    (BOARD/'车牌训练与实板验证.md').write_text(report,encoding='utf-8')
    handoff = HERE.parents[1]/'车牌项目当前进度_20261026.md'
    handoff.write_text(f'''# 车牌分支当前进度

当前板上：{BOARD}，mail版本8，plate contract4，实时摄像头已恢复，SD未写。源于用户“先做车牌”，替代继续优化单数字任务。报告：{BOARD/'车牌训练与实板验证.md'}。

模型SHA256：{proof['model_sha256']}；ELF：{offline['elf_sha256']}。七位蓝牌固定ROI(8,72,384,96)，ARM NEON跑识别，PL原Multinex跑增强。约{hz:.2f}次/秒，14回放+1摄像头数值检查通过。真实摄像头正车牌尚未测试，整图自动检测和八位绿牌未实现。增强普遍提升识别的结论尚未建立。旧单数字、无一致性保护车牌版本和SD保留。

下一步：实际新车牌在固定框内的摄像头验证、固定场景正常/暗光配对评测；不得用已有回放正确率替代真实夜景泛化。无需继续安装或重新训练已验收模型。
''',encoding='utf-8')
    # The redirected finalizer log is still open and changes after this manifest is written.
    files = sorted(p for p in BOARD.rglob('*') if p.is_file() and not any(x in p.relative_to(BOARD).parts for x in ['obj','.Xil','__pycache__']) and p.name not in ['runtime_manifest.json','release.json','finalize.log'])
    write(BOARD/'runtime_manifest.json',[dict(path=p.relative_to(BOARD).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in files])
    archive = BASE/'plate_guarded_verified_20261026_r1.zip'
    assert not archive.exists(), 'Preserve existing release'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in files+[BOARD/'runtime_manifest.json']:
            z.write(p,p.relative_to(BOARD).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
    write(BOARD/'release.json',dict(archive=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,crc_ok=True))
    print('PLATE_VERIFIED_ARCHIVED',hz,json.dumps(summary,ensure_ascii=True),str(archive),sha(archive),flush=True)

if __name__ == '__main__':
    main()
