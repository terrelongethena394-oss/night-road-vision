"""Deliver only the physically verified selected16-lane mode and honest metrics."""
from pathlib import Path
import json,zipfile,hashlib,ast
from conv13_p16_config import HLS,RUNTIME as ROOT,BOARD,PACKAGE
from prepare_fp32_cpu_pack import CURRENT,HERE,read,write,sha
WORK=HERE.parents[1]

def main():
    visual=ROOT/'manual_display_status.json'
    assert not visual.exists() or read(visual).get('stable_promotion_allowed') is True, 'User reported display failure; do not promote candidate'
    soak=read(ROOT/'latest_display_soak.json') if visual.exists() else None
    if soak:
        assert read(visual)['status']=='MANUAL_DISPLAY_RECHECK_PASSED_AFTER_RELOAD'
        assert soak['frame_byte_exact'] and soak['detection_delta']>=20 and soak['preview_delta']>=200
        assert soak['resumed_detection_delta']>=2 and soak['resumed_preview_delta']>=20
        assert sha(Path(soak['evidence_dir'])/'summary.json')==read(visual)['soak_summary_sha256']
    v=read(ROOT/'validated.json');a=read(ROOT/'alternating_speed.json');live=read(ROOT/'final_live.json');arm=read(ROOT/'firmware/arm_complete.json');hw=read(BOARD/'offline_complete.json')
    assert a['status']=='CONV13_BYTE_EXACT_ALTERNATING_CONFIRMED_AND_LIVE'
    mode=a['selected_pl_mode'];assert live['status']==f'CONV13_ABI18_MODE{mode}_CONTINUOUS_CAMERA_CONFIRMED'
    revised=(ROOT/'reselection_protocol_20261029.json').exists()
    if revised:
        selection=read(ROOT/'reselection_protocol_20261029.json')
        assert mode==selection['selected_pl_mode'] and sha(ROOT/'selection_round1/alternating_speed.json')==selection['prior_calibration_sha256'] and sha(ROOT/'validated.json')==selection['physical_quality_proof_sha256']
    else:assert mode==v['selected_pl_mode']
    assert v['trace86_byte_exact'] and v['roi_outputs_byte_exact'] and all(x['outputs_byte_exact'] for x in v['fixed'])
    assert a['speedup_actual15']>=1.05 and a['actual15_independent_mean_savings_bootstrap95'][0]>0
    assert hw['wns_ns']>=0 and hw['whs_ns']>=0 and hw['ps_config_unchanged']
    app=ROOT/'firmware';checks=read(app/'runtime_checksums.json')
    assert all(sha(app/n)==h for n,h in checks.items())
    assert arm['elf_sha256']==sha(app/'road_detail.elf') and arm['bit_sha256']==sha(app/'display.bit')==hw['bit_sha256']
    assert sha(app/'runtime/weights.f32')==sha(CURRENT/'runtime/weights.f32')
    baseline=a['original_baseline']['median'];median=a['median_seconds'][str(mode)];gain=1-median/baseline;fps=v['live'][mode-1]
    path=WORK/'16路共享卷积核实板验收_20261029.md'
    role='12个3×3卷积在16路核运行，其余卷积在ARM' if mode==1 else '12个3×3和39个1×1卷积在16路核运行，其余卷积在ARM'
    samples=a.get('measured_per_mode',10)
    selection_text='初测曾保守选择模式1；第一轮每模式10次发现模式1比模式2慢超过5%，因此拒绝了模式1，该轮未作为模式2的最终确认。随后把模式2固定为候选，另采每模式20次的新交替测量，沿用原来的数值、视频和速度门槛独立确认。' if revised else '选择在初测阶段冻结，随后使用新的交替测量独立确认。'
    text=f'''# 16路共享卷积核实板验收（2026-10-29）

已完成硬件构建、数值和视频校验、交替测速及重新启动检查。当前运行ABI18、PL模式{mode}，高细节双次检测关闭，pipeline2（Gamma增强显示，检测使用原图）。SD卡和Flash未写。

## 实测结论

| 项目 | 结果 |
|---|---:|
| 原稳定版ABI15：同图8次计时中位 | {baseline:.3f}秒 |
| 16路模式1：确认阶段{samples}次中位 | {a['median_seconds']['1']:.3f}秒 |
| 16路模式2：确认阶段{samples}次中位 | {a['median_seconds']['2']:.3f}秒 |
| 最终所选模式 | {mode} |
| 所选模式相对原版耗时减少 | {gain*100:.1f}% |
| 所选模式相对原版处理加速倍率 | {a['speedup_actual15']:.3f}倍 |
| 摄像头短窗检测计数 | {fps['completed']}次/{fps['seconds']:.3f}秒（约{fps['detection_hz']:.2f}次/秒） |
| 摄像头短窗预览更新 | 约{fps['preview_hz']:.2f}次/秒 |

同图计时覆盖增强、预处理、网络和后处理，含协同预览服务，未计入JTAG传图。它不是相机到屏幕的完整端到端延迟。摄像头短窗独立计数，不视作长期FPS，也未达到流畅逐帧实时检测。

{selection_text}最终要求所选模式比实际原ABI15中位快至少5%，模式2还须比模式1快至少5%，成对和独立均值节省区间下界均大于0。实际15与所选模式的均值节省区间为{a['actual15_independent_mean_savings_bootstrap95']}秒。bootstrap描述本轮重复测量波动，不保证所有场景的速度。

## 当前分工和验证范围

FPGA：{role}。这里16路指16个并行输出通道计算单元，不是16个摄像头。新核支持1×1和3×3；支持39个pointwise层并不意味着默认全部启用。

ARM：摄像头/显示控制、图像准备、Gamma增强显示、未下放的卷积、SiLU、解码、NMS和画框。网络权重、阈值、320输入预处理和四个类别（行人/汽车/卡车/公交车）保持不变。没有重新训练，也没有证据表明黄昏识别精度因这次硬件优化提高。

- 60组Csim与7组正交RTL用例逐字节一致，8种非法配置guard通过。
- 两种分工各16组原图/ROI主机整网测试的全86层、解码、NMS及独立打包一致。
- 7个实板固定输入，两模式检测头、解码、框与原ABI15记录逐字节一致；首例全86层和ROI结果一致。
- 摄像头采集缩小、Gamma输出、UI/帧缓存绘制逐字节检查通过；VDMA和PL错误状态为0。
- 最后请求间隔12秒的只读检查中，检测计数增加{live['detection_delta']}、预览增加{live['preview_delta']}，最后完整推理PL调用{live['pl_calls_last_completed_forward']}。肉眼显示反馈另存，不用内存读回冒充用户确认。

100MHz内部时序：WNS={hw['wns_ns']:.3f}ns，WHS={hw['whs_ns']:.3f}ns；资源LUT={hw['resources']['LUT']:.0f}/53200、FF={hw['resources']['FF']:.0f}/106400、BRAM36={hw['resources']['BRAM36']:g}/140、DSP={hw['resources']['DSP']:.0f}/220。外部IO时序并未全部指定，功能仍需结合实物验证。

## 使用和证据

当前程序已经在运行。断电后重新接好JTAG和独立供电，使用[01_start_shared_core.cmd]({(app/'01_start_shared_core.cmd').as_posix()})；该入口读取已确认的模式{mode}。内部experiment.py无参数启动默认模式2，不作为用户优选启动入口。回退原版使用[00_restore_ABI15.cmd]({(app/'00_restore_ABI15.cmd').as_posix()})。

代码：[HLS共享卷积核]({(HLS/'road_conv3_hls.cpp').as_posix()})、[ARM/PL驱动]({(app/'source/road_pl.c').as_posix()})。

证据：[逐层与视频验收]({(ROOT/'validated.json').as_posix()})、[交替确认]({(ROOT/'alternating_speed.json').as_posix()})、[最终运行]({(ROOT/'final_live.json').as_posix()})。原始实板数据保留于firmware/physical_pack_r1；未删除失败记录。

ELF SHA256：`{sha(app/'road_detail.elf')}`；bit SHA256：`{sha(app/'display.bit')}`；权重SHA256：`{sha(app/'runtime/weights.f32')}`。

加载包修复记录：XSA加载会解包road_conv.bit，旧复制镜像的校验值没有同步；已确认其内容与新display.bit、板级构建及XSA内bit四方一致后，仅修正这一校验项。算法、权重、容差和速度门槛未改，修复后完成重新启动与确认。原记录保存在activation_repair_20261029。
'''
    if soak:
        text+='''
## 画面异常反馈后的独立复核

用户第一次反馈“画面异常或停止更新”后，停止将候选列为稳定版。重新连接时虽然能识别APU和FPGA，但DDR控制器处于复位状态、程序内存不可读；该状态不能用于断定此前异常的根因。

先恢复ABI15，用户确认“左侧更新，右侧隔几秒更新，颜色正常”。随后重新完整加载ABI18模式2，额外进行6个10秒等待间隔的只读检查：预览累计增加408、检测累计增加30，各间隔均有进展，VDMA和PL错误均为0。暂停后读回左右图像、UI、检测框和LCD帧缓存，独立主机绘图与实板帧缓存逐字节相同；恢复运行后再等12秒，预览增加81、检测增加6。等待间隔之外含JTAG读回时间，这些计数不作为精确FPS。

用户再次移动手掌并检查颜色后确认“左右刷新、颜色都正常”，才解除候选启动限制。此前失败反馈、两次诊断工具错误、原测速及修复记录均保留。一次复测通过不能证明长期稳定，也没有证明先前异常由某个卷积错误造成。SD和Flash未写。

传输修复仅移除启动中重复设置JTAG频率的两行；LCD验证器修正了把0x7084误写为十进制7084的问题，使用原始读回重新校验；测速协议文字的10次改为与预注册及实际执行一致的20次说明。这些均有独立审计记录，未修改bit、ELF、权重或验收容差。
'''
    path.write_text(text,encoding='utf-8')
    summary=dict(status='ABI18_P16_SELECTED_MODE_VALIDATED_AND_RUNNING',date='2026-10-29',selected_pl_mode=mode,pl_layers_default=12 if mode==1 else 51,baseline_median_seconds=baseline,selected_median_seconds=median,latency_reduction=gain,speedup=a['speedup_actual15'],live=fps,elf_sha256=sha(app/'road_detail.elf'),bit_sha256=sha(app/'display.bit'),weights_sha256=sha(app/'runtime/weights.f32'),startup_command=['E:/FPGA_Enhance_Work/nn_env312/Scripts/python.exe',str(app/'user_start.py')],internal_start_without_argument_is_diagnostic_mode2=True,sd_written=False)
    if soak:summary.update(manual_display_recheck_passed=True,initial_display_failure_not_reproduced_after_reload=True,display_soak_evidence=soak['evidence_dir'],display_soak_summary_sha256=read(visual)['soak_summary_sha256'])
    write(ROOT/'accepted_summary_20261029.json',summary)
    write(WORK/'当前稳定版本.json',summary)
    checkpoint=WORK/'当前运行检查点_摄像头道路检测_20261027.md';old=checkpoint.read_text(encoding='utf-8');title,body=old.split('\n',1)
    checkpoint.write_text(title+'\n\n2026-10-29 最新：已切换到通过数值、视频和重复测速的ABI18/16路核，模式'+str(mode)+'。同图耗时'+f'{baseline:.3f}→{median:.3f}秒，减少{gain*100:.1f}%。'+role+'。SD/Flash未写。重新启动使用user_start.py或01_start_shared_core.cmd，不能把内部experiment.py默认模式2当成最终所选模式。下一轮失败应优先恢复本版的用户入口；旧脚本CURRENT常量仍指ABI15，复用时须调整。详见[验收报告]('+path.as_posix()+')。\n\n## 此前记录\n'+body,encoding='utf-8')
    package(path,summary)
    print('P16_DELIVERY_COMPLETE',summary,flush=True)

