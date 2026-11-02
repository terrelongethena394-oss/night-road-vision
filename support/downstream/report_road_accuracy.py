"""Generate an evidence-led report and labelled examples, including failures."""
import collections,shutil
from PIL import Image,ImageDraw,ImageFont
from road_accuracy_common import *
HERE=Path(__file__).resolve().parent
WORK=Path('C:/Users/曹/Documents/ChatGPT/FPGA创新设计大赛')

def pct(x):return f'{x*100:.2f}%'
def main():
    result=read(ROOT/'fresh_result.json');assert result['quality_accepted']
    base={r['name']:r for r in read(ROOT/'native/baseline_predictions.json')};cand={r['name']:r for r in read(ROOT/'native/candidate_predictions.json')}
    changes=read(ROOT/'changes_all672.json');fixtures=read(ROOT/'board_fixture_protocol.json')
    names=[r['name'] for r in changes if r['timeofday']=='night'][:2]
    default=next(c for c in fixtures['cases'] if c['name']==fixtures['default_case'])['original_name']
    if default not in names:names.append(default)
    bad=next((r['name'] for r in changes if r['timeofday']=='night' and r['name'] not in names and (r['lost_car_gt_indices'] or r['candidate_car_fp']>r['baseline_car_fp']+len(r['recovered_car_gt_indices']))),None)
    if bad and bad not in names:names.append(bad)
    out=ROOT/'examples';out.mkdir(exist_ok=True);font=lambda n:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n)
    from road_retinex_noiseguard import enhance
    records=[]
    for index,name in enumerate(names,1):
        _,raw=sensor400(ROOT/'fresh/images'/name);en=enhance(raw,'guard_light')[0]
        canvas=Image.new('RGB',(1240,390),'#f4f6f9');d=ImageDraw.Draw(canvas)
        title='固定顺序样例' if name in [r['name'] for r in changes if r['timeofday']=='night'][:2] else ('新增检出说明例（事后挑选）' if name==default else '误检／漏检说明例（事后挑选）')
        d.text((10,6),title+'  '+name,font=font(18),fill='#142334')
        for col,(im,r,label) in enumerate([(raw,base[name],'原图＋单次检测'),(raw,cand[name],'原图＋多视图检测'),(en,cand[name],'增强显示＋同一多视图检测')]):
            p=np.asarray(r['detections'],np.float32).reshape(-1,6);p=p[(p[:,4]>=.25)&(p[:,5]==1)];g=np.asarray(r['ground_truth'],np.float32).reshape(-1,5)
            ok=correct(p,g,np.array([.5],np.float32))[0][:,0];im=Image.fromarray(im.copy());draw=ImageDraw.Draw(im)
            for b,match in zip(p,ok):draw.rectangle(tuple(map(float,b[:4])),outline=(35,255,100) if match else (255,70,100),width=1)
            x=10+410*col;d.text((x,37),label,font=font(18),fill='#142334');canvas.paste(im,(x,69))
            d.text((x,316),f'汽车：正确 {int(ok.sum())}，误检 {int((~ok).sum())}',font=font(18),fill='#142334')
        d.text((10,353),'绿框＝匹配标注，红框＝误检；置信度0.25、IoU0.5。中／右检测框完全相同，提亮只用于观看。',font=font(17),fill='#32465a')
        file=out/(f'{index:02d}_'+Path(name).stem+'.png');canvas.save(file);records.append(dict(name=name,selection=title,file=str(file)))
    write(out/'manifest.json',records)
    s=result['actual_c_scores'];a=s['baseline'];b=s['candidate'];an=a['by_time']['night'];bn=b['by_time']['night'];ac=an['classes']['car'];bc=bn['classes']['car'];ci=result['actual_c_uncertainty']['interval97_5'];ec=result['enhancement_comparison']['uncertainty']['interval97_5']
    table=[]
    for label,k0,k1 in [('夜间汽车 AP@0.5',ac['ap50'],bc['ap50']),('夜间汽车 AP@0.5:0.95',ac['ap50_95'],bc['ap50_95']),('夜间车辆三类 mAP@0.5',an['vehicle_mAP50'],bn['vehicle_mAP50']),('夜间四类 mAP@0.5',an['mAP50'],bn['mAP50']),('全部672张四类 mAP@0.5',a['all']['mAP50'],b['all']['mAP50']),('夜间汽车精确率（工作点）',ac['precision'],bc['precision']),('夜间汽车召回率（工作点）',ac['recall'],bc['recall'])]:table.append(f'| {label} | {pct(k0)} | {pct(k1)} | {(k1-k0)*100:+.2f} 个百分点 |')
    board=read(ROOT/'board_verified.json') if (ROOT/'board_verified.json').exists() else None
    status='尚未完成上板：JTAG 未识别到芯片，先前板上程序未在此失败扫描中改写。' if not board else 'ABI23 已通过本轮实板数值及帧缓存验收；未重新取得实物屏幕人工反馈。'
    if board:status+='实测固定图处理 '+f"{min(r['processing_seconds'] for r in board['results']):.2f}–{max(r['processing_seconds'] for r in board['results']):.2f} 秒，不含 JTAG 传输和读回，不能当作实时帧率。"
    if board and (ROOT/'board_annotation_checks.json').exists():status+='实际板上说明例的框也逐一匹配原始标注：原方案正确1辆、误检0，新方案正确3辆、误检0。该例事后挑选用于说明，不能替代320张整体准确率。详见board_annotation_checks.json。'
    lowpath=BASE/'road_accuracy_lowlight_20261030_r1/result.json'
    low=read(lowpath) if lowpath.exists() else None
    confirmation=[]
    if low:
        la=low['scores']['baseline']['all'];lb=low['scores']['candidate']['all'];lc0=la['classes']['car'];lc1=lb['classes']['car'];lci=low['uncertainty']['interval99']
        confirmation=['## 最终暗光依据：新320张低亮度独立确认','',
        '检查展示图时发现源数据的时段标签有错误：标为night的b9117002-f2ff0c31.jpg实际看起来是白天。此图已退出暗光展示，初始选图记录保留。最初672张仍是整批道路检测证据；其中按原标签统计的“夜间480张”不能直接当成严格真实夜间结论。','',
        '随后保持已冻结方案和参数不变，再从尚未使用的前缀组按固定哈希顺序取320张：原标签为night，且检测输入400×240的平均Y=(54R+183G+19B)/256不超过48。先筛亮度、冻结图片和原始标注，再执行任何检测。这是可复核的低亮度定义，不是实测lux，也不保证所有时间标签正确。该组与最初672张及此前训练／测试分组排重。','',
        '| 新320张低亮度图片的汽车指标 | 原单次 | 新多视图 |','|---|---:|---:|',
        f'| AP@0.5 | {pct(lc0["ap50"])} | {pct(lc1["ap50"])} |',
        f'| AP@0.5:0.95 | {pct(lc0["ap50_95"])} | {pct(lc1["ap50_95"])} |',
        f'| 精确率（置信度0.25） | {pct(lc0["precision"])} | {pct(lc1["precision"])} |',
        f'| 召回率（置信度0.25） | {pct(lc0["recall"])} | {pct(lc1["recall"])} |','',
        f'汽车AP提高 {(lc1["ap50"]-lc0["ap50"])*100:.2f} 个百分点，1000次配对重采样99%区间 [{lci[0]*100:+.2f}, {lci[1]*100:+.2f}]，未跨零。{lc0["objects"]}个汽车标注，TP {lc0["tp"]}→{lc1["tp"]}，FP {lc0["fp"]}→{lc1["fp"]}，FN {lc0["fn"]}→{lc1["fn"]}。绝对误检仍增加，精确率小幅提高不等于没有误检。全部1280次网络前向采用实际可移植C，并对融合结果逐框逐字节核对。','',
        f'四类mAP@0.5 {pct(la["mAP50"])}→{pct(lb["mAP50"])}。行人预测保持不变。卡车精确率 {pct(la["classes"]["truck"]["precision"])}→{pct(lb["classes"]["truck"]["precision"])}，公交车精确率 {pct(la["classes"]["bus"]["precision"])}→{pct(lb["classes"]["bus"]["precision"])}，均下降；不能把汽车收益宣传为所有类别都更可靠。','',
        f'完整独立确认：{lowpath.as_posix()}。图像、筛选过程、协议、全部C预测保存在其所在目录。','']
    rows=['# 道路识别准确率改进与证据（2026-10-30）','',
    '本轮证明的是**保留局部图像细节与多视图检测带来的系统收益**。没有重新训练检测权重，也没有证明 Retinex 提亮本身提高检测准确率。增强仍用于供人观察，检测读取原图。','',
    *confirmation,
    f'最初672张中，按原时段标签划出的480张子集上，汽车 AP@0.5 从 {pct(ac["ap50"])} 提高到 {pct(bc["ap50"])}，差值 {(bc["ap50"]-ac["ap50"])*100:+.2f} 个百分点。1000次配对图像／前缀组 bootstrap 的97.5%区间为 [{ci[0]*100:+.2f}, {ci[1]*100:+.2f}] 个百分点。区间未跨零，支持在本批同数据源图片上的提升。AP是框检测指标，不是“42%的图片识别正确”。','',
    '## 方案和代价','',
    '原图由1280×720 JPEG按固定规则变成800×480传感器代理，再以2×2整数平均生成400×240全景图。全景图运行一次冻结 YOLOv5n FP32 四类检测。另从800×480代理图中提取三个400×240窗口，左上角分别为(0,120)、(200,120)、(400,120)，各运行一次相同检测器。局部框映射回全景坐标，去重并以0.75权重补充车辆框。原有行人预测单独保留，不用车辆补充挤占它的框预算。','',
    '每张图片共四次检测。局部区域利用原本存在的像素，不是超分辨率，不是新训练的检测网络，也不把额外计算量隐藏成增强收益。Retinex 显示沿用 ABI22，检测输入保持原图。','',
    '## 最初672张的实际 C 推理结果','',
    '下表“夜间”指原数据标签，含已发现的错误，不能替代上面的独立低亮度确认。','',
    '| 指标 | 原单次检测 | 新多视图检测 | 差值 |','|---|---:|---:|---:|',*table,'',
    f'固定置信度0.25、匹配IoU0.5；480张夜间图共 {ac["objects"]} 个汽车标注。TP {ac["tp"]}→{bc["tp"]}，FP {ac["fp"]}→{bc["fp"]}，FN {ac["fn"]}→{bc["fn"]}。正确检出净增 {bc["tp"]-ac["tp"]}，误检增加 {bc["fp"]-ac["fp"]}；精确率有所下降，不能宣传“误检没有增加”。所有行人预测保持原样，未证明本轮改善行人。','',
    '## 能否说增强改善了识别','',
    f'另外预先冻结了匹配对照：相同网络、相同三个局部区域、相同框融合参数，仅将局部输入改为温和 Gamma 提亮。在GPU FP32上，夜间汽车AP差值仅 {result["enhancement_comparison"]["uncertainty"]["point_difference"]*100:+.4f} 个百分点，97.5%区间 [{ec[0]*100:+.2f}, {ec[1]*100:+.2f}]，包含0，**没有证明额外提亮有稳定收益**。此对照未根据新测试重新选择。','',
    '## 数据与防止挑图','',
    '开发阶段使用此前已用过的320张验证图比较全景原图、两种温和Gamma、ABI22增强，以及中心／三个局部区域和四组固定融合权重。全部开发结果保留，只有旧验证用于选择。选定 three_raw_w75 后，才进行新测试推理。','',
    '最初新测试672张：原标注night480、daytime160、dawn/dusk32，来自所用镜像的BDD100K原官方val对应图片，不是官方完整基准。按文件名前8位组排除此前训练、验证、测试和已预留样例，逐图核对原始标注及SHA。每组仅一张；但前缀排重并不证明地理场景或跨摄像头独立。该组今后只能作为回归数据，不能反复调参再称盲测。','',
    'dawn/dusk合并黎明与黄昏，且此次仅32张，不能单独证明黄昏泛化。所有结果来自同一BDD数据源，未证明本机OV5640实拍提升。成功说明图和误检／漏检说明图均有事后挑选，并在图上标注；它们只用于解释，统计分母始终是全部预留图片。','',
    '## 移植验证和当前状态','',status,'',
    '本轮固定图输入由PC预先生成全景和三个局部窗口，再通过JTAG上传。准备好的板端程序执行四次网络前向、融合和增强显示；PL复用已有卷积核，ARM执行其余算子和处理。三窗口采样尚未接入实时摄像头，不能把电脑裁图描述为已经在板上摄像头流程实现。','',
    '电脑端已对全部672张执行实际可移植FP32 C推理：共2688次网络前向。三视图映射和融合C实现与独立NumPy参考逐框逐字节一致，并检查输出缓冲区边界。GPU开发结果与C复核数值很接近，最终主表和主比较置信区间采用实际C结果。置信区间算法前三次重采样与完整10-IoU指标实现核对一致。','',
    'SD卡和Flash未写入。原 ABI22 固定图片版和 ABI18 摄像头版保留。','',
    '## 可追溯文件','',
    f'- 固定协议：{ROOT.as_posix()}/protocol.json',f'- 全部开发结果与冻结选择：{ROOT.as_posix()}/selected.json',f'- 独立验收：{ROOT.as_posix()}/fresh_result.json',f'- 每张图片的新增／损失目标及误检：{ROOT.as_posix()}/changes_all672.json',f'- 全部实际C预测和移植证明：{ROOT.as_posix()}/native/',f'- 图片示例：{ROOT.as_posix()}/examples/',f'- 工程源码：{ROOT.as_posix()}/firmware/source/','',
    '许可与来源：原检测器遵循YOLOv5 GPL-3.0；BDD100K数据须保留其原许可。增强光照估计借鉴 DOI 10.1109/TCSII.2024.3361561，由本工程独立实现并改造。']
    text='\n'.join(rows)+'\n';(ROOT/'识别改进与验证报告.md').write_text(text,encoding='utf-8');(WORK/'道路识别准确率提升证据_20261030.md').write_text(text,encoding='utf-8')
    src=ROOT/'source';initial=src/'road_accuracy_common.py'
    if initial.exists() and not (src/'initial_common_before_person_budget_guard.py').exists():shutil.copy2(initial,src/'initial_common_before_person_budget_guard.py')
    for pattern in ['*road_accuracy*.py','road_vehicle_multiview.*','launch_road_cuda.py']:
        for p in HERE.glob(pattern):
            if p.resolve()!=(src/p.name).resolve():shutil.copy2(p,src/p.name)
    write(ROOT/'code_provenance.json',dict(current_source_sha256={p.name:sha(p) for p in src.iterdir() if p.is_file()},note='Initial prepare snapshot of common helper preceded the person-budget guard. Guard implemented before development inference and used in all development/fresh/C results. Archived initial helper is not current code.',no_model_or_threshold_change_after_fresh_inference=True))
    print('ACCURACY_EVIDENCE_REPORT_READY',ROOT/'识别改进与验证报告.md',flush=True)

if __name__=='__main__':main()
