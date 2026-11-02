"""Finalize measured upgrade, keeping all errors and restoring live operation."""
from pathlib import Path
import json,csv,zipfile,shutil
from recognition_upgrade_common import ROOT,BASE,sha,write
BOARD=BASE/'multinex_camera_digit_upgrade_20261026'
HERE=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def main():
    offline=read(BOARD/'offline_camera.json');held=read(BOARD/'classifier_heldout_results.json');freeze=read(BOARD/'classifier_frozen.json')
    proof=read(BOARD/'classifier_numeric_proof.json');norm=read(ROOT/'normalization_proof/complete.json')
    assert held['accepted'] and held['model_sha256']==freeze['sha256']==proof['model_sha256']
    assert sha(BOARD/'camera.elf')==offline['elf_sha256'] and sha(BOARD/'camera.bit')==offline['bit_sha256']
    assert sha(BOARD/'app_src/cnn_weights.h')==proof['weights_header_sha256']
    assert sha(BOARD/'app_src/digit_arm_kernel.h')==proof['kernel_sha256']
    assert sha(BOARD/'app_src/digit_normalization.h')==norm['header_sha256']
    rows=[]
    for c in read(BOARD/'digit_cases.json'):
        f=BOARD/'board_digit'/c['id'];a=read(f/'digit_validation.json');b=read(f/'validation.json')
        assert a['logits_exact'] and a['gray_exact'] and a['display_digits_exact'] and a['input_contract']==2
        assert a['model_sha256']==held['model_sha256']
        assert b['rgb_output_exact'] and b['lcd_pixels_exact'] and b['source_kind']=='host_photo'
        assert sha(f/'input32.bin')==c['input_sha256']
        rows.append(dict(id=c['id'],truth=c['truth'],scale=c['scale'],predictions=a['predictions'],alpha=b['protection']['alpha'],raw_seconds=a['raw_recognition_seconds'],other_seconds=a['other_recognition_seconds']))
    live=read(BOARD/'live_snapshot/digit_validation.json');lv=read(BOARD/'live_snapshot/validation.json')
    assert live['logits_exact'] and live['input_contract']==2 and live['model_sha256']==held['model_sha256']
    assert lv['source_kind']=='live_camera' and lv['capture_reduction_exact'] and lv['lcd_pixels_exact'] and lv['rgb_output_exact']
    with (BOARD/'live_cadence.csv').open() as f:cad=list(csv.DictReader(f))
    assert len(cad)==11 and all(int(r[k])==0 for r in cad for k in ['read_error','write_error','error'])
    sec=(int(cad[-1]['elapsed_ms'])-int(cad[0]['elapsed_ms']))/1000;frames=int(cad[-1]['sequence'])-int(cad[0]['sequence']);hz=frames/sec
    assert sec>=9.5 and hz>=6.5,'Performance regression; do not finalize accepted runtime'
    photo=[r for r in rows if r['truth'] is not None];groups=[]
    for scale in [1.,.25,.125]:
        rs=[r for r in photo if r['scale']==scale];groups.append(dict(scale=scale,n=len(rs),correct=[sum(r['predictions'][i]==r['truth'] for r in rs) for i in range(3)]))
    gains={name:dict(wins=sum(r['predictions'][0]!=r['truth'] and r['predictions'][i]==r['truth'] for r in photo),losses=sum(r['predictions'][0]==r['truth'] and r['predictions'][i]!=r['truth'] for r in photo)) for i,name in [(1,'NET'),(2,'AUTO')]}
    fresh=read(ROOT/'run03/fresh_photos/results.json')
    result=dict(status='UPGRADED_RECOGNIZER_OFFLINE_ACCEPTED_AND_BOARD_NUMERICALLY_VERIFIED',heldout_recognizer_accepted=True,real_scene_reliability_established=False,fresh_photo_check=fresh,heldout_results=held,model_sha256=held['model_sha256'],bit_sha256=sha(BOARD/'camera.bit'),elf_sha256=sha(BOARD/'camera.elf'),live_update_hz=hz,completed_frames=frames,measured_seconds=sec,numeric_gray_bytes=(len(rows)+1)*2352,numeric_logits=(len(rows)+1)*33,normalizer_proof=norm,cases=rows,photo_by_scale=groups,enhancement_recognition_wins_losses=gains,live_classification=live,live_visual_observation='No clearly visible digit in the captured live ROI, yet all views predicted5. Unknown-input rejection remains unreliable; numeric matching is not accuracy evidence.',classification_processor='ARM Cortex-A9 #0',enhancement_processor='PL unchanged r4d Multinex network',sd_written=False,limitations=['Given manually selected single-digit ROI; no automatic scene detection or plate/text OCR.','Test sets measure recognition; they do not establish enhancement benefit.','Three old source photos with synthetic gain are regression, not an independent low-light dataset.','Measured display cadence is not sensor FPS or end-to-end latency.','No real paired camera low-light scene captured in this phase.','Supplemental new photos: new1/3 vs old2/3; stone relief/occlusion still fail.','Live ROI without a clearly visible digit still predicted5; unknown-input rejection not established.'])
    write(BOARD/'board_deployed.json',result)
    comparison=[]
    names={'svhn':'SVHN官方测试','chars':'Chars74K未见过的原始场景','fonts':'未见过的字体家族（合成）','mnist':'MNIST官方测试','background':'平坦/噪声背景控制'}
    for key,r in held['results'].items():
        comparison.append('| '+names[key]+f' | {r["n"]} | '+ ' | '.join(f'{100*r[k]["accuracy"]:.2f}%' for k in ['old_raw','old_normalized','new_normalized'])+' |')
    board_table='\n'.join(f'| {r["scale"]:g} | {r["n"]} | '+ ' | '.join(map(str,r['correct']))+' |' for r in groups)
    text=f'''# 本轮识别模型改进与实板验证

新版已通过预先设置的离线验收，并在真实开发板上完成计算、图像和显示核对。SD卡未修改，旧版本和恢复包保留。

**这仍是比赛原型，实景泛化尚未完成：三张额外新门牌照片，旧版2/3、新版1/3。不能只展示下面的标准数据集提升而省略这个结果。**

## 改了什么

识别器仍是两层卷积的小CNN，卷积通道8/16保持，分类隐藏层从32扩大为{proof['hidden']}；增加一致的对比度预处理。补充真实场景字符、不同字体和手写数字训练，保留原有街景数据。使用同一权重、同一预处理分别识别RAW原图、NET纯增强结果、AUTO最终保护结果，不把真值传给板卡。

训练/验证/评测分开。Chars74K按原始照片分组，字体按家族分组；MNIST、SVHN官方评测图像不参与梯度训练，训练轮次只按验证集挑选。前两次不合格结果保留：其中64隐藏单元候选的字符109/120，未达到110/120门槛，未部署。

本轮读取过前一候选的汇总测试反馈，因此下面是固定评测集复测，**不能称为一次新的盲测或无偏泛化估计**。没有按这些测试图片的个别错误训练，也没有在测试集上比较训练轮次后挑权重。最终候选先按验证集固定，再复测，原数值验收门槛未降低。后续仍需要新的实际摄像头场景验证。

Chars74K来自[作者数据页](https://teodecampos.github.io/chars74k/)，应按作者要求引用de Campos、Babu、Varma，VISAPP2009。Windows字体只在本地渲染，包中不分发字体文件。

## 离线测试，三个控制组

| 测试组 | 数量 | 原模型＋原输入 | 原模型＋新预处理 | 新模型＋新预处理 |
|---|---:|---:|---:|---:|
{chr(10).join(comparison)}

这里是给定数字区域的分类准确率；Chars74K是字符裁剪，不是整幅场景自动找数字。合成字体、手写数字、背景控制分别统计。数据分组不能保证公开预训练数据与所有后续图片完全无重叠；原始数据来源/划分见训练协议。背景控制不证明可拒绝所有未知物体。

额外门牌检查在权重固定后运行。预先选定8个标题，5个源站HTTP429暂时无法下载；其余3张先人工标注矩形数字区域，再统一推理。全部结果及署名许可见external_photo_check。新版在蓝色标牌6上正确，石刻2和被电线遮挡的2识别为背景；旧版在其中两张正确。未据此调裁剪、训练权重或筛掉失败结果。样本只覆盖数字2、6，不能作为实景总体准确率。

## 实板检查与性能

CPU C和NumPy对比预处理{norm['cases']}组、{norm['bytes']}字节全相同；候选原生C与NumPy共{proof['cases']}组/{proof['logits']}分数全相同，并记录所有层整数累加界限。

开发板{len(rows)}个照片/数值输入加一个真实摄像头帧，合计{result['numeric_gray_bytes']}字节预处理结果、{result['numeric_logits']}个分类分数全部一致；增强、保护、LCD图像区域和显示数字也逐项核对。摄像头帧另外核对实际采集缓冲与2×2降采样。测试结束后恢复实时摄像头。

连续{sec:.3f}秒完成{frames}次增强/识别/显示更新，约{hz:.2f}次/秒，DMA错误为0。这是完成画面更新频率，不能代替镜头到屏幕延迟测量。

本次真实摄像头截图中，绿框内没有清晰可见的数字，但三路均显示5；这些输出与整数参考完全一致，却不代表识别正确。这也暴露了未知输入拒识不足，不能把“有数字输出”当成检测到了数字。

## 三张旧门牌回归，保留全部结果

| 人工RGB亮度乘数 | 图数 | RAW正确 | NET正确 | AUTO正确 |
|---|---:|---:|---:|---:|
{board_table}

三个亮度档来自相同三张照片，不是九个独立场景，人工暗化也不是实拍夜景或照度测量。NET比RAW新增正确{gains['NET']['wins']}例、损失{gains['NET']['losses']}例；AUTO新增正确{gains['AUTO']['wins']}例、损失{gains['AUTO']['losses']}例。识别器变好与增强是否提高识别率是两个问题；当前数据不足以证明增强在真实暗光下普遍提高识别。

## 板上职责与使用

FPGA PL负责摄像头/显示数据通路及Multinex图像增强神经网络；ARM负责初始化、缓冲与保护逻辑、数字ROI预处理、整数CNN识别及界面组织。不能把当前作品说成所有神经网络都在FPGA逻辑里。

屏幕左原图、右最终图；底部RAW/NET/AUTO是同一数字区域的三路识别。默认绿框为400×240处理画面内(144,64)、112×112区域，需把一个数字放进框里。当前不做整图物体定位、整行文字或车牌识别。

启动入口start_multinex_camera.tcl，适用于当前配套硬件/ELF。JTAG版本断电失效；本轮未生成或写入SD启动内容。离线固定图片测试记录在board_digit，真实摄像头记录在live_snapshot。
'''
    (BOARD/'本轮模型改进与实板验证.md').write_text(text,encoding='utf-8')
    (ROOT/'本轮模型改进与实板验证.md').write_text(text,encoding='utf-8')
    # Keep pre-deployment records as history, with an explicit current-status pointer.
    ready=read(BOARD/'ready_for_board.json');ready['historical_before_deployment']=True;ready['superseded_by']='board_deployed.json';write(BOARD/'ready_for_board.json',ready)
    for p in [BOARD/'本轮离线改进结果.md',ROOT/'本轮离线改进结果.md']:
        previous=p.read_text(encoding='utf-8')
        banner='> 历史记录：此报告生成于首次成功上板前。当前已完成上板，请看[本轮模型改进与实板验证](本轮模型改进与实板验证.md)。\n\n'
        if not previous.startswith('> 历史记录'):p.write_text(banner+previous,encoding='utf-8')
    shutil.copy2(HERE/'finish_upgrade_camera.py',BOARD/'finish_upgrade_camera.py')
    files=[p for p in BOARD.rglob('*') if p.is_file() and 'obj' not in p.relative_to(BOARD).parts and p.name not in ['runtime_manifest.json','release.json']]
    write(BOARD/'runtime_manifest.json',[dict(path=p.relative_to(BOARD).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(files)])
    archive=BASE/'multinex_recognition_upgrade_verified_20261026.zip';assert not archive.exists()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in files+[BOARD/'runtime_manifest.json']:z.write(p,p.relative_to(BOARD).as_posix())
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    write(BOARD/'release.json',dict(archive=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,crc_ok=True))
    print('UPGRADE_VERIFIED_ARCHIVED',hz,str(archive),sha(archive),flush=True)
if __name__=='__main__':main()
