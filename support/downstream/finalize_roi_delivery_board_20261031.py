"""Archive measured independent and physical results without promoting failed claims."""
from pathlib import Path
import json, shutil, zipfile
from car_roi_delivery_common import ROOT, read, write, sha
from roi_delivery_board_tools import BOARD, APP

def main():
    board=read(BOARD/'board_verified.json')
    assert board['physical_readback'] and board['status']=='ABI30_RAW_ROI_ACTUAL_ENGINEERING_VERIFIED'
    fresh=read(ROOT/'confirmation/fresh_result.json')
    assert fresh['accepted'] is False and all(fresh['gates']['baseline'].values())
    evidence=Path(board['evidence'])
    manual=read(BOARD/'final_display.json')
    display=Path(manual['capture'])
    assert read(display/'verified.json')['physical_readback']
    user_screen=dict(status='USER_PHYSICAL_LCD_CONFIRMED',response='左右图像、文字和框均正常，右侧更亮',
                     scope='Fixed night road, RAW IMAGE left, NEURAL ENHANCE right; optical user confirmation, not automated accuracy evidence',sd_written=False)
    write(BOARD/'user_screen_confirmation.json',user_screen)
    out=Path.cwd()/'汽车区域二次核验_20261031'
    out.mkdir(exist_ok=True)
    for name,src in [('独立测试原始结论.json',ROOT/'confirmation/fresh_result.json'),
                     ('实板六项验收.json',BOARD/'board_verified.json'),
                     ('仅工程验证范围.json',BOARD/'engineering_experiment_policy.json'),
                     ('最终增强显示实板验收.json',display/'verified.json'),
                     ('实物屏幕确认.json',BOARD/'user_screen_confirmation.json'),
                     ('实板检测对照.png',evidence/'road0_repeat/lcd_readback.png'),
                     ('实板摄像头采集.png',evidence/'camera/lcd_readback.png'),
                     ('实板增强显示.png',display/'lcd_readback.png')]:
        shutil.copy2(src,out/name)
    low=fresh['scores']['low']; base=low['baseline']; cand=low['candidate']; control=low['same_roi_initial']
    def row(label,r):
        return f"|{label}|{r['ap50']*100:.2f}%|{r['precision']*100:.2f}%|{r['recall']*100:.2f}%|{r['tp']}|{r['fp']}|"
    times='\n'.join(f"|{name}|{v['networks']}|{v['roi_count']}|{v['processing_seconds']:.2f}秒|{v['baseline_visible_cars']} → {v['candidate_visible_cars']}|" for name,v in board['cases'].items())
    comparisons=[n for r in board['cases'].values() for n in r['network_comparisons']]
    ci=fresh['car_ap50_difference_interval99']['baseline']
    report=f'''# 汽车区域二次核验：独立测试与实际板卡结果

日期：2026-10-31。硬件：XC7Z020、OV5640、800×480 RGB屏。版本：ABI30工程实验版；原ABI29仍保留。仅JTAG加载运行内存，未写SD卡或Flash。

## 结论与边界

相对旧版RAW7检测，原始图像上的小车辆区域二次核验在本轮独立夜间图片中提高了汽车AP50，并减少误检。固件已完成六项实际板卡读回校验和额外增强显示模式校验。

**这轮没有证明“增强后再识别比原图识别更好”。检测仍使用原图，增强用于显示。** 新训练权重与“同样区域核验、原始权重”的控制实验差异未通过预设要求，完整研究结论保持`accepted:false`；实板通过只表示这个冻结候选的硬件实现正确。没有更换测试集、重新选权重或调阈值来把失败变成通过。

## 未参与本轮选型的独立图片结果

公开BDD100K道路图像：240张夜间低亮度图片、2203个汽车标注；另有64张正常亮度图片、672个汽车标注。按预先冻结的元数据哈希顺序及原图亮度选取，排除既有图片、来源前缀组与图像哈希，不按检测结果或目标数量筛选。像素亮度分组不能替代照度测量。本轮已用于检验，不能再把同一批称为后续优化的全新测试集。

全部方案使用相同源图、同一原始标注。AP50使用IoU=0.5；P/R/TP/FP使用固定置信度0.25及同一评估规则。结果来自实际CPU C实现，共5158次网络前向。

|方案|汽车AP50|精确率P|召回率R|正确检出TP|误检FP|
|---|---:|---:|---:|---:|---:|
{row('旧版RAW7',base)}
{row('相同区域核验＋原始权重',control)}
{row('ABI30区域核验候选',cand)}

相对旧版：AP50增加{(cand['ap50']-base['ap50'])*100:.2f}个百分点，正确检出增加{cand['tp']-base['tp']}个，误检减少{base['fp']-cand['fp']}个。2000次配对分组bootstrap的99% AP50增益区间为+{ci[0]*100:.2f}～+{ci[1]*100:.2f}个百分点。正常亮度64张的三套输出完全一致。

相对相同区域核验的原始权重控制：AP50只增加{(cand['ap50']-control['ap50'])*100:.2f}个百分点；99%增益区间跨零，不能据此宣称新训练本身优于该控制。该控制也取得了大部分改进，说明区域核验策略是主要贡献。

## 工作分配

- FPGA可编程逻辑：复用16路卷积加速硬件，执行原检测网络及区域核验网络的卷积，摄像头及显示相关硬件链路沿用已验证设计。
- ARM：取帧、原图多视图及ROI裁剪缩放、硬件任务调度、后处理/NMS、框融合、17,549参数框修正网络，以及Retinex与411参数学习亮度融合的增强显示和界面绘制。
- 暗图先运行RAW7，再按冻结条件选至多8个160×96原生分辨率区域做二次核验；正常亮度仍走原RAW4。
- 显示模式0：左原图、右增强图，两侧使用同一组原图核验结果。模式1：左右均为同一原图，左旧版框、右核验框，便于公平比较检测变化。

## 实际板卡读回验收

证据目录：`{evidence}`。包含实际XSCT日志、读回像素/网络输出/框/帧缓冲及逐项验证JSON；不是电脑渲染冒充实板。电脑渲染只作逐字节期望值对照。

|测试输入|网络前向次数|核验区域数|板上处理时间|旧版框数 → 核验框数|
|---|---:|---:|---:|---:|
{times}

时间为板上单次处理，不含JTAG上传/读回及电脑校验。暗光道路图约36秒一张，是静态对照版本，不能描述成实时检测。框变多或变少都不能单独代表准确率，准确率结论来自上述完整标注测试集。

六项均通过输入像素、来源哈希、网络参数、卷积调用数、CPU/PL网络输出、ARM框修正、ROI选取及后处理、增强像素和LCD帧缓冲校验。相同固定图重复运行的输入、计划、网络后处理及检测框逐字节一致。六项共核对{len(comparisons)}次实际网络前向。

FP32说明：早期“所有原始解码数值绝对误差≤0.001”的标准未全部满足，原失败记录保留。独立测试前已冻结操作输出标准：概率误差≤0.00002、整体均值≤0.00002；最终有效框数量/类别一致、坐标误差≤0.005像素（400宽坐标系）、分数误差≤0.00002。不能把后者通过写成原标准通过。

## 已查看的实际显示

`实板检测对照.png`：两侧同一原图，文字和框正常；图中框数由10变9，单图不能证明整体准确率。`实板增强显示.png`：左原图、右增强，同组车辆框；路面和护栏更容易看清，暗区仍有颗粒噪声，增强显示沿用旧版算法，本轮没有新增画质改进结论。`实板摄像头采集.png`：实际摄像头单帧的读回结果，单帧验收不能证明连续实时运行。

## 版本追溯

- ELF：`{sha(APP/'road_detail.elf')}`
- PL位流：`{sha(APP/'display.bit')}`
- ROI权重：`{sha(APP/'runtime/roi_weights.f32')}`
- 独立测试清单：`{fresh['manifest_sha256']}`
- 原始完整研究结果：`独立测试原始结论.json`，`accepted:false`保持原样。

用户已确认实物屏幕“左右图像、文字和框均正常，右侧更亮”，记录见`实物屏幕确认.json`。原SD启动内容没有更新；掉电后此RAM版本消失。
'''
    (out/'验收与效果说明.md').write_text(report,encoding='utf-8')
    source=Path.cwd()/'starter/downstream/run_roi_delivery_board_20261031.py'
    usage=f'''# 使用与恢复

工程实验固件：`{APP}`。本机执行入口：`{source}`。使用现有Python及Xilinx 2020.2环境；归档不是全新电脑的一键安装包。

在PowerShell执行以下命令。开发板保持供电，摄像头、屏幕、JTAG按此前验证过的方式接好。同一时间只执行一条，完成后再执行下一条。每次会上传或采集单张图，暂停显示并完整读回核对，因此电脑命令完成时间长于单次检测时间。

首次上电，加载ABI30至RAM并显示固定夜间图（左原图、右增强）：
```powershell
& 'E:\\FPGA_Enhance_Work\\nn_env312\\Scripts\\python.exe' '{source}' --start --case road0 --view enhancement
```

同一张原图比较旧版框和二次核验框：
```powershell
& 'E:\\FPGA_Enhance_Work\\nn_env312\\Scripts\\python.exe' '{source}' --case road0 --view comparison
```

采集摄像头单帧并显示增强结果；重新执行可更新一帧：
```powershell
& 'E:\\FPGA_Enhance_Work\\nn_env312\\Scripts\\python.exe' '{source}' --case camera --view enhancement
```

恢复此前ABI29摄像头空闲预览（不是自动启动连续识别）：
```powershell
& 'E:\\FPGA_Enhance_Work\\nn_env312\\Scripts\\python.exe' '{source}' --restore
```

每次实际操作证据写入`{BOARD}/manual_时间戳`。脚本异常会尝试恢复ABI29；若下载器掉线导致恢复失败，会在`manual_failed.json`如实记录，需要恢复连接。任何上述命令均不写SD卡或Flash。
'''
    (out/'操作与恢复.md').write_text(usage,encoding='utf-8')
    package=ROOT/'ABI30_raw_ROI_engineering_verified_20261031.zip'
    entries={}
    def add(path,arc):
        if path.is_file():entries[arc]=path
    for p in APP.rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:add(p,'firmware/'+p.relative_to(APP).as_posix())
    old=Path('E:/FPGA_Enhance_Work/road_student_fusion_20261031_r1/board_candidate/firmware')
    for p in old.rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts and 'host' not in p.relative_to(old).parts:
            add(p,'rollback_ABI29/'+p.relative_to(old).as_posix())
    for p in (BOARD/'fixtures').glob('*.bgr'):add(p,'fixtures/'+p.name)
    for p in (Path.cwd()/'starter/downstream').iterdir():
        if p.suffix in ['.py','.c','.h','.tcl']:add(p,'workspace_sources/downstream/'+p.name)
    for p in out.iterdir():
        if p.suffix in ['.json','.md','.png']:add(p,'report/'+p.name)
    for folder,prefix in [(evidence,'physical_six_cases'),(display,'physical_enhancement_mode')]:
        for p in folder.rglob('*'):
            rel=p.relative_to(folder)
            if p.is_file() and 'cpu' not in rel.parts and p.name!='expected_frame.bgr':add(p,prefix+'/'+rel.as_posix())
    for rel in ['protocol.json','selected.json','confirmation/protocol.json','confirmation/fresh_protocol.json',
                'confirmation/fresh/manifest.json','confirmation/fresh/complete.json','confirmation/fresh_result.json',
                'c_proof/complete.json','c_proof/original_probe_failure.json','c_proof/numerical_policy_v2.json',
                'c_proof/numeric_failure_v2.json','c_proof/numerical_policy_v3.json',
                'board_candidate/engineering_experiment_policy.json','board_candidate/physical_acceptance_policy.json',
                'board_candidate/board_verified.json','board_candidate/host_preflight/complete.json']:
        add(ROOT/rel,'frozen_evidence/'+rel)
    manifest={name:{'bytes':p.stat().st_size,'sha256':sha(p)} for name,p in sorted(entries.items())}
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
        for name,p in sorted(entries.items()):z.write(p,name)
        z.writestr('archive_manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(package) as z:
        assert z.testzip() is None
        for n,d in manifest.items():
            import hashlib
            assert hashlib.sha256(z.read(n)).hexdigest()==d['sha256']
    receipt=dict(status='ARCHIVE_CRC_AND_EACH_ENTRY_SHA256_VERIFIED',path=str(package),sha256=sha(package),bytes=package.stat().st_size,members=len(manifest)+1,full_joint_study_accepted=False,sd_written=False)
    write(out/'归档校验.json',receipt)
    write(ROOT/'delivery_complete.json',dict(report=str(out),archive=receipt,physical_board_verified=True,full_joint_study_accepted=False,enhanced_input_superiority_established=False))
    print('ROI_ENGINEERING_REPORT_AND_ARCHIVE_VERIFIED',json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
