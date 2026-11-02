"""Package existing measured evidence; no board access or inference changes."""
from pathlib import Path
import csv
import hashlib
import json
import shutil

WORK = Path(__file__).resolve().parents[2]
OUT = WORK / '阶段展示与收尾_20261030'
BRIGHT = Path('E:/FPGA_Enhance_Work/road_car_bright_20261030_r1')
ROUTE = Path('E:/FPGA_Enhance_Work/road_brightness_route_20261030_r1')
LAB = Path('E:/FPGA_Enhance_Work/road_shadowlift_20261030_r1')
OUT.mkdir(exist_ok=True)
board = json.loads((BRIGHT / 'board_summary.json').read_text(encoding='utf-8'))
result = json.loads((ROUTE / 'fresh_result.json').read_text(encoding='utf-8'))
old = result['low_baseline']['all']['classes']['car']
new = result['low_candidate']['all']['classes']['car']
assert result['low_baseline']['all']['images'] == 320
assert old['objects'] == new['objects'] == 2758
assert result['accepted'] is False  # Keep the failed four-class gate visible.
assert board['all_road_neural_outputs_and_boxes_equal_actual_ABI26']
assert board['SD_and_Flash_untouched']

sources = {
    '01_增强对比_原图_旧版_新版.png': LAB / 'final_comparison.png',
    '02_识别对比_含退步案例.png': ROUTE / 'car_examples_with_regression.png',
    '03_开发板实际帧缓冲.png': Path(board['last_frame']),
    'source_board_summary.json': BRIGHT / 'board_summary.json',
    'source_detection_result.json': ROUTE / 'fresh_result.json',
    'source_example_annotations.json': ROUTE / 'car_examples_with_regression.json',
}
for name, source in sources.items():
    assert source.is_file(), source
    shutil.copy2(source, OUT / name)

