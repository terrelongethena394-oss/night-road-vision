"""Render all fixed preview cases and package the measured, frozen first round."""
from pathlib import Path
import csv,hashlib,json,os,shutil,sys,time,zipfile
import numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path('E:/FPGA_Enhance_Work/road_detection_20261026')
HERE=Path(__file__).resolve().parent
NAMES=['person','car','truck','bus']
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def percent(v):return f'{100*v:.2f}%' if v is not None else '无该类标注'
def main():
    result=read(ROOT/'test/results.json');frozen=read(ROOT/'frozen/frozen_candidate.json');data=read(ROOT/'dataset/complete.json');protocol=read(ROOT/'training_protocol.json')
    assert result['candidate_sha256']==frozen['model_sha256']==sha(frozen['weights'])
    assert sha(ROOT/'dataset/manifest.json')==protocol['dataset_manifest_sha256']
    assert result['test_images']==data['splits']['test']['images'] and not result['board_deployed'] and not result['sd_written']
    assert not data['group_overlap'] and not data['exact_image_overlap']
    OUT=ROOT/'release';OUT.mkdir(exist_ok=False)
    previews=OUT/'效果图';previews.mkdir()
    evaluation=read(ROOT/'test/evaluation_protocol.json');selected=evaluation['display_examples']
    preds={v:{r['name']:r for r in read(ROOT/'test'/f'{v}_predictions.json')} for v in ['raw400','multinex400','protected400']}
    font=lambda n:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n)
    colors=[(255,170,30),(0,230,255),(220,130,255),(60,255,110)]
    for index,name in enumerate(selected,1):
        canvas=Image.new('RGB',(1248,420),'#f4f6f8');draw=ImageDraw.Draw(canvas)
        draw.text((20,8),'电脑离线检测｜真实道路图｜同一训练后模型与阈值',font=font(25),fill='#172436')
        row=preds['raw400'][name];draw.text((20,45),f'{name}    时段：{row["timeofday"]}',font=font(18),fill='#44546a')
        for i,(view,title) in enumerate(zip(['raw400','multinex400','protected400'],['原图 RAW','固定 Multinex 增强','全局亮度保护输出'])):
            x=16+i*412;draw.text((x,77),title,font=font(22),fill='#172436')
            image=Image.open(ROOT/'test/enhancement_inputs'/(Path(name).stem+'.'+view+'.png')).convert('RGB');d=ImageDraw.Draw(image)
            for p in preds[view][name]['detections']:
                if p[4]<.25:continue
                x1,y1,x2,y2,confidence,k=p;k=int(k);color=colors[k]
                d.rectangle((x1,y1,x2,y2),outline=color,width=2)
                if x2-x1>=55 and y2-y1>=18:
                    label=f'{NAMES[k]} {confidence:.2f}';box=d.textbbox((0,0),label,font=font(11));tx=min(max(0,x1),400-(box[2]-box[0]))
                    d.text((tx,max(0,y1-13)),label,fill=color,font=font(11),stroke_width=1,stroke_fill=(0,0,0))
            canvas.paste(image,(x,112))
            draw.text((x,355),f'匹配标注目标：{len(preds[view][name]["matched_gt"])}',font=font(18),fill='#44546a')
        draw.text((20,390),'颜色：橙=行人，青=汽车，紫=卡车，绿=公交车；小目标仅画框，所有预测均计入评测。',font=font(18),fill='#44546a')
        canvas.save(previews/f'{index:02d}_{Path(name).stem}.png')
    source=OUT/'训练评测脚本';source.mkdir()
    for name in ['prepare_road_detector_assets.py','prepare_road_training_data.py','initialize_road_detector.py','train_road_detector.py','evaluate_road_detector.py','cache_road_training_images.py','finish_road_detector.py']:
        shutil.copy2(HERE/name,source/name)
    shutil.copy2(HERE/'cleanup_road_training_cache.ps1',source/'cleanup_road_training_cache.ps1')
    shutil.copytree(ROOT/'yolov5',OUT/'yolov5',ignore=shutil.ignore_patterns('__pycache__','runs','.git','*.pyc','*.pt'))
    weights=OUT/'权重';weights.mkdir();shutil.copy2(frozen['weights'],weights/'road4_best.pt')
    shutil.copy2(ROOT/'initialization/yolov5n_road4.pt',weights/'road4_initial.pt')
    os.chdir(ROOT/'yolov5');sys.path.insert(0,str(ROOT/'yolov5'))
    import torch,yaml
    from models.yolo import Model
    torch.set_num_threads(4)
    trained=torch.load(weights/'road4_best.pt',map_location='cpu',weights_only=False)['model'].float().eval()
    torch.save(trained.state_dict(),weights/'road4_state_dict.pth')
    (weights/'model.yaml').write_text(yaml.safe_dump(trained.yaml),encoding='utf-8')
    architecture=yaml.safe_load((weights/'model.yaml').read_text());restored=Model(architecture,ch=3,nc=4).float().eval()
    restored.load_state_dict(torch.load(weights/'road4_state_dict.pth',map_location='cpu',weights_only=True))
    torch.manual_seed(2026102621);x=torch.rand(1,3,416,416)
    with torch.inference_mode():a=trained(x)[0];b=restored(x)[0]
    assert torch.allclose(a,b,rtol=1e-5,atol=1e-5)
    write(weights/'state_dict_export_proof.json',dict(status='RESTORED_NETWORK_FORWARD_MATCHES_FROZEN_CHECKPOINT',comparison_dtype='CPU float32 for both networks',max_absolute_error=float((a-b).abs().max()),source_sha256=sha(weights/'road4_best.pt'),state_dict_sha256=sha(weights/'road4_state_dict.pth'),parameters=sum(p.numel() for p in trained.parameters())))
    records=OUT/'协议与评测';records.mkdir()
    for name in ['assets.json','training_protocol.json','baseline_validation.json','training_complete.json']:
        shutil.copy2(ROOT/name,records/name)
    for name in ['training_disk_cache.json','training_disk_cache_cleanup.json']:
        if (ROOT/name).exists():shutil.copy2(ROOT/name,records/name)
    for name in ['results.json','evaluation_protocol.json','enhancement_manifest.json','bypass_control_audit.json']:
        shutil.copy2(ROOT/'test'/name,records/name)
    for p in (ROOT/'test').glob('*_metrics.json'):shutil.copy2(p,records/p.name)
    for p in (ROOT/'test').glob('*_predictions.json'):shutil.copy2(p,records/p.name)
    for name in ['manifest.json','complete.json','protocol.json']:
        shutil.copy2(ROOT/'dataset'/name,records/('data_'+name))
    shutil.copy2(ROOT/'dataset/annotation_alignment_audit.json',records/'annotation_alignment_audit.json')
    shutil.copy2(ROOT/'runs/road4_v1/results.csv',records/'training_results.csv')
    shutil.copy2(ROOT/'initialization/transfer_proof.json',records/'initialization_transfer_proof.json')
    shutil.copy2(ROOT/'assets/BDD_DATA_LICENSE.txt',OUT/'BDD_DATA_LICENSE.txt')
    for name in ['LICENSE','NOTICE','MODEL_CARD.md','THIRD_PARTY_NOTICES.md']:
        shutil.copy2('E:/FPGA_Enhance_Work/camera_plate_guarded_20261026/'+name,OUT/('Multinex_'+name))
    model_rows=[]
    for period in ['all','night','dawn/dusk','daytime']:
        before=result['results']['original_initial']['all'] if period=='all' else result['results']['original_initial']['by_time'][period]
        after=result['results']['original_finetuned']['all'] if period=='all' else result['results']['original_finetuned']['by_time'][period]
        model_rows.append(f'| {period} | {after["images"]} | {percent(before["mAP50"])} | {percent(after["mAP50"])} | {percent(before["mAP50_95"])} | {percent(after["mAP50_95"])} |')
    class_rows=[]
    for k,name in enumerate(NAMES):
        m=result['results']['original_finetuned']['by_time']['night']['classes'][name]
        class_rows.append(f'| {name} | {m["objects"]} | {percent(m["ap50"])} | {percent(m["recall_at_conf025"])} | {m["fp_at_conf025"]} | {m["fn_at_conf025"]} |')
    enhance_rows=[]
    for view in ['raw400','multinex400','protected400','gamma400']:
        m=result['results'][view]['by_time']['night'];enhance_rows.append(f'| {view} | {percent(m["mAP50"])} | {percent(m["mAP50_95"])} | '+ ' | '.join(str(m['classes'][k]['fn_at_conf025']) for k in ['person','car'])+' |')
    initial_night=result['results']['original_initial']['by_time']['night']['mAP50']
    trained_night=result['results']['original_finetuned']['by_time']['night']['mAP50']
    raw_night=result['results']['raw400']['by_time']['night']['mAP50']
    enhanced_night=result['results']['multinex400']['by_time']['night']['mAP50']
    write(records/'deployment_decision.json',dict(detector_finetuning_improves_night_test=trained_night>initial_night,
          current_enhancement_improves_night_detection=enhanced_night>raw_night,deploy_road_fusion_now=False,
          reason='Current frozen enhancement lowers night detection mAP on this test. No road detector runtime/resource validation on7020 yet. Report all failures; preserve plate SD.',
          note='Reporting decision only. Frozen weights and test thresholds are not changed in response to test results.'))
    report=f'''# 道路目标检测：首轮训练与留出评测

2026-10-26。已完成行人、汽车、卡车、公交车四类检测器的电脑GPU微调与留出测试。当前模型为YOLOv5n v7.0，约177万参数，输入416；从官方COCO预训练权重迁移骨干及四类检测头，迁移前后对应输出完全一致，再进行微调。**本轮未把道路检测器部署到7020，未修改板卡和SD中的车牌程序。**

**主要结论：检测器微调有效，真实夜间组mAP50从{percent(initial_night)}提高到{percent(trained_night)}。现有增强链路未通过检测收益对照：同为400×240输入，夜间原图mAP50为{percent(raw_night)}，纯增强为{percent(enhanced_night)}。当前融合方案不直接部署，不能将其描述为“增强提高夜间检测”。这一结论仅针对本轮固定权重、数据和处理流程，不代表所有增强方法都无效。**

## 实际数据和划分

真实BDD100K道路帧共3200张：训练2400（夜间1200、黎明/黄昏400、白天800），验证320（160/64/96），留出测试480（240/96/144）。车灯眩光、遮挡和小目标是图像中的真实条件；测试没有使用人工暗化替代真实夜间。dawn/dusk合并黎明与黄昏，不可全部称为傍晚。

数据来自[BDD100K](https://github.com/bdd100k/bdd100k)的[社区镜像](https://huggingface.co/datasets/dronefreak/BDD100K)，固定版本69e9f9a60103df97e151e2606a6ad182db824f55。镜像README与实际路径不一致，实际使用原始式frames/objects/attributes JSON及真实框，非伪标注，也不声称采用修订的Detection2020标注。时段索引来自同作者分类镜像，逐图又与目标标注中的timeofday核对。3200张全部对应单个10000ms关键帧标注；按预先定义的坐标裁界和面积规则去除8个退化目标框，原JSON及逐图计数均保留。保留数据许可与逐图来源哈希。

测试取自原官方val；训练、验证取自原官方train。相同文件名前8位分组不跨划分，官方val出现的前缀完全排除出训练/验证；不同划分精确图片哈希无交集。前缀分组不证明所有地理相近的不同命名行车记录都独立。训练集共有行人2731、汽车24140、卡车912、公交车351个标注框，采用训练图像加权采样缓解不均衡；少数类覆盖仍有限。

## 训练与选权重

RTX4060 Laptop GPU训练，AdamW、初始学习率0.0005、batch16、最多24个epoch；实际完成{frozen['epochs_completed']}个epoch，用时{frozen['training_seconds']/60:.1f}分钟。温和颜色、几何及mosaic增强；固定随机种子2026102621。仅按验证集0.1×mAP50+0.9×mAP50:95选权重，权重哈希固定后才开始测试。验证门槛“mAP50:95不低于初始化模型”结果：{frozen['validation_acceptance']}。这不是全量BDD100K训练或官方榜单结果。

候选SHA256：{frozen['model_sha256']}。YOLOv5旧代码仅作PyTorch2.7可信checkpoint加载兼容；训练入口修正Windows跨盘相对路径问题。曾在梯度更新前修正初始化模型缺少顶层nc元数据，全部权重张量不变。临时磁盘缓存存储与cv2解码完全相同的原像素，仅提高读图速度，不改变预处理或标签。

## 初始化与微调后：同一批原始分辨率测试图

两者均统一letterbox到416×416、同NMS设置。AP统计置信度下限0.001、NMS IoU0.6；AP积分覆盖多个置信度，**mAP不是“识别正确图片占比”**。

| 时段 | 图数 | 初始化mAP50 | 微调mAP50 | 初始化mAP50:95 | 微调mAP50:95 |
|---|---:|---:|---:|---:|---:|
{chr(10).join(model_rows)}

真实夜间逐类结果；以下漏检和误检固定置信度0.25、匹配IoU0.5，不在测试集上调阈值：

| 类别 | 标注目标数 | AP50 | 召回率 | 误检框 | 漏检目标 |
|---|---:|---:|---:|---:|---:|
{chr(10).join(class_rows)}

## 增强是否帮助检测：统一400×240输入对照

所有图统一缩放400×240并RGB565量化后再比较，避免把高分辨率原图与低分辨率增强图直接混比。增强使用已与先前实板核对的固定Multinex C++定点参考；本次道路帧没有在真实PL中采集或运行。检测使用同一个固定训练后模型。protected为原有全局亮度旁路/混合规则，不含车牌号码一致性保护，也没有借助真实框选择输出。Gamma固定为0.5亮度基线。增强权重本轮未重训。

真实夜间240张的全部结果：

| 输入 | mAP50 | mAP50:95 | 行人漏检数 | 汽车漏检数 |
|---|---:|---:|---:|---:|
{chr(10).join(enhance_rows)}

完整新增正确匹配、损失匹配和各类误检计数见协议与评测/results.json。只有同分辨率的raw400与其他400视图能用于增强收益比较。不能挑选成功示例代替整体结果，不能把电脑GPU速度当作7020速度，不能预先宣称增强普遍提高检测。

## 效果图与使用范围

效果图目录保留按元数据顺序预先选定的3张夜间、2张黎明/黄昏和1张白天，共六张三列对照，选择早于首次测试推理。框显示置信度不低于0.25的预测，图中可能漏检、误检；文字“匹配标注目标”来自事后评测，不提供给模型。其余全部预测保留在协议与评测。

模型支持person/car/truck/bus框和类别；尚无距离或碰撞概率估计，无全部障碍物检测保证。真实摄像头、连续视频闪烁和运动模糊尚未单独验收。下一步应依据验证集优化增强/保护策略，做压缩量化和7020资源、时延测试，再进入独立板端演示；本轮成果是可复核的电脑训练基线。

权重/road4_best.pt为完整YOLOv5 checkpoint，权重/road4_state_dict.pth为纯张量字典（weights_only=True可加载），配套model.yaml定义网络。已重建网络并核对导出前后forward一致。yolov5目录保留GPL-3.0许可，BDD数据与Multinex材料分别保留其许可。

训练评测脚本保留本机E:/FPGA_Enhance_Work/road_detection_20261026路径；原始数据、大型GPU运行库与完整工具链未重复打包。复现训练需本机数据和隔离依赖，异机需调整路径，不能直接重跑覆盖现有冻结目录。
'''
    (OUT/'道路目标检测首轮训练与评测.md').write_text(report,encoding='utf-8');(ROOT/'道路目标检测首轮训练与评测.md').write_text(report,encoding='utf-8')
    tracker=HERE.parents[1]/'道路感知项目当前进度_20261026.md'
    tracker.write_text(f'''# 道路感知首轮已完成

用户授权训练行人、汽车、卡车和公交车。当前电脑训练目录{ROOT}，冻结权重{frozen['weights']}，SHA256={frozen['model_sha256']}。真实道路数据2400/320/480，测试在冻结后完成。报告：{ROOT/'道路目标检测首轮训练与评测.md'}。

尚未部署道路检测器，板卡/SD原车牌版本保留；SD卡写入车牌BOOT的记录在E:/FPGA_Enhance_Work/plate_sd_20261026/sd_write_receipt.json，独立冷启动尚未获用户确认。不能把PC GPU检测说成板端运行。增强是否有整体收益以test/results.json为准，不能仅展示成功图。下一步按验证集选择增强策略并压缩量化、实测7020资源和时延。
''',encoding='utf-8')
    files=sorted(p for p in OUT.rglob('*') if p.is_file())
    manifest=[dict(path=p.relative_to(OUT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in files];write(OUT/'manifest.json',manifest)
    archive=ROOT.parent/'road_detector_first_round_20261026.zip';assert not archive.exists()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in files+[OUT/'manifest.json']:z.write(p,p.relative_to(OUT).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert all(hashlib.sha256(z.read(r['path'])).hexdigest()==r['sha256'] for r in manifest)
    write(ROOT/'release.json',dict(archive=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),all_hashes_verified=True))
    print('ROAD_FIRST_ROUND_FINALIZED',str(archive),sha(archive),flush=True)
if __name__=='__main__':main()
