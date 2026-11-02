"""Render and package validation-only diagnosis without hardware writes."""
from pathlib import Path
import collections,hashlib,shutil,zipfile
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from road_adapt_common import BASE,NAMES,read,write,sha
from road_pipeline_diagnose import ROOT,GOLD
HERE=Path(__file__).resolve().parent
def pct(x):return f'{100*x:.2f}%'
def main():
    done=read(ROOT/'complete.json');camera=read(ROOT/'camera_order/complete.json');resolution=read(ROOT/'camera_order/resolution/complete.json')
    audit=read(ROOT/'deployment_budget_check.json');eps=read(ROOT/'epsilon_execution_audit.json');budget=read(ROOT/'deployment_budget.json')
    assert done['no_test_split_used'] and camera['no_new_test'] and resolution['no_test_used']
    assert read(ROOT/'evaluator_parity.json')['predictions_exact'] and audit['source_bit_sha256']==audit['application_bit_sha256']
    assert not done['board_deployed'] and not done['sd_written']
    out=ROOT/'release';out.mkdir(exist_ok=False);records=out/'协议与评测';records.mkdir()
    for p in ROOT.glob('*.json'):shutil.copy2(p,records/p.name)
    for name,folder in [('validation',ROOT/'validation'),('camera_order',ROOT/'camera_order'),('camera_resolution',ROOT/'camera_order/resolution')]:
        dest=records/name;dest.mkdir()
        for p in folder.glob('*.json'):shutil.copy2(p,dest/p.name)
    proof=ROOT/'camera_order/arithmetic_proof/complete.json';shutil.copy2(proof,records/'camera_box_arithmetic_proof.json')
    code=out/'诊断代码';code.mkdir()
    for name in ['road_pipeline_diagnose.py','road_pipeline_eval.py','road_camera_order_diagnostic.py','road_camera_resolution_diagnostic.py','road_budget_audit.py',
                 'camera_box_reference.c','road_adapt_common.py','road_adapt_eval_core.py','finish_road_pipeline_diagnostic.py']:
        shutil.copy2(HERE/name,code/name)
    # Preserve the exact official/folded enhancer sources and notices for reproduction.
    golden=out/'浮点增强参考';golden.mkdir()
    for name in ['MultinexNano_arch.py','official_reference.pth','folded_reference.pth','folded_float_arrays.npz','architecture_config.json','golden_status.json','LICENSE','NOTICE','MODEL_CARD.md','THIRD_PARTY_NOTICES.md']:
        shutil.copy2(GOLD/name,golden/name)
    shutil.copy2(ROOT/'weight_only_sensitivity.npz',out/'weight_only_sensitivity.npz')
    shutil.copy2(ROOT/'camera_order/resolution/weight8sim.npz',out/'camera_order_weight8sim.npz')
    for name in ['utilization.rpt','timing_summary.rpt']:
        shutil.copy2(Path('E:/FPGA_Enhance_Work/multinex_fast_static_r4d_20261026')/name,records/name)
    shutil.copy2(BASE/'assets/BDD_DATA_LICENSE.txt',out/'BDD_DATA_LICENSE.txt')
    shutil.copy2(BASE/'yolov5/LICENSE',out/'YOLOv5_LICENSE')
    # This is an engineering plan, not a fabricated runnable ARM package.
    write(out/'板端实现清单.json',dict(status='IMPLEMENTATION_SPECIFICATION_NOT_AN_EXECUTABLE_ARM_RUNTIME',
        recommended_correctness_prototype=dict(detector='First-round road4_best.pt, weights unchanged',source_sha256=read(ROOT/'protocol.json')['weights_sha256'],
           input=dict(width=400,height=240,format='uint32 word with R bits7:0, G bits15:8, B bits23:16; current snapshot2x2 average'),
           preprocessing='Letterbox to320x320; match OpenCV INTER_LINEAR byte rounding, padding114, RGB normalization/255',
           outputs=dict(classes=NAMES,coordinate_system='original400x240',confidence=.25,nms_iou=.6,max_boxes=300)),
        operators_required=['Fused Conv2D with padding/stride and bias','SiLU','Residual add','Channel concat','5x5 stride1 padded maxpool (SPPF repeats3)',
                            'Nearest-neighbor upsample2x','Three detection heads, anchors/grid/stride decode','Sigmoid and score filtering','Class-aware NMS and inverse letterbox'],
        allocation_todo='Plan scratch/weight buffers from liveness; do not overwrite INPUT/OUTPUT/SCRATCH/DIAG/FINAL/CAPTURE, frame/mailbox, stack/heap or BSP data.',
        current_reserved_addresses=dict(INPUT='0x04000000',OUTPUT='0x04200000',SCRATCH='0x04400000',DIAG='0x04B00000',FINAL='0x04C00000',CAPTURE='0x06000000'),
        proof_steps=['Host C versus trusted float32 PyTorch raw head logits on fixed validation fixtures','Decode/NMS and image-coordinate parity',
                     'ARM cross-compile and ELF memory-map review','JTAG fixed-image board test and output readback','Camera integration and measured frame latency'],
        current_board_app='Vitis standalone Cortex-A9 NEON',new_arm_runtime_implemented=False,full_int8_runtime_implemented=False,board_downloaded=False,sd_written=False))
    # Fixed examples chosen in the first diagnostic protocol, before any inference.
    examples=read(ROOT/'protocol.json')['examples'];previews=out/'效果图';previews.mkdir()
    font=lambda n:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n)
    colors=[(255,170,30),(0,230,255),(220,130,255),(60,255,110)]
    groups=[('定点对照',['sim565','sim_float565','sim_fixed565'],['原图：采集565后2×2平均','相同输入：官方浮点增强','相同输入：定点增强参考']),
            ('输入精度',['sim888','sim_float888','sim_float565'],['RGB888输入顺序模拟','RGB888输入：浮点增强','RGB565输入：浮点增强'])]
    prediction={tag:{x['name']:x for x in read(ROOT/'camera_order'/(tag+'_predictions.json'))} for tag in camera['scores']}
    for category,tags,titles in groups:
        for i,name in enumerate(examples,1):
            canvas=Image.new('RGB',(1264,455),'#f3f6f9');d=ImageDraw.Draw(canvas)
            d.text((16,8),'电脑验证集诊断｜同一检测器416｜预处理顺序模拟，非实板采集',font=font(25),fill='#18293e')
            d.text((16,47),name+'    '+prediction[tags[0]][name]['timeofday']+'    '+category,font=font(19),fill='#405068')
            for j,(tag,title) in enumerate(zip(tags,titles)):
                x0=16+j*416;d.text((x0,83),title,font=font(20),fill='#18293e')
                image=Image.open(ROOT/'camera_order/frames'/(Path(name).stem+'.'+tag+'.png')).convert('RGB');di=ImageDraw.Draw(image);occupied=[]
                row=prediction[tag][name]
                for x1,y1,x2,y2,c,k in row['detections']:
                    if c<.25:continue
                    color=colors[int(k)];di.rectangle((x1,y1,x2,y2),outline=color,width=2)
                    if x2-x1>=55 and y2-y1>=18:
                        text=f'{NAMES[int(k)]} {c:.2f}';box=di.textbbox((0,0),text,font=font(11));w=box[2]-box[0]
                        tx=min(max(0,x1),400-w);ty=max(0,y1-13);rect=(tx,ty,tx+w,ty+13)
                        if not any(rect[0]<b[2] and rect[2]>b[0] and rect[1]<b[3] and rect[3]>b[1] for b in occupied):
                            di.text((tx,ty),text,font=font(11),fill=color,stroke_width=1,stroke_fill=(0,0,0));occupied.append(rect)
                canvas.paste(image,(x0,118));d.text((x0,366),f'匹配标注：{len(row["matched_gt"])} / {len(row["ground_truth"])}',font=font(21),fill='#405068')
            d.text((16,407),'橙=行人  青=汽车  紫=卡车  绿=公交车；所有预测均计入评测，未挑选成功图。',font=font(21),fill='#405068')
            canvas.save(previews/f'{category}_{i:02d}_{Path(name).stem}.png')
    pixel=read(ROOT/'pixel_diagnostics.json')['images'];order=read(ROOT/'camera_order/pixel_diagnostics.json')
    summary={}
    for period in ['night','dawn/dusk','daytime']:
        a=[x for x in pixel if x['timeofday']==period];b=[x for x in order if x['timeofday']==period]
        summary[period]=dict(images=len(a),canonical={p:float(np.mean([x['pairs'][p]['mae'] for x in a])) for p in a[0]['pairs']},
              camera_order={p:float(np.mean([x['pairs'][p]['mae'] for x in b])) for p in b[0]['pairs']},
              camera_input_black_fraction={v:float(np.mean([x['views'][v]['zero_pixel_fraction'] for x in b])) for v in ['sim888','sim565']})
    write(records/'pixel_summary.json',summary)
    def table(scores):
        lines=[]
        for tag,m in scores.items():
            n=m['by_time']['night'];p=n['classes']['person'];c=n['classes']['car']
            lines.append(f'| {tag} | {pct(m["all"]["mAP50"])} | {pct(n["mAP50"])} | {pct(p["recall"])} | {p["fp"]} | {pct(c["recall"])} | {c["fp"]} |')
        return '\n'.join(lines)
    cam_scores=camera['scores'];raw=cam_scores['sim565']['by_time']['night']['mAP50'];fl=cam_scores['sim_float565']['by_time']['night']['mAP50'];fx=cam_scores['sim_fixed565']['by_time']['night']['mAP50']
    cost=[]
    for size,v in budget['profiles'].items():
        cost.append(f'| {size} | {v["conv_macs"]/1e6:.2f} | {v["largest_conv_activation_elements"]/1024:.1f} | {v["largest_conv_activation_elements"]*4/1024:.1f} | {v["illustrative_compute_only_ms_57DSP_100MHz_1MAC_per_DSP_cycle"]:.1f} |')
    resource=[]
    for k,v in budget['existing_resources'].items():resource.append(f'| {k} | {v["used"]} | {v["total"]} | {v["remaining"]} | {v["percent"]:.2f}% |')
    nsummary=summary['night'];report=f'''# 增强链路诊断与7020部署评估

2026-10-26。已完成320张既有验证图片的浮点/定点、RGB888/RGB565、实际采集后缩图顺序、检测输入尺寸及权重INT8模拟对照。**当前主要问题不能归结为定点精度：按实板预处理顺序模拟，原图夜间mAP50={pct(raw)}，官方浮点增强={pct(fl)}，定点增强={pct(fx)}。浮点与定点都降低检测效果。** 本轮无训练、无新测试集使用、无板端下载、无SD写入。

## 结论与实现方向

1. 原图检测与增强显示分别验收。保留上一轮检测权重，不把额外提亮当成检测提升。
2. 320×320可作为ARM低帧率正确性原型的输入候选；它减少运算，同时降低小目标检测表现。不能称其达到最终实时性或识别精度目标。
3. 下一阶段先实现ARM/NEON的卷积、SiLU、C3/SPPF、三尺度解码及NMS正确性，再测实板速度。需加速时根据实测瓶颈选择卷积下沉PL，并重新综合、布局布线。新运行时尚未实现，包中的算子清单是实现规格。

## 数据和公平对照

使用既有320张验证图：night160、dawn/dusk64、daytime96；未访问上一轮或第二轮测试图片。所有权重冻结为首轮road4_best.pt，SHA256={read(ROOT/'protocol.json')['weights_sha256']}。增强模型固定为官方Multinex-Nano LOL-v1权重，没有在道路图片上重训。本轮是诊断，不是新独立测试或官方BDD榜单。

所有模型检测置信度下限0.001、NMS IoU0.6，AP按官方YOLOv5积分；召回和FP使用置信度0.25、匹配IoU0.5。不同检测输入尺寸都映射回400×240后匹配同一标注。评测器尺寸扩展先与上一轮原验证候选的全部320张预测和指标核对完全一致。示例名称在推理前固定。

## 最初的规范离线流程：先缩图、再RGB565

原图INTER_LINEAR缩到400×240，然后可选按R/B保留高5位、G保留高6位并补零，分别走官方浮点/现有定点增强。这与历史离线对照一致。数字解释仅适用于此顺序。

| 输入及尺寸 | 全部mAP50 | 夜间mAP50 | 夜间行人召回 | 行人FP | 夜间汽车召回 | 汽车FP |
|---|---:|---:|---:|---:|---:|---:|
{table(done['scores'])}

夜间平均每通道绝对差：定点与浮点{nsummary['canonical']['fixed565__float565']:.5f}/255；RGB565与RGB888原图{nsummary['canonical']['raw565__raw888']:.5f}/255；两种输入增强后的差异{nsummary['canonical']['float565__float888']:.5f}/255。这里MAE是两种处理之间的差值，不能当作与正常曝光真值的误差。没有配对亮图，未宣称PSNR/SSIM或主观质量提升。

## 修正实板预处理顺序后的对照

读取现有程序发现：OV5640配置输出RGB565；PL把低位补零扩展成24位；VDMA存800×480；ARM snapshot将每个2×2的四个像素逐通道按(sum+2)//4平均到400×240。因平均发生在量化之后，部分低位会重新出现，不能用“缩到400后再量化”的结果直接代表板端。

补充实验从同一BDD图INTER_LINEAR生成800×480作为传感器RGB代理，先量化/补零，再严格按snapshot公式求平均；未量化分支也用相同平均。**这只复现预处理顺序，未复现真实OV5640的ISP、曝光、传感器响应，也不是实板截图。** 四像素平均的C与NumPy实现已在随机、全白、全黑三组共864000输出字节上完全一致。

| 输入 | 全部mAP50 | 夜间mAP50 | 夜间行人召回 | 行人FP | 夜间汽车召回 | 汽车FP |
|---|---:|---:|---:|---:|---:|---:|
{table(cam_scores)}

按此顺序，夜间定点/浮点平均像素差{nsummary['camera_order']['sim_fixed565__sim_float565']:.5f}/255；两者检测mAP50差{(fx-fl)*100:+.3f}个百分点。原图至浮点增强下降{(raw-fl)*100:.2f}个百分点。因此本验证组的主要检测损失在浮点模型中已经存在，单纯增加定点位宽不足以解决。

RGB565的输入精度损失和增强放大敏感性确实存在，但不是全部原因：未量化的sim888增强同样低于sim888原图。当前权重在LOL-v1学习的提亮映射与道路检测器所需特征并不相同；道路域偏移、过强提亮与细节变化是下一步待验证的解释，不能仅根据当前对照将因果全部归于其中一项。效果图可以观察到部分区域被提得很亮；没有明亮真值，不能宣称所有这些区域都过曝或原图没有信息。

## 实板顺序模拟：分辨率与权重量化敏感性

以下使用sim565相同预处理顺序，与上表416原图为匹配对照。weight8sim是在融合后的FP16卷积权重上，逐输出通道对称INT8取整后反量化，实际检测计算仍在GPU FP16；偏置未量化、激活未量化。它是权重敏感性实验，**不是完整INT8网络、不是ARM运行时，也不证明量化加速。** 个别指标提高不能解释为量化普遍提高精度。

| 输入 | 全部mAP50 | 夜间mAP50 | 夜间行人召回 | 行人FP | 夜间汽车召回 | 汽车FP |
|---|---:|---:|---:|---:|---:|---:|
{table(resolution['scores'])}

## 模型实际运算与内存预算

模型未融合参数{budget['parameters']}，理论参数存储FP32={budget['parameter_storage_bytes']['fp32']}字节，FP16={budget['parameter_storage_bytes']['fp16']}字节，理想INT8={budget['parameter_storage_bytes']['int8_ideal']}字节；实际INT8还需要偏置、尺度、对齐和元数据。Conv权重round/dequant文件只为敏感性实验，不能作为完整可执行模型加载到板上。

逐层hook实际forward统计卷积MAC，并用独立THOP仅统计Conv进行核对，三个输入尺寸完全一致。MAC为一次乘加；按一次乘加计2 FLOPs。YOLOv5构造时打印的信息默认按640输入估算，不能把其中4.2GFLOPs当成416或320的运算量。此处未把SiLU、BN、池化、加法、数据搬运和NMS算入Conv MAC。

| 检测尺寸 | Conv百万MAC/帧 | 最大单个卷积输出理想INT8 KiB | 同输出FP32 KiB | 57DSP示意计算时间ms |
|---|---:|---:|---:|---:|
{chr(10).join(cost)}

最后一列只是假设每个DSP每100MHz周期执行1次MAC且100%利用时的算术参照，忽略带宽、调度、非卷积操作等。位宽、DSP打包和实现方法会改变这个假设，**不是实测时延，不是普适上下界，也不是可承诺帧率**。最大单个输出不等于完整峰值内存；C3/SPPF内部临时张量、并存特征图和权重需另做活跃期内存分配。

## 现有PL资源与系统约束

核对现有车牌应用引用的bit SHA与资源报告对应r4d文件完全一致；报告为已布线状态，clk_fpga_0周期10ns。读取的是本机历史报告，本轮没有重新综合或读取实板。

| 资源 | 已用 | 总量 | 数量差 | 占用 |
|---|---:|---:|---:|---:|
{chr(10).join(resource)}

剩余BRAM Tile69个，名义总容量69×36Kbit=317952字节；320输入最大卷积输出即409600字节（即使按INT8也超过此容量），不能把全部权重和特征直接堆入剩余BRAM，需分块/缓存/DDR规划。Slice占用99.43%说明布局已很紧张，但它不同于LUT占用：已占Slice内仍可能有可用LUT/寄存器，因此不能仅凭99.43%断言绝对无法增加逻辑。所有新增IP仍需重新布局布线验证。

XC7Z020资源总量可与[AMD Zynq7000产品资料](https://www.amd.com/en/products/adaptive-socs-and-fpgas/soc/zynq-7000.html)核对。当前ARM应用由arm-none-eabi编译，使用Vitis standalone BSP、Cortex-A9/NEON，不是Linux用户态。若选择ncnn等ARM运行库，要明确系统和运行时适配；[ncnn官方Cortex-A交叉编译示例](https://github.com/Tencent/ncnn/blob/master/docs/how-to-build/how-to-build.md#build-for-arm-cortex-a-family-with-cross-compiling)使用arm-linux-gnueabi/gnueabihf工具链，不能据此把现有裸机ELF直接当成ncnn应用。当前没有迁移系统或覆盖原SD。

## 接下来的具体验收顺序

1. 固定上一轮检测权重，先做320原图ARM正确性原型，模型输入来自snapshot同一份400×240原图；PL增强输出供显示。所有框坐标要从320 letterbox逆映射到400×240，再映射到800×480屏幕，避免画框偏移。
2. 先在电脑C实现对照PyTorch float32的三尺度原始头输出，再核对解码/NMS，随后交叉编译ARM ELF并检查DDR布局；不能仅验证最后有框就认定模型实现正确。
3. 固定照片上板读取输出和耗时，确认正确后接摄像头；记录采集、预处理、增强、检测、后处理、显示各阶段与端到端时延。帧率和视觉延迟分别测量。
4. 若速度不足，再按算子实测选择NEON、分块卷积PL加速或更窄网络；保留原图416精度基线，给出速度/精度代价。完整激活量化必须另做训练集校准与验证，不能沿用本轮权重模拟的精度承诺。

源码和权重保持可回退。本报告及全部数据是离线验证诊断，既不构成新的独立测试结论，也不代表道路检测已在7020运行。现有摄像头/增强/显示及车牌SD程序未改。
'''
    reportpath=ROOT/'增强链路诊断与7020部署评估.md';reportpath.write_text(report,encoding='utf-8');(out/reportpath.name).write_text(report,encoding='utf-8')
    files=sorted(p for p in out.rglob('*') if p.is_file());manifest=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in files]
    write(out/'manifest.json',manifest);archive=ROOT.parent/'road_pipeline_diagnostic_20261026.zip';assert not archive.exists()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in files+[out/'manifest.json']:z.write(p,p.relative_to(out).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert all(hashlib.sha256(z.read(r['path'])).hexdigest()==r['sha256'] for r in manifest)
    release=dict(status='VALIDATION_DIAGNOSTIC_REPORT_AND_ARTIFACTS_VERIFIED',archive=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),all_hashes_verified=True,
          no_test_split_used=True,no_new_arm_runtime=True,board_deployed=False,sd_written=False)
    write(ROOT/'release.json',release)
    tracker=HERE.parents[1]/'道路感知项目当前进度_20261026.md'
    previous=tracker.read_text(encoding='utf-8')
    previous+='\n\n## 本轮增强链路与板端成本诊断已完成\n\n'+f'报告：{reportpath}。完整包：{archive}。仅用既有320验证图，无训练和测试图读取。按实板顺序模拟，原图夜间mAP50={pct(raw)}，浮点增强={pct(fl)}，定点增强={pct(fx)}；主要检测退化已存在于浮点模型。实际相机为565采集后2x2平均，DDR24位存储不能视为原生24位精度。320原图原型候选仅为规划，ARM道路运行时尚未实现或下载；权重INT8只做round/dequant敏感性，不是激活完整量化。MAC与历史资源已核对，板/SD未改。下一步是ARM/NEON算子正确性实现与板端计时。\n'
    tracker.write_text(previous,encoding='utf-8')
    print('ROAD_DIAGNOSTIC_RELEASE_VERIFIED',release,flush=True)
if __name__=='__main__':main()
