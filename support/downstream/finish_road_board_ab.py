"""Summarize completed physical evidence; keep offline candidates immutable."""
from pathlib import Path
import statistics,math,hashlib,zipfile
from road_integer_common import ROOT as QROOT,LIGHT,read,write,sha
from prepare_road_board_ab import ROOT,Q,FP
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[1]

def main():
    workflow=read(ROOT/'workflow_complete.json');assert workflow['current_model']=='Original FP32'
    assert read(ROOT/'q8_full_verified.json')['status']=='ALL8_PHYSICAL_Q8_ALL86_LAYERS_AND_HEADS_NMS_LCD_PASS'
    assert read(ROOT/'fp32_full_verified.json')['status']=='ALL8_PHYSICAL_FP32_HEADS_DECODE_NMS_AND_LCD_PASS'
    protocol=read(ROOT/'protocol.json');timing={tag:read(ROOT/(tag+'_timing_verified.json')) for tag in ['fp32','q8']};fresh=read(LIGHT/'optimization_complete.json')['metrics']
    per=[];summary={}
    for tag,data in timing.items():
        measured=[r for r in data['records'] if not r['warmup']];assert len(measured)==18
        for r in data['records']:
            g=read(ROOT/(tag+'_full')/r['fixture']/'validated.json');assert r['boxes']==g['boxes']['boxes400']['count']
        summary[tag]={field:dict(median=statistics.median(r[field] for r in measured),min=min(r[field] for r in measured),max=max(r[field] for r in measured)) for field in ['total_seconds','network_seconds','preprocess_seconds','post_seconds','render_seconds']}
        summary[tag]['offline_night_ap50']=fresh['teacher' if tag=='fp32' else 'q8']['by_time']['night']['mAP50']
        summary[tag]['offline_all_ap50']=fresh['teacher' if tag=='fp32' else 'q8']['all']['mAP50']
    for f in protocol['fixtures']:
        if f['kind']!='validation':continue
        row=dict(fixture=f['name'],timeofday=f['timeofday'])
        for tag,data in timing.items():
            rs=[r for r in data['records'] if r['fixture']==f['name'] and not r['warmup']]
            row[tag]=dict(total_median=statistics.median(r['total_seconds'] for r in rs),network_median=statistics.median(r['network_seconds'] for r in rs),boxes=rs[0]['boxes'])
        row['q8_over_fp32_time']=row['q8']['total_median']/row['fp32']['total_median'];per.append(row)
    ratio=summary['q8']['total_seconds']['median']/summary['fp32']['total_seconds']['median']
    result=dict(status='PHYSICAL_COMPARISON_COMPLETE_ORIGINAL_FP32_RECOMMENDED_AND_RESTORED',summary=summary,per_image=per,q8_over_fp32_median_time_ratio=ratio,
       numerical=dict(q8='All8 fixtures, all86 tensors, decoded/NMS/framebuffer pass',fp32='All8 fixtures, allheads, decoded/NMS/framebuffer pass; previously verified fullkernel retained'),
       accuracy_provenance='Offline480newimages, including240night. Board images are correctness/timing fixtures, not480-image physical AP evaluation.',
       recommendation='Original FP32: higher independent-night AP and lower measured board latency. Q8 retained only as a compression reference.',
       current_display='Original FP32, fixednightphoto01, camera off',current_elf_sha256=protocol['configs']['fp32']['elf_sha'],current_weight_sha256=protocol['configs']['fp32']['model_sha'],
       source_weights_and_inputs_shared=True,trace_disabled_for_all_timing=True,phase_order='Q8 thenFP32, one warmup+3 measured repeats/image; not a randomized thermal study',
       sd_written=False,flash_written=False,sd_startup_not_tested=True,neural_network_compute='ARM Cortex-A9, no new PL CNN accelerator')
    assert summary['fp32']['offline_night_ap50']>summary['q8']['offline_night_ap50'] and ratio>1
    write(ROOT/'comparison_complete.json',result)
    rows='\n'.join(f"| {r['fixture']} ({r['timeofday']}) | {r['fp32']['total_median']:.3f} | {r['q8']['total_median']:.3f} | {r['q8_over_fp32_time']:.2f}× |" for r in per)
    report=f'''# 道路模型实板A/B测试（2026-10-27）

**结论：目前测试过的版本中，保留原FP32模型更合适。已通过JTAG恢复原版，并留在固定夜间道路图片01；摄像头关闭，SD卡和Flash均未改写。**

| 指标 | 原FP32版 | W8/A8量化版 |
|---|---:|---:|
| 实板单张检测处理耗时中位数 | {summary['fp32']['total_seconds']['median']:.3f}秒 | {summary['q8']['total_seconds']['median']:.3f}秒 |
| 实板网络计算中位数 | {summary['fp32']['network_seconds']['median']:.3f}秒 | {summary['q8']['network_seconds']['median']:.3f}秒 |
| 显示绘制/提交中位数，另计 | {summary['fp32']['render_seconds']['median']:.3f}秒 | {summary['q8']['render_seconds']['median']:.3f}秒 |
| 离线新夜间集mAP50 | {100*summary['fp32']['offline_night_ap50']:.2f}% | {100*summary['q8']['offline_night_ap50']:.2f}% |
| 离线新测试集整体mAP50 | {100*summary['fp32']['offline_all_ap50']:.2f}% | {100*summary['q8']['offline_all_ap50']:.2f}% |

量化版的实板处理耗时约为原版的{ratio:.2f}倍，没有得到加速，同时夜间AP较低。它的模型文件较小，计入新增编译常量后约减少32%，但本次压缩收益不足以支持替换。没有根据框数量多少判断好坏，也没有因“新模型”而自动升级。

## 实板验证方法

- 两个程序使用同一块XC7Z020、同一显示bit和相同400×240固定图片。
- 六张真实图片：夜间3张、黄昏/黎明2张、白天1张；另外检查黑图和随机图，共8个数值用例。
- Q8逐层读回全部86个张量，内部整数码值逐字节一致；浮点检测头/解码按预先记录容差验收。所有用例检测框/NMS、LCD帧缓冲及DMA状态通过。
- 原FP32使用此前已验证的相同ELF与模型，重新核对8张图的检测头、解码、NMS及LCD帧缓冲。
- 正式计时每张真实图片先预热1次，再测3次，共每版18次有效计时；全部关闭逐层trace。计时来自ARM硬件计数器，JTAG传图和大体积结果读回位于计时区间之外；运行期间两版均采用100ms状态轮询。
- “检测处理耗时”包括输入/权重校验、预处理、推理、后处理及输出刷缓存；显示绘制/提交另列。它不是摄像头端到端帧率。
- 顺序为先Q8、后FP32，并非随机热状态对照；保留各次原始计数器和范围，不宣称微小性能差异的统计显著性。

离线精度来自此前冻结后评估的480张新图（其中夜间240张），不是本次在板上跑480张计算出的AP。本次上板证明两个实现正确并测量耗时。窄网络及256/288输入在离线已未通过精度门槛，未拿来替换或做误导性现场比较。

## 分图片处理耗时（秒，三次中位数）

| 图片 | 原FP32 | Q8 | Q8/FP32耗时 |
|---|---:|---:|---:|
{rows}

## 当前板卡与后续边界

当前屏幕为原FP32固定夜间道路图01，有检测框；不是实时摄像头输入。最后一次显示结果、数值及帧缓冲读回已经通过校验。

本轮神经网络仍由ARM Cortex-A9计算，PL沿用显示硬件；没有新增FPGA卷积加速器。恢复原版不代表项目已达到实时辅助驾驶要求。

当前ELF SHA256：`{result['current_elf_sha256']}`。

当前权重 SHA256：`{result['current_weight_sha256']}`。

SD启动任务没有在本次测试中执行，之前准备的SD自启动诊断构建仍需另行验证；本次未写卡或格式化。

证据目录：`{ROOT.as_posix()}`。

完整比较：`comparison_complete.json`；各次计时：`fp32_timing_verified.json`、`q8_timing_verified.json`；最后显示读回：`final_fp32_photo01/validated.json`及`actual_framebuffer.png`。PNG是板上帧缓冲读回，不是对实体屏幕拍照。
'''
    (ROOT/'实板模型对比_20261027.md').write_text(report,encoding='utf-8');(WORK/'实板模型对比_20261027.md').write_text(report,encoding='utf-8')
    for p in [WORK/'离线优化完成与上板检查点_20261027.md',WORK/'道路感知项目当前进度_20261026.md']:
        if p.exists():
            with p.open('a',encoding='utf-8') as f:f.write(f'\n\n2026-10-27实板追加：两版数值验证通过。正式计时原FP32中位数{summary["fp32"]["total_seconds"]["median"]:.3f}s，Q8为{summary["q8"]["total_seconds"]["median"]:.3f}s。原FP32更快且离线夜间AP更高，已恢复并留在图片01。未改SD/Flash。详见[实板模型对比](实板模型对比_20261027.md)。\n')
    files={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(ROOT.rglob('*')) if p.is_file() and p.name not in ['archive.json','manifest.json']}
    write(ROOT/'manifest.json',dict(status='ACTUAL_BOARD_AB_EVIDENCE',files=files))
    archive=ROOT.with_suffix('.zip');assert not archive.exists()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(ROOT.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(ROOT))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name,digest in files.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
    write(ROOT/'archive.json',dict(status='PHYSICAL_AB_RESULTS_ARCHIVED',archive=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),sd_written=False))
    print('ROAD_BOARD_AB_REPORT_COMPLETE',summary,ratio,flush=True)
if __name__=='__main__':main()
