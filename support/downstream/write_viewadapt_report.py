"""Close the offline experiment with all outcomes and explicit evidence limits."""
from road_viewadapt_common import *

def pct(x):return '—' if x is None else f'{x*100:.2f}%'

def main():
 result=read(ROOT/'fresh_result.json');selected=read(ROOT/'selected_classcalibrated.json');export=read(ROOT/'export/complete.json');training=read(ROOT/'training_complete.json')
 report=['# 部署视图微调：离线验收记录（2026-10-30）','',
 '结论：'+('候选通过预先声明的独立图片离线验收，尚未上板验收。' if result['accepted'] else '候选未通过完整独立验收，保留已验证 ABI24 稳定版；不将失败候选下载到板上。'),'',
 '## 本轮改了什么','',
 '在原 YOLOv5n 四类模型上完成了6轮真实权重微调。仅使用原训练集2400张照片，生成与板端相同的全图平均缩小视图及三个局部裁剪视图；没有用验收图片参与梯度训练。网络结构、锚框和 FPGA 位流不变。',
 f"训练耗时约{training['seconds']/60:.1f}分钟。检查了第2、4、6轮权重；最终候选为第{selected['chosen']['epoch']}轮。训练后以开发数据确定卡车/公交车固定分数映射参数{selected['chosen']['gains']}，公式为 g*s/(1+(g-1)*s)。这项映射不改变新模型的汽车/行人分数和框，但微调本身可能改变四类预测。",'',
 '共享校准系数的尝试未通过，原结果保留；随后在开发数据上联合选择两个类别的独立系数，未放宽原来的验收要求。640张开发图片已用实际C神经网络重新推理，C融合/分数映射与NumPy参考逐字节一致。','',
 '图像增强算法本轮没有修改。识别收益应归于权重微调、部署视图适配和分数校准，不能据此证明增强提高识别。','',
 '## 新的独立图片验收','',
 '160张低亮度图片（原 night 元数据且原始平均亮度≤48）和64张较亮图片（daytime 且平均亮度≥70）。来自原数据源官方train池中本项目记录未使用的图片；排除所有已记录训练、评测和亮度筛选的同名前缀组及图像哈希。候选冻结后才运行检测；两版本均使用实际C推理、相同输入和多视图处理。前缀分组不能保证不同前缀的道路在地理上完全独立。','',
 '| 图片组 | 方法 | 汽车 AP50 | 四类 mAP50 | 汽车精确率 | 汽车召回率 | 卡车/公交车 TP | 卡车/公交车 FP |',
 '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
 for cohort,label in [('low','低亮度160张'),('brighter','较亮64张')]:
  for mode,title in [('baseline','稳定算法'),('candidate','训练候选')]:
   m=result['scores'][cohort][mode]['all'];c=m['classes'];report.append(f"| {label} | {title} | {pct(c['car']['ap50'])} | {pct(m['mAP50'])} | {pct(c['car']['precision'])} | {pct(c['car']['recall'])} | {sum(c[n]['tp'] for n in ['truck','bus'])} | {sum(c[n]['fp'] for n in ['truck','bus'])} |")
 report+=['','固定工作点：置信度0.25、匹配IoU0.5；AP50为该IoU下跨置信度的平均精度，不等于正确识别图片比例。','',
 '| 图片组 | 汽车 AP50 差值的99%配对图像自助法区间 | 未通过的验收项 |','| --- | --- | --- |']
 for cohort,label in [('low','低亮度'),('brighter','较亮')]:
  ci=result['paired_uncertainty'][cohort]['car_ap50_difference_interval99'];failed=[k for k,v in result['gates'][cohort].items() if not v]
  report.append(f"| {label} | [{ci[0]*100:+.2f}, {ci[1]*100:+.2f}] 个百分点 | {', '.join(failed) if failed else '无'} |")
 report+=['','## 四个类别的 AP50 都保留报告','', '| 图片组 | 类别 | 稳定算法 AP50 | 候选 AP50 |','| --- | --- | ---: | ---: |']
 for cohort,label in [('low','低亮度'),('brighter','较亮')]:
  for name in NAMES:report.append(f"| {label} | {name} | {pct(result['scores'][cohort]['baseline']['all']['classes'][name]['ap50'])} | {pct(result['scores'][cohort]['candidate']['all']['classes'][name]['ap50'])} |")
 report+=['','## 版本和边界','',
 '- 本轮没有访问开发板，也没有写 SD 卡或 Flash。ABI24 稳定版及其原验收记录保持原状。',
 '- 这些结果是公开道路照片的离线推理，不是新权重在实际OV5640画面上的准确率或速度。当前摄像头工程仍为单帧快照检测，不能称为实时检测。',
 '- 这224张图片已完成一次固定候选验收。若后续根据结果调参，应将它们视为开发数据，不能重复称作新的独立测试。',
 f"- 候选 checkpoint SHA256：`{export['source_checkpoint_sha256']}`。",
 f"- 候选 C/FPGA 布局权重 SHA256：`{export['weights_sha256']}`。",
 f"- 原始独立结果：`{ROOT/'fresh_result.json'}`。",
 f"- 开发集C复核：`{ROOT/'c_development_result.json'}`。",
 f"- 原稳定版验收：`{BASE/'road_camera_snapshot_20261030_r1/board_verified.json'}`。",'']
 workspace=Path(__file__).resolve().parents[2];path=workspace/'模型视图微调验收_20261030.md';path.write_text('\n'.join(report),encoding='utf-8')
 write(workspace/'当前模型优化实验_20261030.json',dict(status='NEW_MODEL_OFFLINE_ACCEPTED_NOT_BOARD_TESTED' if result['accepted'] else 'NEW_MODEL_OFFLINE_REJECTED_RETAIN_ABI24',experiment=str(ROOT),report=str(path),result=str(ROOT/'fresh_result.json'),weights_sha256=export['weights_sha256'],active_verified_camera_version=24,board_tested=False,sd_written=False))
 print('VIEWADAPT_REPORT_SAVED',result['accepted'],flush=True)

if __name__=='__main__':main()
