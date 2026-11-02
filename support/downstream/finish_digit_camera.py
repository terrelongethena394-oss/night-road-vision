"""Archive a numerically verified recognition comparison build, retaining errors."""
from pathlib import Path
import json,csv,hashlib,zipfile,shutil
ROOT=Path('E:/FPGA_Enhance_Work/multinex_camera_digit_fast_20261026')
BASE=ROOT.parent
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
    offline=read(ROOT/'offline_camera.json');proof=read(ROOT/'classifier_numeric_proof.json')
    assert offline['recognition'] and offline['normal_protection']
    assert proof['status']=='NATIVE_C_NUMPY_ALL_LOGITS_EXACT' and proof['model_sha256']=='07478560652fdd4c73e6347f8494cdceecd90cda3f62d8705cbb229babc32493'
    assert sha(ROOT/'camera.elf')==offline['elf_sha256'] and sha(ROOT/'camera.bit')==offline['bit_sha256']
    assert sha(ROOT/'camera.bit')==read(BASE/'multinex_camera_protected_fast_20261026/board_deployed.json')['bit_sha256']
    assert read(ROOT/'classifier_width_proof.json')['header_matches_bound_weights']
    cases=read(ROOT/'digit_cases.json');records=[]
    for c in cases:
        folder=ROOT/'board_digit'/c['id'];a=read(folder/'digit_validation.json');b=read(folder/'validation.json')
        assert a['status']=='ACTUAL_ARM_CLASSIFIER_ALL_LOGITS_EXACT' and a['logits_exact'] and a['gray_exact'] and a['display_digits_exact']
        assert b['status']=='ACTUAL_HOST_PHOTO_ENHANCEMENT_EXACT' and b['rgb_output_exact'] and b['lcd_pixels_exact']
        assert a['roi']==dict(zip(('x','y','size'),c['roi']))
        assert b['read_dma_error']==b['write_dma_error']==0
        assert sha(folder/'input32.bin')==c['input_sha256']
        row=dict(id=c['id'],truth=c['truth'],group=c['group'],scale=c['scale'],predictions=a['predictions'],
            alpha=b['protection']['alpha'],raw_recognition_seconds=a['raw_recognition_seconds'],
            other_recognition_seconds=a['other_recognition_seconds'],physical_cnn_evaluations=a['physical_cnn_evaluations'])
        if c['truth'] is not None:row['correct']=[p==c['truth'] for p in row['predictions']]
        records.append(row)
    live=read(ROOT/'live_snapshot/digit_validation.json');live_base=read(ROOT/'live_snapshot/validation.json')
    assert live['status']=='ACTUAL_ARM_CLASSIFIER_ALL_LOGITS_EXACT' and live['display_digits_exact']
    assert live_base['source_kind']=='live_camera' and live_base['capture_reduction_exact'] and live_base['rgb_output_exact'] and live_base['lcd_pixels_exact']
    with (ROOT/'live_cadence.csv').open() as f:cadence=list(csv.DictReader(f))
    assert len(cadence)==11 and all(int(r[k])==0 for r in cadence for k in ('read_error','write_error','error'))
    seconds=(int(cadence[-1]['elapsed_ms'])-int(cadence[0]['elapsed_ms']))/1000
    frames=int(cadence[-1]['sequence'])-int(cadence[0]['sequence']);assert seconds>9.5 and frames>20
    photos=[r for r in records if r['truth'] is not None];summary=[]
    for scale in (1.,.25,.125):
        rows=[r for r in photos if r['scale']==scale]
        summary.append(dict(scale=scale,n=len(rows),correct={name:sum(r['correct'][i] for r in rows) for i,name in enumerate(('RAW','NET','AUTO'))}))
    gains={}
    for i,name in ((1,'NET'),(2,'AUTO')):
        gains[name]=dict(wins_over_raw=sum(not r['correct'][0] and r['correct'][i] for r in photos),
            losses_to_raw=sum(r['correct'][0] and not r['correct'][i] for r in photos))
    result=dict(status='RECOGNITION_COMPARISON_BUILD_NUMERICALLY_VERIFIED',recognizer_accuracy_accepted=False,
        views=['RAW','NET','AUTO'],classification_processor='ARM Cortex-A9 #0; RAW overlaps PL enhancement',
        enhancement_processor='PL, unchanged r4d Multinex neural core',same_weights_all_views=True,
        photo_cases=len(photos),source_photos=3,numeric_cases=len(records),photo_accuracy_by_scale=summary,gains=gains,
        cases=records,live_classification=live,live_update_hz=frames/seconds,measured_seconds=seconds,completed_frames=frames,
        numeric_gray_bytes=(len(records)+1)*2352,numeric_logits=(len(records)+1)*33,
        model_sha256=proof['model_sha256'],bit_sha256=sha(ROOT/'camera.bit'),elf_sha256=sha(ROOT/'camera.elf'),
        camera_shape=[480,800],enhancement_shape=[240,400],live_roi=[144,64,112],sd_written=False,
        limitations='Fixed single-digit ROI; not automatic detection, object recognition or plate OCR. Three previously seen manually annotated photos and synthetic brightness variants; not independent low-light validation. All errors retained. Correct numeric implementation does not establish recognition accuracy or enhancement benefit.')
    (ROOT/'board_deployed.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    table='\n'.join(f'| {r["scale"]:g} | {r["n"]} | {r["correct"]["RAW"]} | {r["correct"]["NET"]} | {r["correct"]["AUTO"]} |' for r in summary)
    doc=f'''# 数字识别对比验证版

当前已接通图像增强和数字识别。FPGA PL仍执行同一Multinex增强网络；ARM Cortex-A9 #0运行冻结的26731参数整数CNN，在同一帧、同一ROI、同一权重下比较RAW、NET、AUTO。原图识别与PL增强重叠，若AUTO的28×28灰度张量与其他一路完全相同则复用其分数，避免额外耗时。

**这版是识别评估工具，当前识别准确率尚未达到可靠演示要求，不宣称增强普遍提高识别率。**

## 屏幕怎么读

左右绿色框为同一数字区域。左侧原图，右侧保护后图像，KEEP/ENH/MIX含义保持。底部RAW为原图识别、NET为内部纯网络输出识别、AUTO为最终保护后图像识别。分类结果0–9，训练背景类10显示“-”；背景类不保证能拒绝所有未知物品。

把一个数字放入绿框内观察；当前不自动寻找数字、不识别任意物品，也不是车牌OCR。默认live ROI是400×240网络图中的(144,64,112,112)，下采样为28×28灰度。

## 数值/接口核对

本地C与独立NumPy219输入/2409分数全精确，此处包含已有训练数值样本，只用于算术一致性，不是新准确率测试。依据所有RGB8输入的绝对累加范围，conv1/conv2/fc1用32位安全，fc2保持64位；权重/激活/舍入不改。

实板{len(records)}个固定输入及一个真实摄像头帧，灰度张量共{result['numeric_gray_bytes']}字节、分类分数共{result['numeric_logits']}个全部核对。每张实板照片还核对完整增强、保护结果、LCD像素和显示数字字形。真值只保存在电脑统计文件，没有传给板上分类程序。

持续{seconds:.3f}秒完成{frames}次增强/识别/显示更新，约**{frames/seconds:.2f}次/秒**，DMA无错误。不是传感器帧率或精确镜头到屏幕延迟；加入识别后的实际开销以本次数据为准。

## 已有门牌回归，错误全部保留

三张以前看过的原始Wikimedia照片（8、5、8），整张等比缩放/letterbox，保留原上下文，人工标注ROI映射到画面。黑边会影响全帧统计；测试不是自动定位，也不是新盲测。每张有原亮度、乘0.25、乘0.125版本；后两者是人工暗化，不是实拍夜间或实测lux。

| RGB亮度乘数 | 图片数 | RAW正确 | NET正确 | AUTO正确 |
|---|---:|---:|---:|---:|
{table}

三种亮度来自相同三张照片，不是九个独立场景，不能据此估计一般场景准确率。NET相对RAW新增正确{gains['NET']['wins_over_raw']}例、损失{gains['NET']['losses_to_raw']}例；AUTO新增正确{gains['AUTO']['wins_over_raw']}例、损失{gains['AUTO']['losses_to_raw']}例。当前门牌字体/场景泛化仍不足，需改进识别器与数据；没有将失败样本剔除或换成特制数字来宣称成功。

下一步先准备未参与拟合的真实门牌/打印数字/实拍暗光有标签数据，改进识别器并保留正常光回归，随后再判断增强是否有稳定收益。已有被拒收的保持训练CNN未部署，本版使用原冻结权重。

## 保存与恢复

SD卡未写，旧纯增强版和恢复包保留。当前是易失JTAG运行，断电后不自动恢复。入口start_multinex_camera.tcl；board_digit为电脑传入照片的实板记录，live_snapshot是真实摄像头数据。数字识别在ARM运行，不能写成所有神经网络都在PL上。
'''
    (ROOT/'识别对比验证结果.md').write_text(doc,encoding='utf-8')
    (ROOT/'README.md').write_text('# 已上板的数字识别对比验证版\n\n见[识别对比验证结果](识别对比验证结果.md)。\n\n计算路径已验证；当前识别效果尚不可靠，不得当作成熟识别系统。SD未修改。\n',encoding='utf-8')
    shutil.copy2(HERE/'finish_digit_camera.py',ROOT/'finish_digit_camera.py')
    files=[p for p in ROOT.iterdir() if p.is_file() and p.suffix in
        ('.bit','.elf','.xsa','.tcl','.py','.json','.md','.csv','.spec') and p.name not in ('runtime_manifest.json','release.json')]
    for name in ('app_src','digit_inputs','board_digit','live_snapshot'):
        files.extend(p for p in (ROOT/name).rglob('*') if p.is_file())
    files=sorted(set(files));manifest=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in files]
    (ROOT/'runtime_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    archive=BASE/'multinex_digit_comparison_verified_20261026.zip';assert not archive.exists()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in files:z.write(p,p.relative_to(ROOT).as_posix())
        z.write(ROOT/'runtime_manifest.json','runtime_manifest.json')
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    (ROOT/'release.json').write_text(json.dumps(dict(archive=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,crc_ok=True),indent=2),encoding='utf-8')
    print('DIGIT_COMPARISON_BUILD_ARCHIVED',frames/seconds,json.dumps(summary),sha(archive),flush=True)
if __name__=='__main__':main()
