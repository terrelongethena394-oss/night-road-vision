"""Report every prespecified development contrast; never call it independent proof."""
from pathlib import Path
import json,shutil,zipfile
from road_enhanced_detection_common import read,write,sha
from study_roi_enhancement_attribution_20261031 import ROOT,METHODS

def main():
    result=read(ROOT/'selected.json');assert result['reused_development_images']==480
    eligibility=read(ROOT/'roi_eligibility.json')
    assert all(n==eligibility['rois']*len(METHODS) for n in result['verification_forwards'].values())
    out=Path.cwd()/'增强输入因果检验_20261031';out.mkdir(exist_ok=True)
    for rel in ['selected.json','protocol.json','input_invariants.json','source_audit.json','prior_study_scope.json','roi_eligibility.json','method_count_clarification.json','execution_equivalence.json','execution_restart_receipt.json']:
        if (ROOT/rel).exists():shutil.copy2(ROOT/rel,out/rel)
    names={'raw':'原图','learned10':'现有增强10%混合','learned25':'现有增强25%混合','learned50':'现有增强50%混合','learned100':'现有增强100%',
           'gamma090':'轻度伽马0.90','gamma075':'伽马0.75','offset4':'暗部偏移4','offset8':'暗部偏移8','local_shadow':'局部亮度调整'}
    table=[]
    for branch,methods in result['scores'].items():
        for method in METHODS:
            r=methods[method];same=methods['raw']
            gates=next((c for c in result['candidates'] if c['branch']==branch and c['method']==method),None)
            passed='对照' if method=='raw' else ('是' if gates['qualified'] else '否')
            table.append(f"|{'原图训练' if branch=='raw' else '增强训练'}|{names[method]}|{r['ap50']*100:.3f}%|{r['precision']*100:.3f}%|{r['recall']*100:.3f}%|{r['tp']}|{r['fp']}|{(r['ap50']-same['ap50'])*100:+.3f}|{passed}|")
    best=max(result['candidates'],key=lambda c:c['score']['ap50']);r=best['score'];same=result['scores'][best['branch']]['raw'];raw=result['raw_controls'][result['strongest_raw_control']]
    conclusion=('有一个候选通过开发集筛选，但尚未经过新的独立图片验证，不能宣称增强提高了识别效果。' if result['qualified'] else '本轮18个增强设置均未通过预先冻结的完整筛选要求，不能证明增强后检测优于原图检测。没有因此更换板上已验证版本，也没有消耗新的独立测试图片。')
    report=f'''# 增强输入对检测的因果检验

2026-10-31。**{conclusion}**

## 这轮具体检验了什么

480张此前已使用的暗光开发图片，4308个汽车标注。共同前级使用原图RAW7产生候选框；在完全相同的最多8个160×96原生分辨率车辆区域内，比较原图与增强图作为二次核验网络的输入。各方案的区域位置、裁剪缩放、网络结构、推理次数、检测阈值、NMS及框融合规则相同；在同一套权重内进行原图/增强输入对照，权重保持不变。增强只改变像素，不读取标注。

两套已冻结的8轮训练权重，各运行原图与9种增强设置，共20条路线（2条原图对照、18条增强路线）。没有新增训练，也没有为某条路线单独调置信度。

每条路线核验相同的{eligibility['rois']}个区域，其中{eligibility['eligible']}个原图平均亮度≤48，符合增强条件；另{eligibility['unchanged_bright']}个亮度足够，按预设规则保持原图。不能把所有核验区域都描述成已经增强。

范围是“车辆区域增强后核验”，不是“整幅图所有推理都用增强输入”。整图增强的既有失败实验仍保留，未被本轮覆盖。

## 全部结果

AP50使用IoU=0.5；精确率、召回率、TP、FP使用固定置信度0.25。ΔAP50按同一套权重的原图输入计算，单位为百分点。“通过”要求同时胜过最强原图ROI对照和旧RAW7，并通过同权重归因对照。

|权重|核验输入|AP50|精确率P|召回率R|TP|FP|ΔAP50|全部通过|
|---|---|---:|---:|---:|---:|---:|---:|---|
{chr(10).join(table)}

开发集中AP50最高的增强设置为：**{'原图训练' if best['branch']=='raw' else '增强训练'}权重＋{names[best['method']]}**。AP50为{r['ap50']*100:.3f}%，相对同权重原图输入变化{(r['ap50']-same['ap50'])*100:+.3f}个百分点，相对最强原图ROI对照变化{(r['ap50']-raw['ap50'])*100:+.3f}个百分点。它是否通过全部门槛：**{'是' if best['qualified'] else '否'}**。最高AP仅为选优后的开发集结果，不是独立证明。

## 判断门槛及证据边界

增强候选相对最强原图ROI对照、旧RAW7，均要求AP50至少增加0.5个百分点，精确率不下降，召回率至少增加0.5个百分点，误检不增加，F1至少增加0.5个百分点；相对同权重原图输入，要求AP50至少增加0.2个百分点、正确检出不减少、误检不增加。完整逐项布尔结果在`selected.json`，未因结果不好而降低门槛。

480张均已用于开发和本次选优，不能把它们当成独立测试集，也不能从中挑成功照片来证明普遍改善。原ABI30的独立304张只证明原图区域核验相对旧版的改进，本轮未重新使用它们来选择增强方案。

只有开发筛选通过后，才允许冻结一个候选，先核对C实现，再检验未使用过的240张夜间与64张正常亮度图片。独立阶段还要求预设对照下配对分组bootstrap的99% AP50增益区间下限大于0；不得失败后换另一个候选重复尝试同一测试集。

## 评测实现核对

合成输入40项检查通过。为缩短计算时间，在未读取任何准确率结果时，重启了一次相同实验，替换为逐字节相同的C预处理，并合并GPU批次。16张合成图和24个真实开发ROI的预处理逐字节一致，24个ROI的有效输出框坐标、分数抽查差异均为0；变换函数AST也核对一致。原始冻结协议与原始源文件、重启记录均保留，只有协议中“19”这一文字计数误差另附更正：实际是18条增强路线。

GPU开发推理核验次数：{json.dumps(result['verification_forwards'],ensure_ascii=False)}；各路线共有相同的RAW7前级。这些开发结果不是CPU C全链路独立验收，也不是新版本实板证据。

`像素检查`内两处区域按固定哈希顺序抽取，再取最高置信的合格候选，未按增强效果挑选。第一处雨夜区域在强增强后更亮、颗粒更明显，轮廓未明显改善；第二处亮度足够而保持不变。它们只辅助检查像素，不用于证明准确率。

当前开发板、SD卡、Flash均未改动。当前实际运行版本仍是上一轮已验收的ABI30；此前“增强显示＋原图识别”的结论保持不变。

既有全图增强、全局增强专家适配、七视图增强、同预算原图/伽马训练及ROI小样本实验的结果索引保存在`prior_study_scope.json`。这些都是开发实验，不是本轮新增的独立证明；保留它们是为了避免重复尝试已失败的路径。
'''
    (out/'检验结论与全部对照.md').write_text(report,encoding='utf-8')
    shutil.copytree(ROOT/'fixed_pixel_inspection',out/'像素检查',dirs_exist_ok=True)
    for name in ['fast_roi_attribution_runtime_20261031.py','audit_roi_attribution_inputs_20261031.py',
                 'audit_roi_attribution_sources_20261031.py','restart_roi_attribution_execution_20261031.py',
                 'report_roi_attribution_20261031.py','road_accuracy_common.py','road_arm_common.py',
                 'road_numpy_eval.py','pilot_car_roi_verify_20261031.py','road_roi_input_enhance.c',
                 'prove_roi_input_enhance_20261031.py','collect_enhancement_study_status_20261031.py',
                 'inspect_roi_attribution_pixels_20261031.py','count_roi_enhancement_eligibility_20261031.py']:
        shutil.copy2(Path(__file__).with_name(name),ROOT/'source'/name)
    archive=ROOT/'ROI_enhancement_development_evidence_20261031.zip';files=[]
    for p in ROOT.rglob('*'):
        if p.is_file() and p!=archive and p.name!='report_complete.json' and '__pycache__' not in p.parts:files.append(p)
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
        for p in files:z.write(p,'study/'+p.relative_to(ROOT).as_posix())
        for p in out.glob('*'):
            if p.suffix in ['.md','.json'] and p.name!='归档校验.json':z.write(p,'report/'+p.name)
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    receipt=dict(path=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),crc_verified=True,enhanced_input_superiority_established=False,new_independent_test_used=False,hardware_access=False,sd_written=False)
    write(out/'归档校验.json',receipt)
    write(ROOT/'report_complete.json',dict(report=str(out),archive=receipt,qualified_for_next_stage=result['qualified']))
    print('ROI_ATTRIBUTION_DEVELOPMENT_REPORT_COMPLETE',receipt,flush=True)

if __name__=='__main__':main()