def package(report,summary):
    prefix='road_conv13_p16_validated_20261029';zip_path=ROOT.parent/(prefix+'.zip');assert not zip_path.exists()
    files={}
    app=ROOT/'firmware'
    for p in app.rglob('*'):
        if p.is_file() and not any(part in ['physical_pack_r1','obj','static_readback','__pycache__'] for part in p.relative_to(app).parts) and p.suffix not in ['.log','.map','.su']:
            files['firmware/'+p.relative_to(app).as_posix()]=p
    for name in ['alternating_speed.json','alternating_protocol.json','validated.json','original_baseline.json','final_live.json','accepted_summary_20261029.json','protocol.json','host_complete.json']:
        files[name]=ROOT/name
    for name in ['manual_display_status.json','latest_display_soak.json','display_guard_audit_20261029.json','id_check_correction_20261029.json','protocol_text_clarification_20261029.json','transport_repaired_activate.log']:
        if (ROOT/name).exists():files['audit/'+name]=ROOT/name
    for folder in ['activation_repair_20261029','transport_activation_repair_20261029']:
        for p in (ROOT/folder).rglob('*'):
            if p.is_file():files['audit/'+p.relative_to(ROOT).as_posix()]=p
    if (ROOT/'latest_display_soak.json').exists():
        evidence=Path(read(ROOT/'latest_display_soak.json')['evidence_dir'])
        for p in evidence.iterdir():
            if p.is_file():files['display_recheck/'+p.name]=p
    if (ROOT/'reselection_protocol_20261029.json').exists():
        files['reselection_protocol_20261029.json']=ROOT/'reselection_protocol_20261029.json'
        for n in ['alternating_speed.json','alternating_protocol.json']:files['selection_round1/'+n]=ROOT/'selection_round1'/n
    files['README_使用说明.md']=report
    for name in ['checked.json','protocol.json','tb_csim.csv','tb_rtl.csv','road_conv3_hls.cpp','road_conv3_hls.h','tb_road_conv3.cpp','YOLOv5_LICENSE']:
        files['hardware/'+name]=HLS/name
    archive=Path(read(PACKAGE/'snapshot.json')['archive']);files['hardware/'+archive.name]=archive
    for name in ['offline_complete.json','timing_acceptance.txt','utilization.rpt','timing_summary.rpt','drc.rpt','build_board.tcl','system_road_conv_bd.tcl']:
        files['hardware/board/'+name]=BOARD/name
    for name in ['prepare_conv13_p16.py','prepare_road_conv13_runtime.py','conv13_p16_config.py','package_build_conv13_p16.py','package_conv13_snapshot.py','build_conv13_current_board.py','build_road_conv13.py','compile_road_conv13_runtime.py','prepare_conv13_acceptance.py','run_conv13_p16_pipeline.py','retry_conv13_p16_20261029.py','repair_conv13_p16_activation.py','reselect_conv13_p16_mode2.py','confirm_conv13_speed.py','verify_conv13_final_live.py','finalize_conv13_p16.py']:
        files['source_tools/'+name]=HERE/name
    pending=[p for n,p in files.items() if n.startswith('source_tools/') and p.suffix=='.py'];seen=set()
    for name in ['diagnose_p16_display.py','soak_p16_display.py','repair_conv13_p16_transport.py']:
        files['source_tools/'+name]=HERE/name;pending.append(HERE/name)
    while pending:
        p=pending.pop()
        if p in seen:continue
        seen.add(p)
        tree=ast.parse(p.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            mods=[a.name for a in node.names] if isinstance(node,ast.Import) else [node.module] if isinstance(node,ast.ImportFrom) and node.module else []
            for module in mods:
                dep=HERE/(module.split('.')[0]+'.py')
                if dep.is_file():files['source_tools/'+dep.name]=dep;pending.append(dep)
    for p in HERE.iterdir():
        if p.is_file() and p.suffix in ['.c','.cpp','.h','.tcl']:files['source_tools/'+p.name]=p
    for folder in [app/'alternating_speed',ROOT/'original_baseline']:
        for p in folder.glob('*'):
            if p.is_file() and p.suffix in ['.bin','.txt']:files['measurements/'+folder.name+'/'+p.name]=p
    for n in ['final_live_before.bin','final_live_after.bin']:files['measurements/'+n]=ROOT/n
    manifest={n:sha(p) for n,p in files.items()};write(ROOT/'delivery_manifest_20261029.json',manifest)
    files['manifest.json']=ROOT/'delivery_manifest_20261029.json'
    temp=zip_path.with_suffix('.building.zip');assert not temp.exists()
    with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,p in files.items():z.write(p,prefix+'/'+name)
    with zipfile.ZipFile(temp) as z:
        assert z.testzip() is None
        for name,digest in manifest.items():assert hashlib.sha256(z.read(prefix+'/'+name)).hexdigest()==digest,name
    temp.rename(zip_path)
    write(ROOT/'delivery_archive_20261029.json',dict(path=str(zip_path),bytes=zip_path.stat().st_size,sha256=sha(zip_path),entries=len(files),crc_and_sha256_verified=True,scope='Local-machine run bundle; bulky fixtures, rawphysical traces and vendor software not duplicated. Original full evidence remains inE directories.'))

if __name__=='__main__':main()
