"""Create a readable audit and complete regression gallery, without hardware IO."""
from pathlib import Path
import csv,hashlib,json,shutil,zipfile
from PIL import Image,ImageDraw,ImageFont
from train_real_digit import ROOT,REAL

HERE=Path(__file__).resolve().parent
OUT=ROOT/'cnn_candidate'

def main():
    cnn=json.loads((OUT/'training_report.json').read_text(encoding='utf-8'))
    mlp=json.loads((ROOT/'training_report.json').read_text(encoding='utf-8'))
    light=json.loads((OUT/'synthetic_light_diagnostic.json').read_text(encoding='utf-8'))
    rows=cnn['previously_seen_regression_33']['results']
    with (OUT/'真实照片回归结果.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',16)
    small=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',14)
    sheet=Image.new('RGB',(1600,7*202+64),'white');draw=ImageDraw.Draw(sheet)
    draw.text((12,8),'ALL 33 PREVIOUSLY SEEN REGRESSION PHOTOS - PC INTEGER REFERENCE, NOT FPGA RESULTS',font=font,fill='black')
    draw.text((12,32),'Each cell: original | existing NN8 enhancement; supplied digit ROI; failures retained.',font=small,fill='black')
    for i,row in enumerate(rows):
        x=(i%5)*320;y=(i//5)*202+64
        raw=Image.open(REAL/'inputs'/(row['id']+'.png')).crop((480,112,704,336)).resize((150,150))
        enh=Image.open(REAL/'pc_reference_previews'/(row['id']+'_PC_REFERENCE.png')).crop((480,112,704,336)).resize((150,150))
        sheet.paste(raw,(x+5,y+4));sheet.paste(enh,(x+163,y+4))
        draw.text((x+5,y+158),row['id']+' GT='+str(row['truth']),font=small,fill='black')
        draw.text((x+5,y+178),'RAW='+str(row['raw_prediction']),font=small,fill='green' if row['raw_correct'] else 'red')
        draw.text((x+163,y+178),'ENH='+str(row['enh_prediction']),font=small,fill='green' if row['enh_correct'] else 'red')
    sheet.save(OUT/'全部真实照片回归预览.png')
    build=(OUT/'hls/build_retry.log').read_text(encoding='utf-8',errors='replace')
    assert 'DIGIT_INTEGER_PIXEL_MATCH_PASS frames=6 pixels=1586329' in build
    assert 'REAL_CNN_CSIM_SYNTH_PASS' in build
    cosim=OUT/'hls/real_cnn_project/solution_100mhz/sim/report/digit_monitor_cosim.rpt'
    cosim_pass=cosim.exists() and 'Pass' in cosim.read_text(encoding='utf-8',errors='replace')
    evidence=OUT/'evidence';evidence.mkdir(exist_ok=True)
    for name in ('digit_monitor_csynth.rpt','digit_monitor_csynth.xml'):
        shutil.copy2(OUT/'hls/real_cnn_project/solution_100mhz/syn/report'/name,evidence/name)
    if cosim.exists():shutil.copy2(cosim,evidence/cosim.name)
    diagnostics=[]
    for name in ('fabric','serial'):
        log=OUT/f'hls_{name}_diagnostic/build.log'
        if log.exists():
            value=log.read_text(encoding='utf-8',errors='replace')
            diagnostics.append(dict(variant=name,c_sim_pass='DIGIT_INTEGER_PIXEL_MATCH_PASS' in value,
                rtl_cosim_pass='C/RTL co-simulation finished: PASS' in value,
                failure='Zero-input margin: C/Python 7804859, RTL 5048887' if 'margin=5048887' in value else 'See log'))
            shutil.copy2(log,evidence/f'{name}_diagnostic.log')
    (OUT/'hardware_diagnostics.json').write_text(json.dumps(dict(results=diagnostics,
        conclusion='Both multiplier-fabric and serial-channel variants reproduce the same discrepancy. Root cause unresolved; not accepted for download.'),indent=2),encoding='utf-8')
    sources=OUT/'sources';sources.mkdir(exist_ok=True)
    for name in ('download_svhn_train.py','train_real_digit.py','train_real_digit_cnn.py','digit_model.py',
        'prepare_digit_hls.py','prepare_real_cnn_hls.py','real_cnn_kernel.h','digit_monitor.cpp','digit_monitor.h','tb_digit.cpp',
        'evaluate_real_cnn_light.py','finish_real_training.py','prepare_cnn_fabric_diagnostic.py','prepare_cnn_serial_diagnostic.py'):
        shutil.copy2(HERE/name,sources/name)
    shutil.copy2(ROOT/'data/source_manifest.json',OUT/'svhn_train_source_manifest.json')
    shutil.copy2(ROOT/'split_indices.npz',OUT/'split_indices.npz')
    # Preserve existing successful camera models and the old SD boot image.
    protected={
        'E:/FPGA_Enhance_Work/camera_nn_sd_20261018/BOOT.BIN':'e0d606c4c623463e01e6b4123ad127a63d0103c046674514bec01891e9ad67d3',
        'E:/FPGA_Enhance_Work/camera_nn_digit_candidate_20261023/camera_digit.bit':'d91401bcb0e255e09db6d19aedd5d7256b4a8797c410f058ac420d5befcb4ab1'}
    checks=[]
    for file,expected in protected.items():
        p=Path(file)
        # Some frozen packages put board files in a board subdirectory.
        if not p.exists():
            matches=list(p.parent.rglob(p.name));assert len(matches)==1,(file,matches);p=matches[0]
        actual=hashlib.sha256(p.read_bytes()).hexdigest();assert actual==expected,(p,actual)
        checks.append(dict(file=str(p),sha256=actual,unchanged=True))
    status=dict(status='OFFLINE_TRAINED_HARDWARE_CANDIDATE_REJECTED_RTL_MISMATCH' if not cosim_pass else 'TRAINED_QUANTIZED_RTL_COSIM_PASS_NOT_DOWNLOADED',
        rtl_cosimulation_pass=cosim_pass,model_sha256=cnn['model']['sha256'],
        rtl_failure=None if cosim_pass else dict(case=0,expected_prediction=10,rtl_prediction=10,
            expected_margin=7804859,rtl_margin=5048887,note='First zero-input diagnostic; later cases also differ. Candidate is not accepted for download.'),
        hardware_changed=False,sd_written=False,protected_originals=checks,
        hls_estimates=dict(bram_18k=44,dsp=15,lut=10845,ff=6730,
            inference_cycles=88127,clock_target_ns=10,clock_estimated_ns=7.882,
            effective_budget_ns=7.3,warning='Estimated 7.882ns exceeds HLS uncertainty-adjusted 7.3ns budget. Not an implemented timing result.'),
        unresolved=['Previous FPGA/software numerical mismatch is not proved fixed by this candidate.',
            'Full-board implementation/resource/timing, sustained video and real camera evaluation pending.',
            'Normal-light enhancement regressions retained; enhancement weights unchanged.'])
    (OUT/'candidate_status.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
    normal,dark=light['summary']
    text=f'''# 真实照片识别器重训结果（2026-10-25）

已完成真实照片训练、独立电脑测试、定点权重导出、HLS C仿真及综合。**生成RTL协同仿真失败，硬件候选未通过验收。** 新版尚未生成整机位流、未下载到开发板，未写SD卡。当前板上仍为此前固定图片模式。电脑训练结果与硬件计算失败必须分开理解。

## 训练了什么

本轮更换的是数字识别器，原有NanoDCE8增强网络权重保持不变。用真实门牌数字SVHN训练，保留原始背景、字体、颜色；采用灰度输入及光照、对比度、轻微平移和噪声增强。先固定训练/验证索引，再训练，再冻结权重后测试。

实际拟合65,257张真实数字照片，验证8,000张；另加入5,000张训练、500张验证的空白/渐变/噪声背景控制。完整SVHN训练文件73,257张，182,040,794字节，MD5已与官方torchvision源码核对。**未使用官方测试照片或3张Wikimedia门牌参与梯度训练、选择最佳权重。**

预处理为与固定图实验一致的32→224 LANCZOS缩放、RGB565截断、整数亮度及8×8均值池化，得到28×28。SVHN原图只有32×32，放大不会新增真实细节。

先训练784→64→11全连接候选：独立测试定点准确率{mlp['official_svhn_test']['integer_accuracy']:.2%}，并未达到满意效果。随后训练两层卷积候选，不按测试图正确与否挑选照片。

CNN结构：3×3卷积1→8、ReLU、2×2最大池化；3×3卷积8→16、ReLU、2×2最大池化；784→32 ReLU→11。共{cnn['model']['parameters']:,}个参数，训练36轮。类别0–9为数字，10仅为空白控制类，不能解释成可靠的任意物体拒识能力。

## 独立测试及数值

SVHN官方测试集26,032张，全部纳入：

| 识别器 | 同一输入上的电脑定点准确率 |
|---|---:|
| 原黑底白字模型 | {mlp['official_svhn_test']['old_integer_accuracy_same_inputs']:.4%} |
| 真实照片全连接候选 | {mlp['official_svhn_test']['integer_accuracy']:.2%} |
| 真实照片卷积候选 | **{cnn['official_svhn_test']['integer_accuracy']:.2%}（22,170/26,032）** |

卷积模型浮点准确率85.14%，浮点/定点预测一致率{cnn['official_svhn_test']['float_integer_agreement']:.2%}。权重Q12/int16、偏置Q20/int32、层间非负Q8/20位，累加40位；已核对保守累加范围。训练集、验证集、测试集按索引分别保存。

同一个官方测试集也用于比较候选，此后不应继续反复按它调参并宣称为全新盲测。此前30张SVHN照片是该测试集的一部分，早已被查看；另3张Wikimedia照片也属于已知回归集。

## 之前失败的33张照片：全部保留

电脑定点重新测试，原图**27/33**正确，现有增强网络后的电脑参考图片**18/33**正确。之前旧模型同一33张的电脑参考及实物测试均0/33。这里的新结果全是电脑结果，不能与旧实物结果混称为新版板上提升。

细分：30张SVHN原图26/30，3张完整门牌照片的人工裁剪区域仅1/3。不同门牌风格仍有明显泛化问题。全部33张结果见`真实照片回归结果.csv`，全部成功/失败预览见`全部真实照片回归预览.png`。增强图片来自原测试目录的电脑定点参考，绝非FPGA图像回读。

## 冻结模型后的光照诊断

另外按每类最早10个官方测试索引固定100张，模型保持冻结，同一识别器对比原图、固定Gamma和现有NN8。没有按识别结果筛图：

| 100张真实照片的输入条件 | 原图 | Gamma | 当前NN8 |
|---|---:|---:|---:|
| 原始照片 | {normal['correct']['RAW']}/100 | {normal['correct']['GAMMA']}/100 | {normal['correct']['NN8']}/100 |
| RGB乘1/8的合成暗光 | {dark['correct']['RAW']}/100 | {dark['correct']['GAMMA']}/100 | {dark['correct']['NN8']}/100 |

**合成压暗不是真实夜间拍摄，也不是lux照度测量。** 这100张包含之前查看过的部分SVHN照片，不是额外独立数据集。结果表明当前增强对这批合成暗图有帮助，但正常光明显退步，不能笼统宣称所有真实场景识别更好。

下一阶段应验证正常光旁路/减弱增强、暗光增强及真实噪声抑制，使用新的真实暗光照片/成对数据进行验证或训练。不能通过改真值、挑图、只报告成功样例或让两路使用不同识别器制造优势。

## FPGA候选状态

已准备共享4个输出通道计算通路的HLS内核，乘法显式有符号并扩宽。C仿真6帧、1,586,329像素，分类、margin、帧号、像素和视频边带与独立Python参考一致；HLS综合成功。

单个识别核HLS估计44块BRAM18K、15个DSP、10,845个LUT；核心推理88,127周期，按100MHz换算约0.881ms。这些**均为HLS估计**，不是实测帧率、整机延迟或布线后资源。

时钟目标10ns，HLS估计7.882ns，但超过扣除2.7ns不确定度后的7.3ns有效预算，工具存在时序警告，尚不能宣称整机时序通过。后续需完整布局布线、连续视频及板上数值验收。

**RTL协同仿真已运行6帧但未通过数值检查：** 第0帧零输入的类别均为10，但margin的Python/C期望7,804,859，RTL输出5,048,887，后续帧也存在差异。单帧将乘法改为fabric的隔离实验仍得到同样错误，因此不能据此断言只是DSP乘法映射问题。进一步串行通道隔离实验结果见`hardware_diagnostics.json`。未定位根因，禁止把该HLS候选作为已验证硬件版下载。

此前旧板上margin/软件参考差异仍未查清；新内核的显式有符号计算不能证明该问题已经修复。新版必须先完成实物逐位核查，不能把电脑预测直接作为板上成绩。

## 当前能力及剩余工作

当前是**已给定ROI内的单个数字识别**，没有完整场景数字定位、车牌检测、多字符切分、中文OCR。摄像头画面中的对焦、曝光、噪声、物体尺寸与位置仍需新的实拍数据验证。

建议顺序：先完成新版定点/RTL/整机验证，再用固定真实图片上板复测，记录所有失败；随后优化正常光与暗光的增强策略，最后加入摄像头测试及实拍数据。原摄像头成功版本与原SD电脑BOOT文件哈希已核对未改。本轮不需要重新操作板卡。

## 来源与复现

- [SVHN数据说明（TensorFlow Datasets）](https://tensorflow.google.cn/datasets/catalog/svhn_cropped)
- [torchvision官方SVHN下载地址、校验值和标签定义](https://raw.githubusercontent.com/pytorch/vision/main/torchvision/datasets/svhn.py)
- 下载镜像及校验：`svhn_train_source_manifest.json`；训练/验证划分：`split_indices.npz`。
- 训练、定点评估及HLS准备源码在`sources/`；原始完整报告、逐轮记录、官方测试全部预测及整数权重在本目录。
- Wikimedia来源与署名继续由原真实照片测试包维护。包含Palauenc05的CC BY-SA4.0门牌5照片；本目录预览中的相应裁剪/缩放衍生图保持该许可并应署名，详见原包`original_photos/sources.json`。其他两张为公有领域。

冻结CNN权重SHA256：`{cnn['model']['sha256']}`。
'''
    (OUT/'真实场景训练结果说明.md').write_text(text,encoding='utf-8')
    # Include attribution beside the derived gallery, not just in another folder.
    shutil.copy2(REAL/'original_photos/sources.json',OUT/'photo_sources_and_attribution.json')
    package=ROOT/'real_digit_cnn_offline_candidate.zip'
    include=[]
    for p in OUT.rglob('*'):
        if p.is_file() and 'real_cnn_project' not in p.parts and p.name not in ('cases.txt','package_manifest.json') and '__pycache__' not in p.parts:include.append(p)
    manifest=[dict(path=p.relative_to(OUT).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in include]
    (OUT/'package_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
        for p in include+[OUT/'package_manifest.json']:z.write(p,p.relative_to(OUT))
    print('REAL_TRAINING_REPORT_READY',str(OUT/'真实场景训练结果说明.md'),'rtl_cosim',cosim_pass,'zip_bytes',package.stat().st_size,flush=True)

if __name__=='__main__':main()
