"""Freeze successful board evidence, deployable JTAG package and honest report."""
from pathlib import Path
import csv,hashlib,json,re,shutil,zipfile
from PIL import Image,ImageDraw,ImageFont
from validate_real_cnn_batch import validate
from train_real_digit_cnn import OUT

WORK=Path('E:/FPGA_Enhance_Work')
BUILD=WORK/'camera_real_cnn_score64_20261025'
BASE=WORK/'real_cnn_image_test_score64_20261025'
AUTO=WORK/'real_cnn_adaptive_image_test_20261025'
RELEASE=WORK/'real_cnn_adaptive_verified_20261025'
HERE=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    b=validate(BASE,'baseline_66');a=validate(AUTO,'adaptive_66')
    post=(BUILD/'post_synth_check/simulate.log').read_text(encoding='utf-8',errors='replace')
    assert 'REAL_CNN_STREAM_AUTORESTART_BACKPRESSURE_RESET_PASS frames=2 pixels=61593' in post
    probe=(WORK/'cnn_score_probe_20261025/simulate.log').read_text(encoding='utf-8',errors='replace')
    assert 'SCORE_PROBE_POST_SYNTH_PASS cases=3' in probe
    identity=json.loads((BASE/'runtime_identity.json').read_text())
    model=json.loads((OUT/'training_report.json').read_text())
    manifest=json.loads((AUTO/'case_manifest.json').read_text(encoding='utf-8'))
    cases=manifest['cases'];expected={c['id']:c for c in cases}
    assert identity['model_sha256']==sha(OUT/'real_digit_cnn.pth')==manifest['digit_sha256']
    assert sha(AUTO/'board/system_wrapper.bit')==sha(BASE/'board/system_wrapper.bit')==identity['bit_sha256']
    for c in cases:assert sha(AUTO/'inputs'/(c['id']+'.bgr888'))==sha(BASE/'inputs'/(c['id']+'.bgr888'))
    preserved={WORK/'camera_nn_sd_20261018/BOOT.BIN':'e0d606c4c623463e01e6b4123ad127a63d0103c046674514bec01891e9ad67d3',
        WORK/'camera_nn_digit_candidate_20261023/camera_digit.bit':'d91401bcb0e255e09db6d19aedd5d7256b4a8797c410f058ac420d5befcb4ab1'}
    for p,value in preserved.items():assert sha(p)==value,(p,sha(p))
    br=list(csv.DictReader((BASE/'baseline_66/board_results.csv').open()))
    ar=list(csv.DictReader((AUTO/'adaptive_66/board_results.csv').open()))
    joined=[]
    for old,new in zip(br,ar):
        c=expected[new['id']];assert old['id']==new['id'] and old['raw_board']==new['raw_board']
        joined.append(dict(id=new['id'],truth=c['truth'],group=c['group'],alpha=c['alpha'],
            raw=int(new['raw_board']),always_nn8=int(old['enh_board']),adaptive=int(new['enh_board']),
            roi_mean=int(new['roi_mean']),enhance_mode=int(new['enhance_mode']),
            raw_margin=int(new['raw_margin']),adaptive_margin=int(new['enh_margin'])))
    util=(BUILD/'utilization.rpt').read_text()
    resources={}
    for label,key in [('Slice LUTs','lut'),('Slice Registers','ff'),('Block RAM Tile','bram_tiles'),('DSPs','dsp')]:
        match=re.search(r'^\|\s*'+label+r'\s*\|\s*([0-9.]+)',util,re.M);assert match,label
        value=float(match.group(1));resources[key]=int(value) if value.is_integer() else value
    assert 'VIOLATED' not in (BUILD/'bus_skew.rpt').read_text()
    status=dict(status='BOARD_NUMERIC_VERIFIED_ADAPTIVE_FIXED_IMAGE',hardware_downloaded=True,sd_written=False,
        baseline=b,adaptive=a,model_sha256=identity['model_sha256'],bit_sha256=identity['bit_sha256'],
        elf_sha256=sha(AUTO/'image_test.elf'),ps7_init_sha256=identity['ps7_init_sha256'],
        wns_ns=identity['wns'],whs_ns=identity['whs'],clock_mhz=100,resources=resources,
        hls_c_rtl=dict(frames=6,pixels=1586329,pass_all=True),native_stream_rtl=dict(frames=5,pixels=123339,pass_all=True),
        actual_synthesized_video_core=dict(frames=2,pixels=61593,pass_all=True),
        actual_synthesized_score_layer=dict(hidden_vectors=3,pass_all=True),
        gate_threshold=36,gate_calibrated_from_official_train_validation_only=True,
        preserved_old_files=[dict(path=str(p),sha256=value) for p,value in preserved.items()],
        limits=['Supplied ROI, single digit; not full-scene detection or plate OCR.',
            'Dark tests use synthetic RGB*1/8, not real night capture or measured lux.',
            'Preview RGB is PC reference. Actual FPGA RGB output was not captured to DDR.',
            'Normal full-photograph manual crops: 1/3 correct; old printed8 controls:0/2 correct.',
            'Recognition accuracy is distinct from numerical equivalence.',
            'Camera integration and robustness of exposure gate remain unverified.'])
    RELEASE.mkdir(exist_ok=True);assert not (RELEASE/'release_manifest.json').exists(),'Keep a frozen successful release'
    for name in ('board','inputs','pc_roi_references'):shutil.copytree(AUTO/name,RELEASE/name,dirs_exist_ok=True)
    for name in ('image_test.elf','start_fixed_image.tcl','run_fixed_image.tcl','cases.tcl','case_manifest.json','photo_sources_and_attribution.json'):
        shutil.copy2(AUTO/name,RELEASE/name)
    shutil.copy2(BASE/'image_test.elf',RELEASE/'baseline_image_test.elf')
    (RELEASE/'start_baseline.tcl').write_text((BASE/'start_fixed_image.tcl').read_text().replace('$root/image_test.elf','$root/baseline_image_test.elf'),encoding='ascii')
    (RELEASE/'run_baseline.tcl').write_text((BASE/'run_fixed_image.tcl').read_text().replace('$root/cases.tcl','$root/baseline_cases.tcl'),encoding='ascii')
    shutil.copy2(BASE/'cases.tcl',RELEASE/'baseline_cases.tcl')
    evidence=RELEASE/'evidence';evidence.mkdir(exist_ok=True)
    for root,name in [(BASE,'baseline_66'),(AUTO,'adaptive_66')]:
        shutil.copytree(root/name,evidence/name,dirs_exist_ok=True)
    copies={OUT/'hls_score64/verify.log':'hls_verify.log',OUT/'rtl_stream_score64/simulate.log':'native_stream_rtl.log',
        BUILD/'post_synth_check/simulate.log':'synthesized_video_core.log',
        WORK/'cnn_score_probe_20261025/simulate.log':'synthesized_score_probe.log',
        WORK/'real_cnn_image_test_20261025/bias_sign_extension_diagnostic.json':'rejected_first_revision_bias_diagnostic.json',
        BUILD/'timing_summary.rpt':'timing_summary.rpt',BUILD/'utilization.rpt':'utilization.rpt',
        BUILD/'drc.rpt':'drc.rpt',BUILD/'bus_skew.rpt':'bus_skew.rpt',BUILD/'integration_audit.json':'integration_audit.json'}
    for src,name in copies.items():shutil.copy2(src,evidence/name)
    shutil.copytree(OUT/'exposure_gate',RELEASE/'gate_validation',dirs_exist_ok=True)
    for name in ('training_report.json','frozen_candidate.json','real_digit_cnn.pth','integer_weights.npz'):
        shutil.copy2(OUT/name,RELEASE/name)
    sources=RELEASE/'sources';sources.mkdir(exist_ok=True)
    for p in HERE.glob('*.py'):
        if p.name.startswith(('train_real','prepare_real','prepare_cnn','prepare_score','calibrate_exposure','validate_real','finish_real','stage_real','fix_real','analyze_cnn','audit_cnn')) or p.name in ('digit_model.py','prepare_digit_hls.py','prepare_fixed_image.py','prepare_fixed_cases.py','download_svhn_train.py'):
            shutil.copy2(p,sources/p.name)
    for name in ('digit_monitor.cpp','digit_monitor.h','real_cnn_kernel.h','cnn_weights.h'):
        shutil.copy2(OUT/'hls_score64'/name,sources/name)
    shutil.copytree(AUTO/'app_src',sources/'adaptive_arm',dirs_exist_ok=True)
    shutil.copy2(BUILD/'build_board.tcl',sources/'build_board.tcl')
    (RELEASE/'hardware_test_status.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
    with (RELEASE/'逐图实板结果.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(joined[0]));writer.writeheader();writer.writerows(joined)
    photos=[r for r in joined if r['group'] in ('SVHN_first3_per_class','real_photo_manual_roi','synthetic_dim_from_SVHN')]
    sheet=Image.new('RGB',(1536,11*188+64),'white');draw=ImageDraw.Draw(sheet)
    font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',13)
    draw.text((10,8),'ALL 63 PHOTO CASES: 33 original + 30 synthetically dimmed; supplied digit ROI. 10=background class.',font=font,fill='black')
    draw.text((10,29),'RGB images: PC reference, NOT FPGA capture. Labels: actual FPGA measurements. All failures retained.',font=font,fill='black')
    for i,r in enumerate(photos):
        x=(i%6)*256;y=(i//6)*188+64
        raw=Image.open(AUTO/'inputs'/(r['id']+'.png')).crop((480,112,704,336)).resize((120,120))
        enhanced=Image.open(AUTO/'pc_roi_references'/(r['id']+'_PC_ENH_ROI.png')).resize((120,120))
        sheet.paste(raw,(x+4,y+4));sheet.paste(enhanced,(x+132,y+4))
        draw.text((x+4,y+127),r['id']+' GT='+str(r['truth']),font=font,fill='black')
        draw.text((x+4,y+145),'RAW='+str(r['raw']),font=font,fill='green' if r['raw']==r['truth'] else 'red')
        draw.text((x+132,y+145),'AUTO='+str(r['adaptive']),font=font,fill='green' if r['adaptive']==r['truth'] else 'red')
        draw.text((x+4,y+163),'mean='+str(r['roi_mean'])+' NN8='+str(r['enhance_mode']),font=font,fill='black')
    sheet.save(RELEASE/'全部照片与实板识别结果.png')
    text=f'''# 真实照片数字识别与自适应增强：实板验证版（2026-10-25）

当前版本已通过JTAG临时下载到领航者ZYNQ7020 V3.9、800×480 RGB屏，使用固定图片输入，摄像头DMA关闭。SD卡没有改动。**数值验收通过不代表图片都能识别正确。**

## 已完成的工作与实际结果

同一冻结CNN分别识别原图和处理后图像。先对无条件NN8版测试66张，再对自动旁路版测试完全相同的66张。两轮各132路类别及margin全部与电脑定点参考精确一致；全部输入FNV通过，首张整帧1,152,000字节从DDR读回逐字节相同，DMA错误0。

| 输入组 | 张数 | 原图识别正确 | 无条件NN8增强 | 自动旁路增强 |
|---|---:|---:|---:|---:|
| SVHN正常照片、预先给定数字区域 | 30 | 26 | 17 | 26 |
| 完整门牌照片的手动裁剪区域 | 3 | 1 | 1 | 1 |
| 上述30张SVHN的RGB统一乘1/8 | 30 | 19 | 26 | 26 |

正常照片合计33张：原图27/33、无条件增强18/33、自动旁路27/33。合成暗图30张：原图19/30（63.33%）、处理后26/30（86.67%）。**RGB乘1/8不是真实夜间拍摄，也不是lux照度测量。**

另有3张诊断控制：1张色块、2张旧黑底白字数字8。新版识别器在这两个旧字体8样例均失败，全部结果保留，不能宣称普适识别。色块没有数字真值，不计识别准确率。完整66张逐项结果见`逐图实板结果.csv`。

SVHN是原生32×32的真实街景数字裁剪图，本实验将其放大至224×224；放大不新增细节。30张按每类最早3个官方测试索引固定，3张门牌照片ROI先标注，未按结果筛图。它们已在早期实验被查看，是回归/展示集合，不应称新的盲测集。两张完整门牌8仍识别错误，真实字体/背景泛化尚需改进。

## 模型和训练

识别器为两层3×3卷积（1→8→16）、ReLU和最大池化，再接784→32→11，共26,731参数。使用SVHN TRAIN文件65,257张训练、8,000张验证，另有空白控制。官方TEST26,032张的冻结电脑定点准确率85.16%，浮点85.14%，预测一致率99.74%。这些大样本成绩是**电脑评估**，不是26,032张全部上板的成绩。

0–9是数字，10是背景控制类（屏幕显示“-”），不构成可靠的任意物体拒识。这里只做**已给定区域内的单个数字**，不包含完整场景自动定位、多位数字切分或车牌OCR。

增强网络仍是此前NanoDCE8-Cal，本轮未重训其权重。新增的是亮度门控：ROI整数亮度均值<=36时开启NN8，否则保留原图。阈值只用训练文件中既存验证集每类前50张、原图及RGB×1/4共1000例确定，没有用官方test或Wikimedia图拟合；并非让算法根据真值选择结果。该简单策略不能解决所有场景的曝光/噪声问题。

## FPGA和ARM各做什么

FPGA PL处理视频流、亮度转换和池化，执行RAW CNN、NanoDCE8增强、ENH CNN，并叠加绿色区域框及RAW/ENH标签。两路CNN使用同一组权重。

ARM初始化板卡、配置VDMA/显示时钟，从电脑上传的原始DDR图像计算ROI亮度均值并控制增强旁路，配对同帧硬件结果、更新显示。Python负责电脑训练/生成参考，不在ARM上代替CNN推理。主机没有向板卡发送真值或参考预测；门控版对旁路图另检查两路类别及margin完全一致。

## 修复与验证证据

第一处差异在HLS的局部累加处理，显式有符号原生累加及保留更新顺序后，逐层RTL恢复一致。第二处在最后分类层：第一版实板132路结果可由负偏置被误零扩展21位精确解释，差值2^21。将最后层累加/比较同样改为原生有符号计算后，通过独立的Vivado综合后分类层测试、完整综合网表和实板复测。权重及数学模型未变。

- HLS C/RTL：6帧、1,586,329像素，类别/margin/帧号/边带/画面检查通过。
- 随机背压、自动重启、复位、AXI读结果：5帧、123,339像素通过。
- 实际综合后的分类层：3组隐藏向量通过。
- 实际综合后完整核：2帧、61,593像素通过。
- 无条件与自动旁路版本：各66输入、各132路类别/margin精确通过，实测文件在`evidence/`。

保留了第一版失败数据和诊断，不以电脑结果替换实板结果。预览PNG中的RGB来自电脑参考，标签来自实板；FPGA增强RGB目前直接送屏幕，没有读回到DDR，因此**不报告硬件图像PSNR/SSIM或逐像素输出一致率**。

## 实际布线资源与时序

100MHz受约束路径WNS={identity['wns']}ns，WHS={identity['whs']}ns；LUT={resources['lut']}/53,200，FF={resources['ff']}/106,400，BRAM Tile={resources['bram_tiles']}/140，DSP={resources['dsp']}/220。Bus-skew报告无VIOLATED，DRC无Error，仍继承原厂摄像头PCLK路由例外及缺失外部IO延时等限制，完整报告保留。

启动日志中一秒处理帧计数增加约61，反映固定帧重复处理/显示节奏，**不是摄像头实测帧率或每秒新图片数量**。JTAG单张传输约数秒，也不是加速器运算延迟。

## 使用当前成功包

开发板独立供电、下载器接牢，按此前JTAG启动方式操作；修改拨码前先关电。本包仅临时JTAG下载，断电后不会保留新版，SD原版本未变。

PowerShell执行：

```powershell
Set-Location 'E:\\FPGA_Enhance_Work\\real_cnn_adaptive_verified_20261025'
& 'E:\\Xilinx\\Vitis\\2020.2\\bin\\xsct.bat' start_fixed_image.tcl
& 'E:\\Xilinx\\Vitis\\2020.2\\bin\\xsct.bat' run_fixed_image.tcl manual_results commons_1_roi
```

该例为真实门牌5。输入为固定图，移动手掌不会改变画面。可用cases.tcl中的任意ID切换图片；运行全部66张可省略最后ID参数。暗图ID以`_dim8`结尾，属于合成暗光。不要同时运行两个发图脚本。

对照无条件增强版本使用`start_baseline.tcl`和`run_baseline.tcl`，二者配套；默认`start_fixed_image.tcl`运行自动旁路版。摄像头实时接入和实拍稳健性尚未验证，此包不切换摄像头、不生成/写入BOOT.BIN。

## 来源与权重身份

SVHN来源及官方MD5记录保存在训练目录；模型/训练报告及源码在本包。Wikimedia原图来源与署名在`photo_sources_and_attribution.json`；门牌5照片作者Palauenc05，CC BY-SA4.0，其裁剪/缩放/增强衍生图沿用该许可并署名，另外两张门牌图为公有领域。配套厂商代码原有版权头保留。

模型SHA256：`{identity['model_sha256']}`。

FPGA位流SHA256：`{identity['bit_sha256']}`。

自动旁路ELF SHA256：`{status['elf_sha256']}`。

旧SD电脑BOOT.BIN及旧摄像头候选位流哈希均核对未变。下一阶段应采集实际摄像头正常/弱光数字照片、补充字体与背景，再验证泛化及噪声处理；当前成绩不能推广为完整车牌或真实夜景识别能力。
'''
    (RELEASE/'新版使用与实测结果.md').write_text(text,encoding='utf-8')
    items=[p for p in RELEASE.rglob('*') if p.is_file() and p.name!='release_manifest.json' and '__pycache__' not in p.parts]
    hashes=[dict(path=p.relative_to(RELEASE).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in items]
    (RELEASE/'release_manifest.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
    archive=WORK/(RELEASE.name+'.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in items+[RELEASE/'release_manifest.json']:z.write(p,p.relative_to(RELEASE))
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    for r in hashes:assert sha(RELEASE/r['path'])==r['sha256']
    print('REAL_CNN_ADAPTIVE_RELEASE_VERIFIED',len(hashes),'files','zip_bytes',archive.stat().st_size,flush=True)

if __name__=='__main__':main()