with (OUT / '汽车检测指标.csv').open('w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['指标', '稳定模型', '汽车专项模型', '说明'])
    for label, key in [('AP50', 'ap50'), ('精确率', 'precision'), ('召回率', 'recall')]:
        w.writerow([label, f'{old[key]*100:.2f}%', f'{new[key]*100:.2f}%',
                    '同一批320张暗光图；IoU=0.5；精确率/召回率置信阈值0.25'])
    for label, key in [('正确检出TP', 'tp'), ('误检FP', 'fp'), ('漏检FN', 'fn')]:
        w.writerow([label, old[key], new[key], '2758个汽车标注'])

guide = '''# 接下来的工作与三人分工

以2026年11月1日冻结作品、11月4日前提交为目标。当前不再追求实时检测，也不扩大类别；先完成“暗光图像增强显示＋汽车检测”的可信演示。

## 已完成的证据

| 项目 | 现有结果 | 可说明的结论 |
|---|---|---|
| 显示增强 | 同一张夜间道路图，平均亮度旧版34.39→新版62.02（0–255） | 暗部更亮；亮度本身不等于画质，噪点和光晕仍存在 |
| 汽车检测 | 320张独立暗光图、2758个汽车标注，AP50 44.94%→46.46% | 这批数据上的汽车检测有所提升 |
| 检出与误检 | TP 1287→1331；FP 1646→1579；FN 1471→1427 | 仍有较多误检与漏检，不能称为成熟辅助驾驶系统 |
| 上板一致性 | 7组输入、56组神经网络输出比较通过；增强与C参考逐像素一致 | 软件参考与当前硬件部署实现一致 |
| 当前速度 | 双模型对照单帧计算约16.5–17.4秒 | 单帧/快照演示；不包含JTAG传输和电脑校验时间 |

暗光按未修改原图平均亮度≤48定义，并不等于测得的照度。三张识别示例按结果选取，包含退步案例；总体数字来自全部320张。新模型对卡车/公交车的保留指标未达原四类验收门槛，因此只用于汽车专项对照，不宣称四类全面提升。

**关键边界：目前神经网络仍吃原图，增强用于显示。AP提升来自检测模型调整，不能写成“增强使识别准确率提升”。** 若要证明后者，需要固定同一个检测器，对原图/增强图做同批标注图片的严格A/B，连同误检、漏检和退步场景报告。目前尚无该结论。AP50、精确率、召回率也不能混称为一个“准确率”。

## 今天先做：保存证据、确认实物演示

1. 本目录的01图展示原图/旧版/新版增强；03图是开发板实际帧缓冲读回，不是摄像头新拍的照片。
2. 拍摄当前开发板实物屏幕，重点记录暗处、车灯和路面。冻结图模式下，移动手掌不会改变图片，这是正常现象。
3. 暂不继续提高增强强度。观察到新版路面更亮，同时噪点更明显；已有照片不足以证明细节恢复。

## 三个人的分工

| 人员 | 现在开始做什么 | 完成标志 |
|---|---|---|
| 你：硬件与摄像头 | 保持接线，固定镜头，准备静止车辆或固定道路图片；拍正常/较暗两种照明下的单帧测试 | 保存原始帧、光照条件、屏幕照片、是否识别正确的记录 |
| 组员2：数据与核对 | 阅读指标表，人工复核增益和退步示例；准备3段演示素材 | 不把更多框当成更准确；标出正确框、误检、漏检 |
| 组员3：汇报与录制 | 根据本目录写展示讲解、整理系统分工与限制、准备录屏 | 能清楚区分图像增强、检测提升和硬件加速 |

我可以继续做：编写测试与统计脚本、分析误检、整理图表和报告、维护可回退的软件包。插拔接线、布置真实目标、改变照明、拍摄实物视频需要你们操作。若要新增严谨对照实验，先冻结协议与参数，再运行；不要看过测试答案后反复挑参数并继续称其为独立测试。

## 下一次摄像头验证怎么做

1. 固定镜头与静止目标，先正常照明，再降低照明；两次保持构图一致。优先真实车辆；拍道路图片只能验证屏摄链路，不能代替真实道路性能。
2. 每种条件至少保存3帧原图，记录照明和检测时间；不要只保留成功帧。
3. 相机自动曝光/增益可能补偿变暗，必须记录；未经验证不随意改OV5640寄存器。需要严格光照比较时，再核对并控制曝光设置。
4. 在同一张冻结原图上比较两套检测模型；增强显示前后也用同一原图。人工统计TP/FP/FN。
5. 实物画面正常仅证明显示链路工作；判断识别好坏要有标注和匹配，不能仅凭屏幕框数。

## 目前的演示入口

程序目录：`E:/FPGA_Enhance_Work/road_car_bright_20261030_r1`

- `04_fixed_road.cmd`：重新跑固定道路照片。
- `03_enhancement.cmd`：原图/增强图页面；两边是同一新模型在原图上的检测框。
- `02_models.cmd`：稳定/新模型页面；两边使用相同增强背景。
- `01_capture_camera.cmd`：采集并计算新一帧，需要相机、开发板和JTAG在线。
- 断电后要重新运行时，使用`05_start_camera.cmd`恢复JTAG程序。

这些命令需在电脑上执行。当前是JTAG运行内存版本，SD卡和Flash未修改。拔掉下载器且独立供电时可保留当前运行状态；断电后不能保证从SD卡启动当前新版。

## 11月1日前的交付清单

- 10月30日：保存当前版本、本目录证据、实物展示记录。
- 10月31日：摄像头固定场景验证，记录至少一个有效例和一个失败例；完成报告初稿。
- 11月1日：冻结代码与参数，复核指标、版本、演示流程；此后主要录视频和整理材料。
- 独立启动包尚需另行制作和断电重启验收；当前资料包不等于已经更新SD卡。

建议视频顺序：板卡与接线→固定道路原图/增强→同一原图新旧模型→全量指标与失败案例→实际摄像头单帧演示。等待推理可剪辑，但需标明实际单帧耗时。

系统分工：PL负责摄像头/显示硬件链路及已部署的卷积加速；ARM负责流程调度、图像预处理、Retinex增强、网络其余计算与检测后处理等。增强当前在ARM上运行，不能把它写成“神经网络增强已全部在FPGA逻辑中实现”。
'''
(OUT / '下一步与分工.md').write_text(guide, encoding='utf-8')

hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
          for p in sorted(OUT.iterdir()) if p.is_file() and p.name != 'manifest.json'}
(OUT / 'manifest.json').write_text(json.dumps({
    'purpose': 'Existing evidence and completion guide; no new experiments claimed',
    'board_access': False, 'sd_written': False,
    'source_copies': {k: str(v) for k, v in sources.items()},
    'sha256': hashes,
}, ensure_ascii=False, indent=2), encoding='utf-8')
for name, source in sources.items():
    assert hashlib.sha256(source.read_bytes()).hexdigest() == hashes[name]
for entry in ['01_capture_camera.cmd', '02_models.cmd', '03_enhancement.cmd',
              '04_fixed_road.cmd', '05_start_camera.cmd']:
    assert (BRIGHT / entry).is_file(), entry
print(json.dumps({'status': 'evidence_package_checked', 'files': len(hashes)+1,
                  'output': str(OUT), 'board_access': False, 'sd_written': False},
                 ensure_ascii=True))
