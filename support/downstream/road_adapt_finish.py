"""Publish measured results, fixed examples and reproducible frozen weights."""
from pathlib import Path
import hashlib,os,shutil,sys,zipfile
from PIL import Image,ImageDraw,ImageFont
from road_adapt_common import BASE,ROOT,NAMES,TRAIN_MILD,read,write,sha
HERE=Path(__file__).resolve().parent
def pct(x):return f'{100*x:.2f}%'
def main():
    done=read(ROOT/'test/complete.json');selected=read(ROOT/'selected.json')
    assert sha(ROOT/'selected.json')==done['selection_sha256'] and not done['board_deployed'] and not done['sd_written']
    out=ROOT/'release';out.mkdir(exist_ok=False);records=out/'协议与评测';records.mkdir()
    for name in ['protocol.json','prepare_complete.json','selected.json','fresh_selection.json','paired_manifest.json']:
        shutil.copy2(ROOT/name,records/name)
    for folder in ['validation','metric_regression','bounded_numeric_proof']:
        dest=records/folder;dest.mkdir()
        for p in (ROOT/folder).glob('*.json'):shutil.copy2(p,dest/p.name)
    for name in ['manifest.json','complete.json']:shutil.copy2(ROOT/'fresh'/name,records/('fresh_'+name))
    for split in ['fresh','regression']:
        shutil.copytree(ROOT/'test'/split,records/split)
    for name in ['complete.json','test_protocol.json','fresh_frames_manifest.json']:shutil.copy2(ROOT/'test'/name,records/('test_'+name))
    for mode in ['raw_control','mixed']:
        dest=records/mode;dest.mkdir();shutil.copy2(ROOT/'runs'/mode/'results.csv',dest/'training_results.csv');shutil.copy2(ROOT/'frozen'/mode/'complete.json',dest/'freeze.json')
    source=out/'代码';source.mkdir()
    for p in HERE.glob('road_adapt_*.py'):shutil.copy2(p,source/p.name)
    for name in ['road_bounded_luma.h','road_bounded_host.c','prepare_road_training_data.py']:shutil.copy2(HERE/name,source/name)
    shutil.copytree(ROOT/'yolov5',out/'yolov5',ignore=shutil.ignore_patterns('__pycache__','runs','.git','*.pyc','*.pt'))
    for name in ['BDD_DATA_LICENSE.txt']:shutil.copy2(BASE/'assets'/name,out/name)
    for p in (BASE/'release').glob('Multinex_*'):shutil.copy2(p,out/p.name)
    weights=out/'权重';weights.mkdir()
    for mode in ['raw_control','mixed']:
        assert sha(ROOT/'frozen'/mode/'best.pt')==selected['all_candidate_sha256'][mode]
        shutil.copy2(ROOT/'frozen'/mode/'best.pt',weights/(mode+'.pt'))
    # Tensor-only export and reconstruction proof for the VALIDATION-selected model.
    os.chdir(ROOT/'yolov5');sys.path.insert(0,str(ROOT/'yolov5'))
    import torch,yaml
    from models.yolo import Model
    torch.set_num_threads(4)
    model=torch.load(selected['weights'],map_location='cpu',weights_only=False)['model'].float().eval()
    torch.save(model.state_dict(),weights/'selected_state_dict.pth')
    (weights/'selected_model.yaml').write_text(yaml.safe_dump(model.yaml),encoding='utf-8')
    restored=Model(yaml.safe_load((weights/'selected_model.yaml').read_text()),ch=3,nc=4).float().eval()
    restored.load_state_dict(torch.load(weights/'selected_state_dict.pth',map_location='cpu',weights_only=True))
    torch.manual_seed(2026102627);x=torch.rand(1,3,416,416)
    with torch.inference_mode():a=model(x)[0];b=restored(x)[0]
    assert torch.allclose(a,b,rtol=1e-5,atol=1e-5)
    write(weights/'export_proof.json',dict(status='TENSOR_ONLY_NETWORK_RECONSTRUCTION_FORWARD_MATCH',source_sha256=sha(selected['weights']),
          state_dict_sha256=sha(weights/'selected_state_dict.pth'),max_absolute_error=float((a-b).abs().max()),dtype='CPU float32',parameters=sum(p.numel() for p in model.parameters())))
    # Fixed BEFORE fresh inference: preserve good and bad examples without filtering.
    examples=read(ROOT/'test/test_protocol.json')['examples'];previews=out/'效果图';previews.mkdir()
    tags=['previous__raw','raw_control__raw','raw_control__full_net','mixed__full_net']
    titles=['上一轮模型＋原图','追加原图训练＋原图','同一模型＋增强图','混合训练模型＋增强图']
    preds={tag:{r['name']:r for r in read(ROOT/'test/fresh'/(tag+'_predictions.json'))} for tag in tags}
    font=lambda n:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n)
    colors=[(255,170,30),(0,230,255),(220,130,255),(60,255,110)]
    for idx,name in enumerate(examples,1):
        canvas=Image.new('RGB',(1680,452),'#f3f6f9');d=ImageDraw.Draw(canvas)
        d.text((16,8),'电脑离线｜新留出道路帧｜统一400×240 / RGB565｜置信度0.25',font=font(25),fill='#18293e')
        d.text((16,44),name+'    '+preds[tags[0]][name]['timeofday']+'    样例按元数据顺序预先固定',font=font(20),fill='#405068')
        for col,(tag,title) in enumerate(zip(tags,titles)):
            x0=16+col*416;d.text((x0,81),title,font=font(21),fill='#18293e')
            kind='raw' if tag.endswith('__raw') else 'net';stem=Path(name).stem
            image=Image.open(ROOT/'test/fresh_frames'/(stem+'.'+kind+'.png')).convert('RGB');di=ImageDraw.Draw(image)
            row=preds[tag][name]
            for x1,y1,x2,y2,c,k in row['detections']:
                if c<.25:continue
                color=colors[int(k)];di.rectangle((x1,y1,x2,y2),outline=color,width=2)
                if x2-x1>=55 and y2-y1>=18:
                    text=f'{NAMES[int(k)]} {c:.2f}';box=di.textbbox((0,0),text,font=font(11));tx=min(max(0,x1),400-(box[2]-box[0]))
                    di.text((tx,max(0,y1-13)),text,font=font(11),fill=color,stroke_width=1,stroke_fill=(0,0,0))
            canvas.paste(image,(x0,117));d.text((x0,365),f'匹配标注：{len(row["matched_gt"])} / {len(row["ground_truth"])}',font=font(21),fill='#405068')
        d.text((16,405),'橙=行人  青=汽车  紫=卡车  绿=公交车；框可能误检/漏检，全部预测均计入评测。尚未上板。',font=font(21),fill='#405068')
        canvas.save(previews/f'{idx:02d}_{Path(name).stem}.png')
    results=done['results'];fresh=results['fresh'];scores=fresh['scores'];choice=fresh['selected'];s=scores[choice]
    lines=[]
    for tag,m in scores.items():
        n=m['by_time']['night'];p=n['classes']['person'];car=n['classes']['car']
        lines.append(f'| {tag} | {pct(m["all"]["mAP50"])} | {pct(n["mAP50"])} | {pct(n["mAP50_95"])} | {pct(p["recall"])} | {p["fp"]} | {pct(car["recall"])} | {car["fp"]} |')
    per=[]
    for period in ['night','dawn/dusk','daytime']:
        for name in NAMES:
            m=s['by_time'][period]['classes'][name]
            per.append(f'| {period} | {name} | {m["objects"]} | {pct(m["ap50"])} | {pct(m["recall"])} | {m["tp"]} | {m["fp"]} | {m["fn"]} |')
    regression=[]
    for tag,m in results['regression']['scores'].items():regression.append(f'| {tag} | {pct(m["all"]["mAP50"])} | {pct(m["by_time"]["night"]["mAP50"])} |')
    v=[]
    for mode,ss in selected['validation_scores'].items():
        for name,m in ss.items():v.append(f'| {mode} | {name} | {pct(m["by_time"]["night"]["mAP50"])} | {pct(m["by_time"]["night"]["classes"]["person"]["recall"])} |')
    before=scores['previous__raw']['by_time']['night']['mAP50'];after=s['by_time']['night']['mAP50'];net=scores['raw_control__full_net']['by_time']['night']['mAP50'];mix=scores['mixed__full_net']['by_time']['night']['mAP50']
    report=f'''# 道路感知第二轮：配对训练与新场景验收

2026-10-26。本轮已完成两组各12轮的匹配训练、验证策略搜索、新480张真实道路帧测试和旧480张回归。**当前验证选中 {selected['mode']}＋{selected['policy']['name']}；增强策略未通过验证收益门槛，不能宣传为“增强后更容易识别”。道路检测仍在电脑运行，板卡和SD未改。**

新夜间240张，同分辨率下：上一轮模型原图mAP50={pct(before)}，验证选中模型={pct(after)}，变化{(after-before)*100:+.2f}个百分点；原图对照模型接纯增强图={pct(net)}，混合训练模型接增强图={pct(mix)}。这些是四类框检测的平均AP，不是图片识别正确率。即使混合训练改善增强输入，也须与同条件原图对照比较。

## 本轮实际做了什么

采用YOLOv5n v7.0四类person/car/truck/bus，约177万参数。两组都从首轮冻结权重出发，各12轮、batch16、输入416、AdamW、相同种子、学习率、增强配置和采样算法。raw_control只见400×240 RGB565原图；mixed训练加载约50%原图、30%限幅增强、20%完整增强。均消耗同样次数的视图随机数，但图像加权采样受每轮模型评测影响，不声称两组逐步训练顺序完全一致。每组先按原图验证fitness选checkpoint，再用同320张验证图选择输入策略。raw训练{read(ROOT/'frozen/raw_control/complete.json')['seconds']/60:.1f}分钟；mixed训练{read(ROOT/'frozen/mixed/complete.json')['seconds']/60:.1f}分钟。

增强网络Multinex权重保持原样，本轮训练的是检测器；额外实现固定整数限幅提亮规则，不把它描述为新训练的增强网络。限幅规则只依据原图/增强图亮度，保护高亮像素、不主动压暗；7组参数共70000像素的C和NumPy逐字节一致。该核对在电脑完成，未证明ARM或FPGA部署后的等价性。

验证共比较{sum(len(x) for x in selected['validation_scores'].values())}组模型/策略组合：20组单路输入及符合原图门槛候选的双路补充。要求夜间mAP50至少提高0.5个百分点、行人召回不大幅下降、误检不明显增加且白天不退化；双路另要求夜间行人召回不降。混合候选的原图行人召回未达到候选门槛，所以没有继续搜索它的双路配置。所有阈值及参数写在validation/selection_rules.json，先于验证搜索。无增强方案通过，按预定规则保留原图对照。双路在暗图需要两次检测，未被采用，也没有板端实时性能结论。

## 新数据与评测边界

沿用2400训练、320验证。新测试480张来自BDD100K原官方val：夜间240、dawn/dusk96、白天144；dawn/dusk合并黎明与黄昏。新组排除上一轮全部3200张的文件名前8位分组，480张各自不同前缀，图片精确SHA无重复。分组不保证不同命名记录地理场景完全独立。所有框来自实际原始frames/objects JSON，timeofday与元数据一致；不是人工暗化照片或伪标签。新图无任何训练参与，选权重和策略前只下载/检查文件，不进行模型推理。旧480张已影响后续思路，只能作为回归记录。

所有新测试视图统一RGB缩放400×240、RGB565零扩展，再letterbox416×416；检测GPU float16。增强使用冻结Multinex C++定点参考，不是本轮实板采集。AP使用置信度下限0.001、NMS IoU0.6；操作点召回/TP/FP/FN固定置信度0.25、匹配IoU0.5。匹配和AP重构已与上一轮全部时段/类别结果核对一致。所有选定策略、权重和示例顺序在新测试推理前冻结；测试后没有改阈值或挑模型。

数据来源：[BDD100K](https://github.com/bdd100k/bdd100k)、[固定社区镜像](https://huggingface.co/datasets/dronefreak/BDD100K/tree/69e9f9a60103df97e151e2606a6ad182db824f55)，实际原始式标注并非修订Detection2020标注；镜像README与实际目录不一致，代码采用核实过的真实路径。检测源：[YOLOv5 v7.0](https://github.com/ultralytics/yolov5/tree/v7.0)。包中保留各许可，Multinex的非商业/教育限制仍适用。

## 新480张全部预先声明的视图

| 模型与输入 | 全部mAP50 | 夜间mAP50 | 夜间mAP50:95 | 夜间行人召回 | 行人FP | 夜间汽车召回 | 汽车FP |
|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(lines)}

## 验证选中模型逐类结果：新测试

| 时段 | 类别 | 标注数 | AP50 | 召回 | TP | FP | FN |
|---|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(per)}

全部新增/损失匹配见test_complete.json内changes_vs_matched_raw_control；它按真实目标ID追踪，同一GT不能因重框重复计功。图像中明亮不等于检测成功，框数量增加也不等于更多正确目标。

## 旧480张回归，不能再次称为新盲测

| 模型与输入 | 全部mAP50 | 夜间mAP50 |
|---|---:|---:|
{chr(10).join(regression)}

## 完整验证搜索记录

| 模型 | 策略 | 夜间mAP50 | 夜间行人召回 |
|---|---|---:|---:|
{chr(10).join(v)}

## 文件与下一步

权重/raw_control.pt、mixed.pt为真实训练checkpoint；selected_state_dict.pth为验证选中模型纯张量，selected_model.yaml为结构，已重建并核对float32 forward一致。代码保存真实训练、处理、评测和限幅C实现；协议与评测保留冻结哈希、全部预测、指标和失败案例。六张效果图来自预先指定顺序，原图与增强图同条件，不挑成功图。所有原始照片仍在本机数据目录，大型数据和GPU环境未重复打包；脚本使用本机绝对路径，异机需改路径，重复执行会拒绝覆盖已冻结目录。

**当前完成的是电脑实验。** 7020原有图像采集/增强/显示与车牌程序保留；道路检测尚无板端量化、算子、DDR带宽、资源或时延验收，也未添加距离估计、跟踪或真实风险判断。电脑GPU批量forward时间不等于板卡FPS。

本轮结论支持将“供人观察的增强显示”和“用于检测的图像”分别验收；保留原图检测作为基线。下一阶段先验证量化/缩小输入的检测损失及7020实现预算，再决定ARM与PL分工。若继续优化增强，应在训练/验证集上进行；这480张从此作为回归，下一次独立验收须另选未使用场景。项目目前不能宣称增强已提升辅助驾驶，也不能作为实际行车安全系统使用。
'''
    report_path=ROOT/'道路感知第二轮训练与验收.md';report_path.write_text(report,encoding='utf-8');(out/report_path.name).write_text(report,encoding='utf-8')
    write(records/'decision.json',dict(validation_selected=choice,enhancement_accepted=selected['enhancement_validation_accepted'],fresh_night_map50=after,
          fresh_change_vs_previous_pp=100*(after-before),fresh_gain_is_not_assumed=True,deploy_to_board=False,sd_written=False))
    files=sorted(p for p in out.rglob('*') if p.is_file());manifest=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in files]
    write(out/'manifest.json',manifest);archive=ROOT.parent/'road_joint_adapt_20261026.zip';assert not archive.exists()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in files+[out/'manifest.json']:z.write(p,p.relative_to(out).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert all(hashlib.sha256(z.read(r['path'])).hexdigest()==r['sha256'] for r in manifest)
    write(ROOT/'release.json',dict(status='SECOND_ROUND_MEASURED_RELEASE_HASHES_AND_ZIP_CRC_VERIFIED',archive=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),all_hashes_verified=True,board_deployed=False,sd_written=False))
    tracker=HERE.parents[1]/'道路感知项目当前进度_20261026.md'
    tracker.write_text(f'''# 道路感知第二轮已完成

报告：{report_path}。完整包：{archive}。全部哈希与ZIP CRC通过。两组匹配12轮微调、验证策略搜索、新480张测试、旧480张回归已完成。

验证选择{choice}，增强未通过收益门槛。新夜间mAP50：上一轮原图{pct(before)}，选中模型{pct(after)}，同一raw_control增强输入{pct(net)}，mixed增强输入{pct(mix)}。不得仅根据画面提亮宣传检测提高。完整指标、失败样例与来源见报告和test/complete.json。

本轮模型均在电脑GPU评测，道路检测尚未上板。板卡和SD中的车牌版未改；此前SD独立冷启动尚未获得用户确认。原项目与首轮包保留。当前新480张今后只作回归；继续调参不可再称其为独立新验收。
''',encoding='utf-8')
    print('ROAD_SECOND_ROUND_RELEASE_VERIFIED',str(archive),sha(archive),flush=True)
if __name__=='__main__':main()
