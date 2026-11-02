"""Recommend a raw-inference next-stage candidate without rewriting failed enhancement studies."""
from pathlib import Path
from road_enhanced_detection_common import BASE,read,write,sha,gates,f1
def main():
    root=BASE/'road_car_roi_trainaug_20261031_r1';s=read(root/'selected.json');initial=read(root/'initial_control_result.json');assert not s['qualified']
    m=s['scores']['matched_raw'];base=s['scores']['baseline'];same_roi=initial['scores'];gg=dict(old_raw7=gates(base,m),initial_same_roi=gates(same_roi,m));assert all(all(v.values()) for v in gg.values())
    model=BASE/'road_allview_gammafit_20261031_r1/frozen/raw8/model.pt';assert sha(model)==s['main_control_sha256']
    out=Path(__file__).resolve().parents[2]/'增强识别优化验证_20261031';out.mkdir(exist_ok=True)
    receipt=dict(status='PROPOSED_RAW_ROI_NEXT_PHASE_CANDIDATE_DEVELOPMENT_ONLY',original_enhanced_inference_goal_completed=False,enhancement_at_detection_inference=False,augmentation_training_advantage_confirmed=False,
      scope='480alreadyexposeddevelopmentimages/4308carannotations;pilot64included,notindependent',candidate_weights=str(model),candidate_weights_sha256=sha(model),candidate=m,baseline=base,initial_same_roi_control=same_roi,development_gates=gg,
      raw_roi_candidate_comparison_selected_json_sha256=sha(root/'selected.json'),initial_roi_control_sha256=sha(root/'initial_control_result.json'),
      common_raw7_proposal_forwards=3360,native_roi_verification_forwards=s['verification_forwards']['matched_raw'],independent_tested=False,firmware_ready=False,board_programmed=False,sd_written=False,
      next_steps=['Freeze RAW-inference ROI candidate as separate hypothesis; retain all failed enhancement results.','Verify portable C ROI planning, resizing, model outputs and postprocessing.','Confirm on unused image/prefix groups with original annotations and paired uncertainty.','Only after qualified confirmation, JTAG/RAM board validation and framebuffer readback; retain SD.'])
    write(out/'二次核验全量结果_未上板.json',receipt)
    lines=['# 下一步：二次核验独立验收','',
      '本轮找到的有效方向是利用原始800×480图像中的小车细节，裁剪后放大并再次检测，改善定位和误检。它仍使用原图作为检测输入；不能称为增强图输入优于原图。',
      '', '480张已使用开发图、4308个汽车标注；置信度0.25、IoU0.5固定。不是独立测试。','',
      '| 方案 | 汽车AP50 | 精确率 | 召回率 | F1 | 正确检出 | 误检 |','|---|---:|---:|---:|---:|---:|---:|']
    for label,v in [('现有RAW7',base),('原稳定权重＋同样ROI核验',same_roi),('重训RAW8＋ROI核验（建议候选）',m),('增强训练权重＋原图ROI核验',s['scores']['candidate'])]:
        lines.append(f"| {label} | {100*v['ap50']:.2f}% | {100*v['precision']:.2f}% | {100*v['recall']:.2f}% | {100*f1(v):.2f}% | {v['tp']} | {v['fp']} |")
    lines += ['', '建议候选相对当前RAW7多检出44辆汽车、减少956个误检。相对相同ROI/计算预算的原稳定权重，AP、精确率和召回率也提高；这仍只是开发结果。', '',
      '64张预验证中增强训练看似占优，完整480张上未保持优势，原“增强训练胜出”研究按原门槛判为失败，selected.json保持不变。这里单独记录的是原图推理候选，不改写前一项失败结果，也不声称完成了“增强后直接识别更好”的要求。','',
      '下一步按顺序执行：冻结该候选和独立验收指标；核对C版裁剪、网络与后处理；用未参与调参的来源图片验收；通过后JTAG临时上板，读回结果和实际屏幕确认。板上仍是ABI29，SD卡和Flash均未改动。', '',
      '检测与显示的指标分开：图像增强展示亮度/细节变化，检测展示AP50、精确率、召回率、误检、漏检以及每张处理耗时。展示增强不应被描述成检测输入或准确率收益来源。']
    (out/'下一步与二次核验结果.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(dict(report=str(out/'下一步与二次核验结果.md'),raw_roi_development_gates=gg,original_enhancement_goal_complete=False,hardware_programmed=False))
if __name__=='__main__':main()
