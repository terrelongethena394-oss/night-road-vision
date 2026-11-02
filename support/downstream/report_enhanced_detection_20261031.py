"""Consolidate actual results, preserving failed gates and dataset scope."""
from pathlib import Path
import shutil,zipfile,json,hashlib
from road_enhanced_detection_common import BASE,read,write,sha,f1
def main():
    workspace=Path(__file__).resolve().parents[2];out=workspace/'增强识别优化验证_20261031';out.mkdir(exist_ok=True)
    studies={k:BASE/name for k,name in dict(global_fit='road_enhanced_detection_20261031_r1',spatial_gate='road_task_gate_20261031_r1',allview='road_allview_enhance_20261031_r1',allview_fit='road_allview_gammafit_20261031_r1',exposure_band='road_exposure_route_20261031_r1',specialist='road_gamma_specialist_route_20261031_r1',dual_exposure='road_dual_exposure_20261031_r1',task_router='road_task_router_20261031_r1',matched_tta='road_gammafit_tta_20261031_r1').items()}
    selected={k:read(p/'selected.json') for k,p in studies.items() if (p/'selected.json').exists()}
    initial=selected['allview']['scores']['raw'];fit=next(r for r in selected['allview_fit']['records'] if r['epoch']==8)['scores']['enh'];rawflip=selected['dual_exposure']['raw_flip_control']['scores'];rows=[('当前稳定检测 RAW 7视图',initial),('新增强适配 ENH8 7视图',fit),('原图翻转融合 RAW 14视图',rawflip)]
    if 'matched_tta' in selected:
        rows.append(('重训原图 + 翻转融合 RAW 14视图',selected['matched_tta']['matched_raw_flip_control']['scores']))
        rows.append(('新增强适配 + 翻转融合 ENH 14视图',selected['matched_tta']['best_descriptive']['scores']))
    table=['| 方案 | 汽车AP50 | 精确率P | 召回率R | F1 | 正确检出TP | 误检FP |','|---|---:|---:|---:|---:|---:|---:|']
    for name,m in rows:table.append(f"| {name} | {m['ap50']*100:.2f}% | {m['precision']*100:.2f}% | {m['recall']*100:.2f}% | {f1(m)*100:.2f}% | {m['tp']} | {m['fp']} |")
    qualified=[k for k,s in selected.items() if s['qualified']];pending=[k for k in studies if k not in selected]
    status='有候选通过开发集门槛，仍需实际C、独立测试和上板验收。' if qualified else '本轮尚无方案通过完整的增强检测验收门槛。'
    if pending:status+='仍在进行：'+','.join(pending)+'。'
    report='''# 增强后汽车检测优化记录（2026-10-31）

'''+status+'''

这份记录区分画面提亮、检测收益和上板结果。当前开发板仍为已验收ABI29；增强显示不等于增强输入检测。以下新研究尚未下载到板卡，SD卡和Flash未修改。

## 同一开发集上的实际比较

480张已反复使用的暗光道路图片，4308个汽车(car)标注；不把卡车和公交车计入这些数字。固定检测置信度0.25、匹配IoU0.5。各方案均保留完整低分预测计算AP50，TP/FP/FN在固定置信度处统计。

'''+ '\n'.join(table)+'''

以上是开发结果，包含模型/参数选择带来的乐观偏差，不能作为新独立测试准确率。不同方案7或14次主网络前向，不能把额外推理带来的收益全算作增强效果。新增强适配ENH8比稳定版多检出42辆汽车、增加10个误检；尚未通过此前冻结的完整门槛。

新增强适配加翻转融合的开发候选比板上RAW7多检出54辆、减少190个误检，AP50增加约2.69个百分点。但与原图翻转的对等计算量对照相比，其精确率、误检数和F1仍较差，所以它不是已证实最优的增强方案，尚未获准作为本轮验收通过版替换板上程序。三组指标(AP、P、R)不能用一句“准确率”混在一起。

## 实际做过的工作

- 原图/增强全图专家各12轮训练；另做原图/增强全图与细节适配各12轮训练，权重确实更新。
- 冻结检测器训练153参数增强强度网络，比较轻度Gamma、论文光照估计参考和ABI29混合增强在全部7视图上的效果。
- 比较预先定义的亮度分段、专家路由、原图与增强双路融合，保留原图翻转融合的同计算量对照。
- 在1060张原始训练暗光图上计算增强前后检测得失，训练1155参数图像内容控制网络；训练来源与开发来源分组隔离。该网络未通过开发集门槛。
- 完成相同14次前向的翻转融合对照：原图训练专家、增强专家的原图输入、增强专家的增强输入均使用相同36组融合配置。未通过的结果完整保留。
- Gamma C实现272组像素检查逐字节一致。控制网络特征/计算核45组预检查通过；这些仅是实现一致性检查，不是准确率通过或上板证明。

所有未通过方案的原始门槛和失败结果都保留。没有放宽IoU、改图片标注、换测试集挑图来宣称提升，也没有将依赖真实标注的诊断选择器当作可部署模型。

## 图片如何看

`增强正例与反例.png`同时展示增强有利和不利的真实道路开发例。绿色是正确检出，橙色是误检，紫色是漏检标注；例子按结果选择并明确标出，因此只能解释现象，不能代替全量指标。

## 验收条件与当前边界

本轮完整门槛包含：对既定原图对照，AP50至少增加0.5个百分点，精确率不下降、召回率至少增加0.5个百分点、误检数不增加、F1至少增加0.5个百分点；另有同模型原图输入的归因对照。门槛是在相应候选结果出现前保存的，未因结果不通过而追改。

只有通过的候选才进入新的独立图片确认和实际上板；独立确认仍需同样门槛及成对图像重采样的99%AP收益区间为正。本轮尚未接触新的独立确认图片。不能保证继续调参一定提高，也不能用开发集的小幅提升代替该证据。

'''
    (out/'优化记录.md').write_text(report,encoding='utf-8')
    result=dict(status='DEVELOPMENT_CANDIDATE_REQUIRES_FURTHER_ACCEPTANCE' if qualified else 'NO_ENHANCEMENT_CANDIDATE_ACCEPTED_YET',qualified_development_studies=qualified,pending=pending,metrics=[dict(name=n,**m,f1=f1(m)) for n,m in rows],study_results={k:dict(status=s['status'],qualified=s['qualified'],path=str(studies[k]/'selected.json'),sha256=sha(studies[k]/'selected.json')) for k,s in selected.items()},new_independent_test_used=False,hardware_programmed=False,sd_written=False,flash_written=False,current_board_version=29)
    write(out/'实际结果汇总.json',result)
    if 'matched_tta' in selected:
        tta=selected['matched_tta'];best=tta['best_descriptive'];checkpoint=BASE/'road_allview_gammafit_20261031_r1/frozen/enh8/model.pt';assert sha(checkpoint)==tta['main_checkpoint_sha256']
        write(out/'增强检测候选_未上板.json',dict(status='DEVELOPMENT_ONLY_FAILED_FULL_ACCEPTANCE_NOT_BOARD_FIRMWARE',main_checkpoint=str(checkpoint),main_checkpoint_sha256=sha(checkpoint),enhancement='Classical hue-preserving Gamma0.8,cap3,highlightfade.65..98;owncropmeanY>48bypass. Detection NN newlyfine-tuned ENH8,not a new neural pixel enhancer.',views='7sourceviews +7horizontal-flippedviews,same frozen RAWsource for boxrefiner',fusion_config=best['config'],development_scores=best['scores'],failed_gates=best['gates'],fusion_dll=str(BASE/'road_dual_exposure_20261031_r1/fusion.dll'),fusion_dll_sha256=sha(BASE/'road_dual_exposure_20261031_r1/fusion.dll'),independent_tested=False,board_programmed=False,sd_written=False,not_bitstream=True))
    files={}
    for kind,root in studies.items():
        for n in ['protocol.json','selected.json','source_audit.json','training_complete.json','history.json','training_config.json']:
            if (root/n).exists():files['studies/'+kind+'/'+n]=root/n
        for p in (root/'source').glob('*'):
            if p.is_file() and p.suffix in ['.py','.c','.h']:files['studies/'+kind+'/source/'+p.name]=p
    for n in ['优化记录.md','实际结果汇总.json','增强正例与反例.png','图例选择记录.json','增强检测候选_未上板.json']:
        if (out/n).exists():files['report/'+n]=out/n
    archive=out/'优化证据_开发阶段.zip';manifest={n:sha(p) for n,p in files.items()}
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for n,p in files.items():z.write(p,n)
        z.writestr('SHA256_MANIFEST.json',json.dumps(manifest,indent=2))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for n,digest in manifest.items():assert hashlib.sha256(z.read(n)).hexdigest()==digest
    write(out/'证据包完整性.json',dict(archive=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,members=len(files)+1,all_member_hashes_verified=True))
    print(dict(report=str(out/'优化记录.md'),status=result['status'],qualified=qualified,pending=pending,archive_bytes=archive.stat().st_size))
if __name__=='__main__':main()
