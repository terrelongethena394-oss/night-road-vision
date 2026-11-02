"""Evidence-specific report; never call rare-class precision overall accuracy."""
from road_brightness_route_common import *

def main():
 r=read(ROOT/'fresh_result.json');a=r['low_baseline']['all'];b=r['low_candidate']['all'];ca=a['classes'];cb=b['classes'];tp=lambda z:sum(z[k]['tp'] for k in ['truck','bus']);fp=lambda z:sum(z[k]['fp'] for k in ['truck','bus']);p=lambda z:tp(z)/(tp(z)+fp(z));ci=r['uncertainty'];workspace=Path(__file__).resolve().parents[2]
 text=['# 暗光分场景模型：独立验收（2026-10-30）','',
 ('结论：通过新416张图片的独立离线验收，尚未上板验收。' if r['accepted'] else '结论：未通过新416张图片的完整独立验收，保留ABI24稳定版，不下载失败候选。'),'',
 '新系统先读取未增强全图的平均亮度；≤48使用微调权重及固定卡车/公交车分数映射，>48使用原稳定模型。每张图片只运行其中一个模型的四个视图，没有把两模型结果做集成。图像增强算法保持原状。','',
 '此规则是在上一轮无条件替换模型失败后提出，并在新416张图片推理之前冻结。旧224张结果明确作为开发数据使用，没有继续称作此规则的独立测试。新416张图片排除所有已记录训练、评测、亮度筛选的前缀组和图像哈希；按原始亮度选择320张低亮度、96张较亮照片，没有按检测结果筛选。','',
 '## 320张新低亮度图片','',
 '| 指标 | 稳定算法 | 暗光候选 |','| --- | ---: | ---: |',
 f"| 汽车 AP50 | {ca['car']['ap50']*100:.2f}% | {cb['car']['ap50']*100:.2f}% |",
 f"| 汽车精确率（阈值0.25） | {ca['car']['precision']*100:.2f}% | {cb['car']['precision']*100:.2f}% |",
 f"| 汽车召回率（阈值0.25） | {ca['car']['recall']*100:.2f}% | {cb['car']['recall']*100:.2f}% |",
 f"| 四类 mAP50 | {a['mAP50']*100:.2f}% | {b['mAP50']*100:.2f}% |",
 f"| 卡车/公交车正确检出 TP | {tp(ca)} | {tp(cb)} |",
 f"| 卡车/公交车误检 FP | {fp(ca)} | {fp(cb)} |",
 f"| 卡车/公交车精确率 | {p(ca)*100:.2f}% | {p(cb)*100:.2f}% |",'',
 '工作点为置信度0.25、IoU0.5。AP50跨置信度计算；不能把AP50当作正确识别图片的百分比。', '',
 f"卡车/公交车精确率差值的99.5%配对图像自助法区间：[{ci['precision_difference_interval995'][0]*100:+.2f}, {ci['precision_difference_interval995'][1]*100:+.2f}]个百分点。",
 f"汽车AP50差值的99.5%区间（描述性）：[{ci['car_ap50_difference_interval995_descriptive'][0]*100:+.2f}, {ci['car_ap50_difference_interval995_descriptive'][1]*100:+.2f}]个百分点。",'',
 '主要假设是暗光下卡车/公交车误检减少和精确率提高，并满足已冻结的检出保留条件。汽车AP50只有在区间排除0时才有支持稳定提升的证据；不能把本试验概括成所有类别、所有场景准确率都提高。','',
 '## 较亮场景和实现检查','',
 '- 96张较亮照片由独立C进程重新执行稳定权重；四个视图的全部检测结果以及融合结果均与基准逐字节一致。',
 '- 全部416张图的亮度路由由C整数实现决定，并与独立浮点亮度参考一致。阈值临界值、输入不被改写等检查保留在router_c。',
 '- 暗光校准由C执行，并与NumPy参考逐字节核对。',
 '- 当前结果来自电脑端实际C神经网络推理，尚不是此候选的ARM/FPGA上板验收，也不是实物摄像头识别准确率。',
 '- 尚未访问开发板或修改SD/Flash；已验证ABI24摄像头单帧版保留。',
 '- 夜间/白天元数据可能存在误标，本实验以原始图像平均亮度门限定义工作场景，不声称测量了实际照度。','',
 '## 各类AP50','', '| 类别 | 稳定版 | 暗光候选 |','| --- | ---: | ---: |']
 for k in NAMES:text.append(f"| {k} | {ca[k]['ap50']*100:.2f}% | {cb[k]['ap50']*100:.2f}% |")
 text+=['','未通过的低亮度验收项：'+(', '.join(k for k,v in r['low_gates'].items() if not v) or '无')+'。','',f'原始结果：`{ROOT/"fresh_result.json"}`。',f'协议：`{ROOT/"protocol.json"}`。','']
 path=workspace/'暗光分场景模型验收_20261030.md';path.write_text('\n'.join(text),encoding='utf-8');write(workspace/'当前暗光分场景候选_20261030.json',dict(status='OFFLINE_ACCEPTED_NOT_BOARD_TESTED' if r['accepted'] else 'OFFLINE_REJECTED_RETAIN_ABI24',experiment=str(ROOT),report=str(path),model_sha256=r['model_sha256'],active_verified_camera_version=24,board_tested=False,sd_written=False));print('ROUTED_MODEL_REPORT_SAVED',r['accepted'],flush=True)

if __name__=='__main__':main()
