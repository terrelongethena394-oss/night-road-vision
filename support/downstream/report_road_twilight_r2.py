"""Write a result report from frozen evidence, without changing any model choice."""
from pathlib import Path
import shutil
from road_twilight_r2_common import ROOT,PREV,read,write,sha

WORK=Path(__file__).resolve().parents[2]

def main():
 s=read(ROOT/'selected.json');train=read(ROOT/'training_complete.json')
 assert train['matched_sampler_plans']
 fresh=read(ROOT/'fresh_complete.json') if (ROOT/'fresh_complete.json').exists() else None
 if fresh is None:assert (ROOT/'holdout_not_consumed.json').exists()
 decision=fresh['deployment_decision'] if fresh else 'retain_current'
 board=read(ROOT/'firmware/session_r1.json') if (ROOT/'firmware/session_r1.json').exists() else None
 running=bool(board and board['status']=='NEW_MODEL_QUALITY_AND_BOARD_VALIDATED_RUNNING')
 rows=['# 黄昏与夜间检测改进实验（2026-10-27）','',
  '本报告区分模型训练带来的提升、运行时图像增强带来的提升，以及实际下载到板卡后的状态。mAP@0.5 是检测指标，不能称作识别准确率。', '',
  '## 完成内容','',
  '- 新增 600 张带真实标注的训练图片：400 张 dawn/dusk，200 张夜间；训练集总计 3000 张。',
  '- 两组使用相同初始化、采样顺序、翻转、标签、优化步数和教师约束。对照组输入原图／原图，增强组输入原图／增强图。',
  '- 两组各训练 8 轮；冻结批归一化运行统计，保留原始模型的正样本响应和中间特征，以减少旧场景性能遗忘。',
  '- 模型结构保持 YOLOv5n 四类：行人、小汽车、卡车、公交车；输入 320×320，部署精度 FP32。',
  '- 增强曲线固定为板上现有的自适应 Gamma，未根据测试结果挑曲线。',
  '- 第一轮匹配训练两组各16轮，没有通过旧验证准入，未消耗新测试。第二轮补充600张数据、加入教师约束，两组各8轮，再执行新480张测试。', '',
  '## 用于选择模型的旧验证集（320 张）','',
  '| 输入与模型 | 全部 | 黎明／黄昏 | 夜间 | 日间 |',
  '|---|---:|---:|---:|---:|']
 def table(label,m):
  return '| '+label+' | '+' | '.join(f'{100*v:.2f}%' for v in [m['all']['mAP50'],m['by_time']['dawn/dusk']['mAP50'],m['by_time']['night']['mAP50'],m['by_time']['daytime']['mAP50']])+' |'
 rows += [table('现有模型／原图',s['original']),table(f"匹配对照，第 {s['control']['epoch']} 轮／原图",s['control_metrics']),table(f"增强训练，第 {s['candidate']['epoch']} 轮／原图",s['candidate_raw']),table('同一增强训练模型／增强图',s['candidate_enhanced'])]
 rows += ['',f"所有检查点只根据上述旧验证集选择；增强分支通过旧验证准入：{'是' if s['enhancement_validation_accepted'] else '否'}。",'', '## 独立留出的新图片测试','']
 if fresh:
  rows += ['480 张此前未用于这些模型训练或选择的新图片：160 张黎明／黄昏、192 张夜间、128 张日间。按文件名前缀组排除已有划分，并核对图片哈希。', '',
   '| 输入与模型 | 全部 | 黎明／黄昏 | 夜间 | 日间 |','|---|---:|---:|---:|---:|',
   table('现有模型／原图',fresh['original']),table('匹配对照／原图',fresh['raw_control']),table('增强训练模型／原图',fresh['candidate_raw']),table('增强训练模型／增强图',fresh['candidate_enhanced']),'']
  u=fresh['uncertainty']
  for label,k in [('原图对照模型减现有模型','raw_control_minus_original'),('增强分支减匹配原图对照','enhanced_minus_matched_raw')]:
   lo,hi=u[k];rows.append(f'- {label}：黎明／黄昏 mAP@0.5 差值的配对 bootstrap 97.5% 区间 [{lo*100:+.2f}, {hi*100:+.2f}] 个百分点。')
  rows += ['', '每个比较使用 1000 次配对图像／组重采样；两个比较各采用 97.5% 区间作为多重比较的保守措施。区间包含 0 时不能声称稳定提升。新测试结果未用于重新选择检查点。','', '固定准入检查：','', '| 方案 | 检查 | 结果 |','|---|---|---|']
  for title,key in [('原图升级','raw_fallback_gates'),('增强升级','enhanced_point_gates')]:
   for k,v in fresh[key].items():rows.append(f"| {title} | {k} | {'通过' if v else '未通过'} |")
  rows += ['',f"预先固定规则得出的部署决策：`{decision}`。"]
 else:
  rows += ['旧验证集没有达到预先固定的升级条件，因此没有消耗新 480 张测试集的预测结果。保留该测试集，避免反复选模型造成测试集泄漏。']
 diagnosis=read(ROOT/'error_diagnosis.json') if (ROOT/'error_diagnosis.json').exists() else None
 if diagnosis:
  rows += ['', '## 漏检诊断（测试后的描述性分析）','',
   '以下用于解释失败原因，不据此重新挑选已评测模型或调整发布门槛。高度指进入网络后目标框高度，工作点置信度 0.25、IoU 0.5。','',
   '| 场景 | 行人数 | 高度不足16像素 | 其中原模型检出 | 全部原模型检出 |','|---|---:|---:|---:|---:|']
  for period,title in [('dawn/dusk','黎明／黄昏'),('night','夜间')]:
   allp=next(r for r in diagnosis['objects'] if r['timeofday']==period and r['cls']=='person' and r['dimension']=='all')
   tiny=next(r for r in diagnosis['objects'] if r['timeofday']==period and r['cls']=='person' and r['dimension']=='input_height' and r['bucket']=='<16px')
   rows.append(f"| {title} | {allp['objects']} | {tiny['objects']} | {tiny['original_tp']} | {allp['original_tp']} |")
  light=diagnosis['brightness']['dawn/dusk'];rows += ['',f"160 张黎明／黄昏图中有 {light['bypassed']} 张全局亮度达到自动旁路条件，只有 {light['changed']} 张实际改变了像素。整体场景标签不等于每个目标局部都很暗。该观察不证明放宽提亮门槛就会改善识别。"]
  if fresh:
   a=fresh['original']['by_time']['night']['classes'];b=fresh['raw_control']['by_time']['night']['classes']
   rows += ['',f"夜间对照组总 mAP 虽由 {100*fresh['original']['by_time']['night']['mAP50']:.2f}% 升至 {100*fresh['raw_control']['by_time']['night']['mAP50']:.2f}%，行人 AP 却由 {100*a['person']['ap50']:.2f}% 降至 {100*b['person']['ap50']:.2f}%。不能把总平均值提升解释为行人安全性提升。夜间公交只有 {a['bus']['objects']} 个目标，少数类别的波动会影响四类平均值。"]
 roi_path=ROOT.parent/'road_center_roi_20261027/complete.json'
 if roi_path.exists():
  roi=read(roi_path);a=roi['baseline']['by_time']['dawn/dusk'];b=roi['candidate']['by_time']['dawn/dusk']
  rows += ['', '## 保留中心区细节的额外可行性试验','',
   '从原始 800×480 传感器代理图中保留中心 400×240 像素，再额外运行一次同一检测器，与全景结果合并。该方法利用原本存在的像素，不是超分辨率，也不是新的增强神经网络。','',
   f"只在旧验证集：黎明／黄昏 mAP@0.5 {a['mAP50']*100:.2f}% → {b['mAP50']*100:.2f}%；行人召回 {a['classes']['person']['recall']*100:.2f}% → {b['classes']['person']['recall']*100:.2f}%。",
   f"固定可行性检查：{roi['gates']}。原图行人误检 {a['classes']['person']['fp']} 个，未校准合并后 {b['classes']['person']['fp']} 个。",
   '这会从一次推理增加到两次，预计推理时间接近翻倍；尚未测量板上延迟。未做新留出集测试，未接入或替换当前摄像头程序。验证集结果不能称为部署收益。']
  shutil.copy2(roi_path,ROOT/'center_roi_feasibility.json')
  cp=roi_path.parent/'classwise/complete.json'
  if cp.exists():
   cal=read(cp);a=cal['baseline']['by_time']['dawn/dusk'];b=cal['candidate']['by_time']['dawn/dusk']
   rows += ['',f"进一步只用旧验证集进行置信度校准。四类权重 {cal['weights']}；误检受控时，黎明／黄昏 mAP@0.5 {a['mAP50']*100:.2f}% → {b['mAP50']*100:.2f}%，行人召回 {a['classes']['person']['recall']*100:.2f}% → {b['classes']['person']['recall']*100:.2f}%。仍未达到事先设定的行人召回增加3个百分点的要求，因此没有下载新测试集或替换板上程序。未通过时未放宽发布门槛。"]
   shutil.copy2(cp,ROOT/'center_roi_calibration.json')
 rows += ['', '## 当前部署状态','']
 if running:
  rows += [f"新模型已通过实际板卡测试并运行，ABI14，默认 pipeline={board['default_pipe']}。", '同一物理输入的 CPU／FPGA 检测头、解码、NMS 结果逐字节一致；固定 8 例、首例全部 86 个张量及摄像头画面／显示缓冲均已校验。']
 elif decision!='retain_current':
  rows += ['离线升级准入已通过；是否完成 C 数值校验、ARM 编译及实板验收，以对应文件为准。当前未取得新模型运行成功收据，不能声称已上板成功。']
 else:
  rows += ['没有将本轮未通过的候选模型替换到板上。保留此前 ABI13：增强显示、原图检测。新的 C 数值校验、ARM 构建和上板脚本已准备，但本轮未进入这些阶段，不能视为已编译或实板验收的新版本。']
 rows += ['SD 卡与 Flash 未写入。未测得新摄像头持续帧率时，不沿用其他量化实验的帧率。','', '## 结论边界','',
  '- BDD100K 的 dawn/dusk 是黎明与黄昏合并标签；本实验不能单独证明黄昏或本机 OV5640 的提升。',
  '- 新留出集仍来自同一数据源；按文件前缀和图像哈希排除重叠，不等于已经证明跨城市、跨摄像头泛化。',
  '- Gamma 提亮是传统图像处理；神经网络是后端检测器。原图检测器训练改进不能作为“增强改善检测”的证据。',
  '- 这是竞赛感知演示系统，尚未完成道路连续视频、运动模糊、雨雾和本机固定场景照明对照。','', '## 复核文件','',
  f'- [训练脚本]({WORK.as_posix()}/starter/downstream/train_road_twilight_r2.py)',
  f'- [固定实验协议]({ROOT.as_posix()}/protocol.json)',
  f'- [模型选择与全部验证结果]({ROOT.as_posix()}/selected.json)',
  f'- [训练完成记录]({ROOT.as_posix()}/training_complete.json)']
 for p in [ROOT/'fresh_complete.json',ROOT/'error_diagnosis.json',roi_path,ROOT/'native_complete.json',ROOT/'firmware/arm_complete.json',ROOT/'firmware/board_fixed_r1/validated.json',ROOT/'firmware/session_r1.json']:
  if p.exists():rows.append(f'- [{p.name}]({p.as_posix()})')
 path=WORK/'黄昏夜间检测改进结果_20261027.md';path.write_text('\n'.join(rows)+'\n',encoding='utf-8');shutil.copy2(path,ROOT/'RESULTS_CN.md')
 paths=[ROOT/n for n in ['protocol.json','training_config.json','prepare_complete.json','selected.json','training_complete.json','fresh_release_policy.json','fresh_complete.json','holdout_not_consumed.json','error_diagnosis.json','center_roi_feasibility.json','center_roi_calibration.json','native_complete.json','firmware/arm_complete.json','firmware/session_r1.json','firmware/board_fixed_r1/validated.json']]
 write(ROOT/'result_evidence.json',dict(decision=decision,board_running_receipt=running,evidence_sha256={str(p.relative_to(ROOT)):sha(p) for p in paths if p.exists()},report_sha256=sha(path),report=str(path),sd_written=False,flash_written=False))
 print('TWILIGHT_RESULT_REPORT_WRITTEN',path,decision,'board_running',running,flush=True)

if __name__=='__main__':main()
