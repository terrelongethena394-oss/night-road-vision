"""Keep real-photo failures and sources; never substitute PC predictions."""
from pathlib import Path
import csv,hashlib,json,shutil,zipfile

HERE=Path(__file__).resolve().parent
ROOT=Path('E:/FPGA_Enhance_Work/real_scene_test_scaled_20261025')
DATA=Path('E:/FPGA_Enhance_Work/real_scene_test_20261025')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    manifest=json.loads((ROOT/'case_manifest.json').read_text(encoding='utf-8'))
    cases={r['id']:r for r in manifest['cases']}
    rows=list(csv.DictReader((ROOT/'board_batch_33/board_results.csv').open(encoding='ascii')))
    assert len(rows)==33 and {r['id'] for r in rows}==set(cases)
    assert 'FIXED_IMAGE_BATCH_FINISHED cases=33' in (ROOT/'board_batch_33.log').read_text(encoding='utf-8',errors='replace')
    for r in rows:
        assert int(r['fnv_board'])==int(r['fnv_expected'])==cases[r['id']]['fnv']
        assert int(r['dma_errors'])==0
        assert sha(Path(cases[r['id']]['file']))==cases[r['id']]['sha256']
    assert (ROOT/'board_batch_33/first_input_readback.bin').read_bytes()==Path(cases[rows[0]['id']]['file']).read_bytes()
    summaries=[]
    for group in ['SVHN_first3_per_class','real_photo_manual_roi']:
        subset=[r for r in rows if cases[r['id']]['group']==group]
        summaries.append(dict(group=group,n=len(subset),raw_correct=sum(r['truth']==r['raw_board'] for r in subset),
             enhanced_correct=sum(r['truth']==r['enh_board'] for r in subset),
             raw_background_predictions=sum(int(r['raw_board'])==10 for r in subset),
             enhanced_background_predictions=sum(int(r['enh_board'])==10 for r in subset)))
    mismatch=[]
    for r in rows:
        c=cases[r['id']];fields=[]
        for k in ['raw','enh']:
            if int(r[k+'_board'])!=c[k+'_expected']:fields.append(k+'_label')
            if int(r[k+'_margin'])!=c[k+'_margin']:fields.append(k+'_margin')
        if fields:mismatch.append(dict(id=r['id'],fields=fields))
    for name in ['system_wrapper.bit','camera_digit.xsa','ps7_init.tcl']:
        assert (ROOT/'board'/name).read_bytes()==(Path('E:/FPGA_Enhance_Work/camera_nn_digit_candidate_20261023')/name).read_bytes()
    assert sha(Path('E:/FPGA_Enhance_Work/camera_nn_sd_20261018/BOOT.BIN'))=='e0d606c4c623463e01e6b4123ad127a63d0103c046674514bec01891e9ad67d3'
    status=dict(date='2026-10-25',stage='REAL_PHOTOGRAPHS_TESTED_CURRENT_MODEL_NOT_ACCEPTED_FOR_REAL_SCENES',
        input_count=33,summary=summaries,artificial_darkening=False,thresholding_or_inversion=False,
        model_or_weights_changed=False,camera_used=False,sd_written=False,
        each_input_checksum_verified=True,first_input_full_byte_readback_verified=True,vdma_error_bits=0,
        truth_sent_to_board=False,all_failed_samples_retained=True,software_reference_mismatches=mismatch,
        preprocessing_bug=dict(initial_unscaled_run_invalid=True,invalid_directory=str(DATA),
             fix='Explicitly resize small images up to 224x224; regression probe checked content at edges.',
             valid_directory=str(ROOT)),
        limitations=['SVHN inputs are pre-cropped 32x32 photographs, not full-scene detection.',
            'Three source photographs use manually annotated ROI; positions were not found by an FPGA detector.',
            'These are real photographs, not a dedicated natural-nighttime benchmark.',
            'Current recognition weights were trained on MNIST/printed digits, not SVHN or real photographs.',
            'Integer board/reference numerical differences remain open; scores are not calibrated probabilities.',
            'PC_REFERENCE PNG files are software previews, not captured FPGA enhanced RGB output.'])
    (ROOT/'hardware_test_status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    shutil.copytree(DATA/'original_photos',ROOT/'original_photos',dirs_exist_ok=True)
    shutil.copy2(DATA/'source_manifest.json',ROOT/'svhn_source_manifest.json')
    with (ROOT/'真实照片结果.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['图片编号','真值','原图板上结果','增强后板上结果','原图是否正确','增强后是否正确','来源类别'])
        for r in rows:w.writerow([r['id'],r['truth'],r['raw_board'],r['enh_board'],r['truth']==r['raw_board'],r['truth']==r['enh_board'],cases[r['id']]['group']])
    sources=json.loads((DATA/'original_photos/sources.json').read_text(encoding='utf-8'))
    credits='\n'.join('- ['+s['title']+']('+s['page']+')；作者 '+s['metadata'].get('Artist',{}).get('value','See source')+'；'+s['metadata'].get('LicenseShortName',{}).get('value','See source')+'；本次进行了ROI裁剪、缩放及RGB565转换。' for s in sources)
    table='| 来源 | 数量 | 原图识别正确 | 增强后识别正确 |\n|---|---:|---:|---:|\n'
    for r in summaries:table+=f'| {r["group"]} | {r["n"]} | {r["raw_correct"]} | {r["enhanced_correct"]} |\n'
    doc='''# 真实照片测试记录

2026-10-25，使用原来的FPGA位流、增强模型和数字识别权重，在板上实测33张真实照片。没有用人工黑底白字替代照片，没有反色、二值化、去背景或人工压暗；保留原有颜色、纹理、阴影和背景，仅做尺寸适配、必要留边和RGB565格式转换。

## 图片是什么

30张来自SVHN测试集，每个数字0–9按测试集索引取最早的3张，在计算模型预测之前固定。SVHN来源是真实街景门牌，裁剪版本原生32×32，已明确放大至224×224识别框；放大不会产生新的真实细节。标签指中心目标数字，邻近数字可能同时出现在图中，不统计整串数字识别。

另有3张Wikimedia实拍门牌（8、5、8），完整原照片保存在original_photos。用于识别的ROI由人工在看过原照片后、计算预测前标出并固定，坐标记录在case_manifest.json；这一步不是FPGA自动定位。不能把本测试写成整场景自动寻找数字、整车牌或任意物体识别。

SVHN原站下载不可用时使用镜像，下载文件MD5与torchvision官方实现一致。来源、下载错误及SHA256保留在svhn_source_manifest.json。只取测试数据，不对本批图片训练或挑选识别成功样例。

## 板上结果

'''+table+'''
完整33张结果包含全部失败，见真实照片结果.csv及board_batch_33/board_results.csv。输出10表示识别器的背景类，在这些有数字的照片中输出背景就是识别失败，不能解释为“照片中没有数字”。

当前识别器不能通过这批真实照片验收，不能用先前理想化黑底白字结果代表真实场景能力。电脑参考也表现很差，说明当前训练分布与照片差别很大；同时此前已发现的板上定点数值差异仍未完全解决。需要保留当前基线，先解决数值一致性，再用独立训练集训练适合真实场景的识别器，以未参与训练和选择的照片验收。仅提高亮度不会自动获得真实场景识别能力，也不能由这批结果断言增强有益。

每张输入已通过板上数据校验，第一张整帧读回与文件逐字节一致；VDMA错误位0。增强与分类实际在PL上执行，ARM只控制缓冲和读取同帧结果，没有向板卡发送真值或电脑预测。

这里不是天然夜景专用数据集。若下一步评估真实低照度，应另加入自然暗光、固定曝光拍摄的独立照片，不能把亮度滑块或合成乘系数当作实测照度。

## 预处理错误的处理

第一次准备SVHN时，thumbnail没有放大32×32小图，数字在框内过小，该轮目录已标INVALID_UNSCALED_INPUTS.json，结果不计入本表。之后改为显式放大并检查内容覆盖识别框，重新准备33张、重新上板，才形成这里的有效记录。旧轮保留用于追溯，没有覆盖或混入本轮。

## 怎么看和继续使用

- 真实照片预览.png：33张有效输入ROI及真值；GT是目标数字，不是模型预测。
- original_photos：3张完整实拍原图、作者和许可信息。
- inputs：送入板卡的PNG和BGR888；左右两半是同一个场景。
- pc_reference_previews：电脑定点增强参考，名称带PC_REFERENCE；不是板上增强RGB回读。
- hardware_test_status.json：实测状态、失败及未解决问题。

当前板卡运行固定图片程序，摄像头不参与输入，SD未改。重新供电后可运行本目录start_fixed_image.tcl；发图脚本run_fixed_image.tcl与原固定图片流程相同。示例（输出目录名请使用新的名字）：

```powershell
& 'E:\\Xilinx\\Vitis\\2020.2\\bin\\xsct.bat' 'E:\\FPGA_Enhance_Work\\real_scene_test_scaled_20261025\\run_fixed_image.tcl' 'E:/FPGA_Enhance_Work/real_scene_test_scaled_20261025/manual_photo5_01' commons_1_roi
```

恢复摄像头数字识别版本仍使用原候选camera_nn_digit_candidate_20261023/download_digit_jtag.tcl。模型文件和原先摄像头候选均未改。

## 数据来源与图片署名

SVHN：[原始数据项目](http://ufldl.stanford.edu/housenumbers/)，[作者论文](https://ai.stanford.edu/~twangcat/papers/nips2011_housenumbers.pdf)，[torchvision校验值及标签映射实现](https://github.com/pytorch/vision/blob/main/torchvision/datasets/svhn.py)。SVHN原标签10映射为数字0，绝不是本模型的背景类10。

'''+credits+'\n\n原照片及相应派生图片保留各来源的许可与署名，法国数字5照片及其裁剪派生图使用CC BY-SA4.0。原始SVHN MAT（约64MB）保留在本机下载目录，不重复装入结果包。\n'
    (ROOT/'真实照片测试说明.md').write_text(doc,encoding='utf-8')
    (ROOT/'sources').mkdir(exist_ok=True)
    for name in ['prepare_real_cases.py','finish_real_cases.py']:shutil.copy2(HERE/name,ROOT/'sources'/name)
    for name in ['digit_model.py','prepare_digit_hls.py','prepare_fixed_cases.py']:shutil.copy2(HERE/name,ROOT/'sources'/name)
    files=[p for p in ROOT.rglob('*') if p.is_file() and p.suffix not in ['.bin','.part'] and '.Xil' not in p.parts]
    package_manifest={p.relative_to(ROOT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in files}
    (ROOT/'package_manifest.json').write_text(json.dumps(package_manifest,indent=2),encoding='utf-8')
    archive=ROOT.parent/'real_scene_test_scaled_20261025_ready.zip';assert not archive.exists()
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files+[ROOT/'package_manifest.json']:z.write(p,p.relative_to(ROOT))
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    print('REAL_PHOTO_TEST_COMPLETE',json.dumps(summaries),'archive_bytes',archive.stat().st_size,flush=True)

if __name__=='__main__':main()
