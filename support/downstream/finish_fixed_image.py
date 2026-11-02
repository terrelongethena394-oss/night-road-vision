"""Archive actual fixed-image board measurements, including all mismatches."""
from pathlib import Path
import csv,hashlib,json,shutil,zipfile

HERE=Path(__file__).resolve().parent
ROOT=Path('E:/FPGA_Enhance_Work/fixed_image_test_20261025')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    cases=json.loads((ROOT/'case_manifest.json').read_text(encoding='utf-8'))['cases']
    by_id={x['id']:x for x in cases}
    rows=list(csv.DictReader((ROOT/'batch_38/board_results.csv').open(encoding='ascii')))
    assert len(rows)==38 and {r['id'] for r in rows}==set(by_id)
    assert 'FIXED_IMAGE_JTAG_READY no_camera=1 s2mm_run=0 genlock=0 parking=1' in (ROOT/'start_fixed_image.log').read_text(encoding='utf-8',errors='replace')
    assert 'FIXED_IMAGE_BATCH_FINISHED cases=38' in (ROOT/'batch_38.log').read_text(encoding='utf-8',errors='replace')
    assert 'FIXED_IMAGE_BATCH_FINISHED cases=1' in (ROOT/'display_demo8_dim.log').read_text(encoding='utf-8',errors='replace')
    for r in rows:
        c=by_id[r['id']]
        assert int(r['fnv_expected'])==int(r['fnv_board'])==c['fnv']
        assert sha(Path(c['file']))==c['sha256'] and int(r['dma_errors'])==0
    first=by_id[rows[0]['id']]
    assert (ROOT/'batch_38/first_input_readback.bin').read_bytes()==Path(first['file']).read_bytes()
    mismatches=[]
    for r in rows:
        c=by_id[r['id']]
        fields=[]
        for key in ['raw','enh']:
            if int(r[key+'_board'])!=c[key+'_expected']:fields.append(key+'_label')
            if int(r[key+'_margin'])!=c[key+'_margin']:fields.append(key+'_margin')
        if fields:mismatches.append(dict(id=r['id'],fields=fields,board=r,reference=c))
    summary=[]
    for alpha in [1.0,0.125,0.0625]:
        group=[r for r in rows if by_id[r['id']]['group']=='heldout_font_digits' and by_id[r['id']]['alpha']==alpha]
        assert len(group)==10
        summary.append(dict(alpha=alpha,n=10,raw_correct=sum(int(r['raw_board'])==int(r['truth']) for r in group),
             enhanced_correct=sum(int(r['enh_board'])==int(r['truth']) for r in group)))
    candidate=Path('E:/FPGA_Enhance_Work/camera_nn_digit_candidate_20261023')
    for name in ['system_wrapper.bit','camera_digit.xsa','ps7_init.tcl']:
        assert (ROOT/'board'/name).read_bytes()==(candidate/name).read_bytes()
    assert sha(Path('E:/FPGA_Enhance_Work/camera_nn_sd_20261018/BOOT.BIN'))=='e0d606c4c623463e01e6b4123ad127a63d0103c046674514bec01891e9ad67d3'
    status=dict(date='2026-10-25',stage='FIXED_IMAGES_INJECTED_AND_MEASURED_NUMERIC_REFERENCE_DIFFERENCES_OPEN',
        camera_initialized=False,camera_s2mm_running=False,identical_left_right_input=True,
        enhancement_and_recognition_computed_on_PL=True,truth_or_reference_predictions_sent_to_board=False,
        sd_written=False,same_fpga_bitstream=True,arm_image_app_sha256=sha(ROOT/'image_test.elf'),
        input_cases=38,each_input_fnv_verified=True,first_input_full_byte_readback_verified=True,
        vdma_errors=0,paired_same_frame_results=True,user_observation='左右都是固定数字8，右侧更亮',
        digit_summary=summary,normal_demo8=dict(raw=8,enhanced=8),dim_demo8=dict(alpha=.125,raw=6,enhanced=8),
        reference_mismatch_cases=len(mismatches),reference_raw_label_mismatch=sum('raw_label' in r['fields'] for r in mismatches),
        reference_enh_label_mismatch=sum('enh_label' in r['fields'] for r in mismatches),
        reference_mismatch_details=mismatches,
        diagnostics=dict(C_source_matches_python_reference=True,native_generated_RTL_matches_python_reference=True,
            native_continuous_test_frames=4,native_continuous_test_pixels=1536000,
            packaged_RTL_and_ROM_files_match_generated_source=True,
            same_input_bypass_two_board_cores_match=True,root_cause='UNRESOLVED; not claiming bit-exact hardware implementation'),
        limitations=['Ten fixed digit examples per brightness; not an independent camera benchmark.',
            'Alpha is synthetic encoded-RGB darkening, not lux or physical exposure.',
            'No complete license-plate detection/Chinese OCR.',
            'Enhanced RGB pixels feed LCD only; PC reference previews are NOT captured FPGA output.',
            'Board/reference integer numerical differences remain open; actual measurements and failures are preserved.',
            'JTAG host elapsed times are not FPGA accelerator latency or frame rate.'])
    (ROOT/'hardware_test_status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    with (ROOT/'结果汇总.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['合成亮度系数','数字样本数','原图正确数','增强后正确数','原图正确率','增强后正确率'])
        for r in summary:w.writerow([r['alpha'],r['n'],r['raw_correct'],r['enhanced_correct'],r['raw_correct']/10,r['enhanced_correct']/10])
    table='| 合成亮度系数 | 数字数 | 原图正确 | 增强后正确 |\n|---|---:|---:|---:|\n'
    for r in summary:table+=f'| {r["alpha"]:g} | 10 | {r["raw_correct"]}/10 | {r["enhanced_correct"]}/10 |\n'
    guide='''# 固定图片输入开发板：首轮实测

2026-10-25。现在已经实现“电脑图片→JTAG写入DDR→VDMA读出→FPGA增强和识别→LCD”，摄像头不参与输入。用户确认“左右都是固定数字8，右侧更亮”。沿用原FPGA位流和模型权重，仅更换独立的裸机ARM测试程序，不写SD卡。

## 已实测结果

38个输入全部完成：颜色检查1个、演示数字8的正常/暗光2个、每档10个固定数字共30个、空背景3个、自然暗光照片2个。真值只在电脑端统计，未把文件名、类别或参考预测写给板上的识别程序。

'''+table+'''
这里的亮度系数是在数字图片上合成压暗，附加固定噪声并保留RGB565精度，不是实测照度。每档只有10个相同来源的固定数字，不能作为摄像头准确率或泛化能力的证明。正常亮度两路各有失败样本；所有失败均保留。演示数字8正常光两路都为8，1/8亮度时板上原图为6、增强后为8；演示样例与上述30个数字分开统计。

每张输入均通过板上FNV-1a校验，第一张另从DDR完整回读，逐字节与源文件一致。VDMA错误位均为0。测试先写未显示的缓冲，再在帧边界切换，等待三帧并配对同一帧识别输出。图片虽是静态，FPGA会持续处理和刷新；移动手掌不应改变图片。

## 当前必须保留的问题

板上部分识别类别和分数与电脑定点参考不同，详见hardware_test_status.json。已确认输入传输正确，C源及独立RTL仿真与电脑参考一致，导出的RTL/ROM文件一致；旁路检查中两板上识别器对同样像素的输出相同。差异根因仍未解决，不能声称板上实现已达到逐位一致。这份表使用实际板上输出，没有用电脑预测替换硬件结果。下一步需继续核对综合后实现及运行时数值，再扩大验收集。

目前没有把增强后的RGB图像存回DDR。pc_reference_previews中的PNG是电脑定点参考图，名字带PC_REFERENCE，不能称为FPGA图像回读或用来计算“板上PSNR”。板上增强效果由LCD观察，识别结果通过寄存器回读；后续若要导出真正的板上增强图，需要加入输出采集通路。

## 文件用途

- inputs：38张实际输入PNG和对应BGR888二进制；左右两半是同一幅图。
- batch_38/board_results.csv：38个板上实测结果，包括失败及参考差异。
- case_manifest.json：预先固定的图片来源、真值、SHA256及电脑参考值。
- hardware_test_status.json：当前实物状态及未解决问题；app_build_status.json是构建时记录。
- image_test.elf：固定图片输入ARM程序；board内的位流/XSA/PS初始化与摄像头候选逐字节相同。
- start_fixed_image.tcl：临时下载图片测试程序。
- run_fixed_image.tcl：发送指定图片或整个批次并记录硬件结果。

## 以后如何操作

保持板卡供电，下载器接好。若改启动开关，先关电，JTAG使用BOOT_CFG两位ON/ON，再上电。无需插拔摄像头，也不依赖摄像头。

重新启动固定图片模式：

```powershell
& 'E:\\Xilinx\\Vitis\\2020.2\\bin\\xsct.bat' 'E:\\FPGA_Enhance_Work\\fixed_image_test_20261025\\start_fixed_image.tcl'
```

显示正常亮度数字8（输出目录名需换成未使用的名字，避免覆盖旧记录）：

```powershell
& 'E:\\Xilinx\\Vitis\\2020.2\\bin\\xsct.bat' 'E:\\FPGA_Enhance_Work\\fixed_image_test_20261025\\run_fixed_image.tcl' 'E:/FPGA_Enhance_Work/fixed_image_test_20261025/manual_normal_01' demo8_normal
```

显示1/8亮度数字8：

```powershell
& 'E:\\Xilinx\\Vitis\\2020.2\\bin\\xsct.bat' 'E:\\FPGA_Enhance_Work\\fixed_image_test_20261025\\run_fixed_image.tcl' 'E:/FPGA_Enhance_Work/fixed_image_test_20261025/manual_dim_01' demo8_dim
```

显示自然暗光图：最后参数可换成natural_1或natural_111。不提供最后参数时会跑完38个测试；自然照片没有数字真值，不统计数字准确率。JTAG发图约需数秒/张，这是传输和测试等待时间，不能写成FPGA处理延迟。

恢复摄像头＋数字识别版本：

```powershell
& 'E:\\Xilinx\\Vitis\\2020.2\\bin\\xsct.bat' 'E:\\FPGA_Enhance_Work\\camera_nn_digit_candidate_20261023\\download_digit_jtag.tcl'
```

上述操作只改变易失配置/内存，断电后需重新加载；旧SD卡内容未改。以后想添加自己的照片，可先交给我转换格式、确定是否含可识别数字，再加入测试清单。当前识别仍局限于居中的黑底白色单个数字，不是通用物体或整车牌识别。

自然图片取自此前已下载的LOL eval15探索性比较数据，曾用于候选筛选，不能当作新的独立测试集。厂商/Xilinx例程及NanoDCE的许可说明保留在notices；不在本包中分发Windows字体。
'''
    (ROOT/'使用与结果说明.md').write_text(guide,encoding='utf-8')
    source_dir=ROOT/'sources';source_dir.mkdir(exist_ok=True)
    for name in ['fixed_image_main.c','prepare_fixed_image.py','prepare_fixed_cases.py','start_fixed_image.tcl','run_fixed_image.tcl','finish_fixed_image.py']:
        shutil.copy2(HERE/name,source_dir/name)
    if not (ROOT/'notices').exists():shutil.copytree(candidate/'notices',ROOT/'notices')
    selected=[]
    for name in ['board','app_src','sources','notices','inputs','pc_reference_previews']:
        selected.extend(p for p in (ROOT/name).rglob('*') if p.is_file())
    for name in ['batch_38','smoke_test','display_demo8_dim']:
        selected.extend(p for p in (ROOT/name).rglob('*.csv'))
    selected.extend(p for p in ROOT.iterdir() if p.is_file() and p.suffix in ['.json','.tcl','.elf','.md','.csv','.log'] and p.name not in ['tool_help.log','tool_help.tcl'])
    for directory in ['hls_diagnostic','rtl_diagnostic','rtl_continuous_diagnostic']:
        selected.extend(p for p in (ROOT/directory).glob('*.log'))
    selected=sorted(set(selected))
    manifest={p.relative_to(ROOT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in selected}
    (ROOT/'package_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    archive=ROOT.parent/'fixed_image_test_20261025_ready.zip'
    assert not archive.exists(),'Preserve existing archive'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in selected+[ROOT/'package_manifest.json']:z.write(p,p.relative_to(ROOT))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name,entry in manifest.items():assert hashlib.sha256(z.read(name)).hexdigest()==entry['sha256']
    print('FIXED_IMAGE_BOARD_RESULTS_ARCHIVED',json.dumps(summary),'reference_mismatches',len(mismatches),'archive_bytes',archive.stat().st_size,flush=True)

if __name__=='__main__':main()
