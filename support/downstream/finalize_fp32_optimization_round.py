"""Write a factual round report only after verified rollback; preserve history."""
from pathlib import Path
import json,hashlib
from prepare_fp32_cpu_pack import BASE,CURRENT,read,write,sha
WORK=Path(__file__).resolve().parents[2]

def main():
    candidates=[('R1 连续权重布局','road_fp32_cpu_pack_20261028_r1'),('R3 微内核','road_fp32_microkernel_20261028_r3'),('R4 重复行复用','road_fp32_stem_reuse_20261028_r4'),('R5 首层RGB专用函数','road_fp32_stem_rgb_20261028_r5')]
    records=[]
    for label,name in candidates:
        root=BASE/name;s=read(root/'session.json');v=read(root/'validated.json')
        assert s['status']=='NOT_PROMOTED_PREVIOUS_ABI15_RESTORED' and s['restored'] is True
        assert v['trace86_byte_exact'] and v['roi_outputs_byte_exact'] and all(c['outputs_byte_exact'] for c in v['fixed'])
        assert len(read(root/'native_complete.json')['cases'])==16
        records.append(dict(label=label,root=str(root),baseline=v['timing']['0_0']['median'],candidate=v['timing']['1_0']['median'],speedup=v['speedup_single'],latency_reduction=1-1/v['speedup_single'],live=v['live'],status=s['status']))
    last=BASE/candidates[-1][1]
    assert 'ROAD_DETAIL_EXPERIMENT_LIVE_READY' in (last/'restore0.log').read_text(encoding='utf-8')
    assert sha(CURRENT/'road_detail.elf')=='d92e60df05d0c3f7bbd5aece53609cbda75f842d9b3e2c986c744ac61595c7f7'
    for name,digest in read(CURRENT/'runtime_checksums.json').items():assert sha(CURRENT/name)==digest,name
    assert 'ROAD_DETAIL_EXPERIMENT_LIVE_READY' in (BASE/'road_fp32_microkernel_20261028_r3/pretest_repair0.log').read_text(encoding='utf-8')
    assert 'FT_Read' in (BASE/'road_fp32_tile8_20261028_r2/startup.log').read_text(encoding='utf-8')
    summary=dict(status='ROUND_COMPLETE_NO_CANDIDATE_PROMOTED_ABI15_RESTORED',variants=records,current_elf_sha256=sha(CURRENT/'road_detail.elf'),current_firmware=str(CURRENT),sd_written=False,jtag_frequency_hz=6000000)
    write(last/'round_summary.json',summary)
    rows='\n'.join(f"| {r['label']} | {r['baseline']:.3f} | {r['candidate']:.3f} | {r['latency_reduction']*100:+.1f}% | 未保留 |" for r in records)
    report=f'''# ARM卷积优化实板验证记录（2026-10-28）

本轮已完成四个候选的完整数值、摄像头、屏幕和测速检查，另一个候选因下载器掉线未完成推理。**没有候选达到预设的整次检测中位加速至少5%的门槛，最终已恢复原ABI15并重新启动摄像头。** SD卡和Flash未写入。

## 整次处理耗时

各行是同一ELF、同一固定图片的原实现/候选实现对照，预热1次后计时3次，单位秒。最后一列为处理耗时减少比例，负数表示更慢。不同ELF/不同轮次不能作为严格横向速度排名；这些短测不是长期FPS。

| 候选 | 本轮原实现 | 本轮候选 | 耗时减少 | 决定 |
|---|---:|---:|---:|---|
{rows}

R2（八空间位置分块）只有离线验证与编译结果。权重传输期间发生FT_Read I/O错误，没有完成新程序的板上推理，不能给出板上速度。之后已重新识别JTAG并成功恢复ABI15；用户也确认USB重新插接。当前JTAG为6MHz，不改变ARM/FPGA计算时钟。

## 数值和视频验证

- 四个完整实板候选均通过16组全景/ROI输入的主机全86层逐字节校验。
- 实板7个固定输入的检测头、解码和检测框与同一ARM基线及此前ABI15记录逐字节一致；首例全86层读回、首例全景加ROI输出一致。
- 摄像头短窗计数、VDMA错误状态、采集缩小像素、Gamma显示及屏幕绘制逐字节校验通过。没有据此代替用户的肉眼验收。
- R4复用结果前完整比较六行输入窗口，真实图片的160个首层输出行中有58行可复用；这是离线输入审计，不是独立的板上复用计数器。首层profile跨度约0.326→0.194秒，但整次只改善约0.3%。profile含协同预览服务，不能称为纯算子时间。
- R5额外固定首层尺寸，只省略已核验恒为正零的填充通道乘加。离线和实板一致性通过，但没有得到整次提速。

本轮没有重新训练网络，也没有证明黄昏/夜间识别精度提高；权重和FPGA bit均保持原样。默认依然是ARM Gamma增强显示、检测使用原图、12层3×3卷积由FPGA执行。高细节双次检测默认关闭，尚不属于流畅逐帧检测。

## 当前可用版本

固件：[ABI15目录]({CURRENT.as_posix()})。

ELF SHA256：`{sha(CURRENT/'road_detail.elf')}`。

恢复启动：`E:/FPGA_Enhance_Work/nn_env312/Scripts/python.exe E:/FPGA_Enhance_Work/road_detail_board_20261028_r1/firmware/experiment.py start`。

本轮最后恢复日志：[restore0.log]({(last/'restore0.log').as_posix()})，已含`ROAD_DETAIL_EXPERIMENT_LIVE_READY`；运行文件校验全部保持一致。断电后RAM版需重新下载，SD卡原内容未改。

## 证据和后续方向

四个完整测试目录各自保留`native_complete.json`、`validated.json`、`session.json`、原始`firmware/physical_pack_r1`与失败恢复日志。汇总：[round_summary.json]({(last/'round_summary.json').as_posix()})。

当前还有42个1×1卷积运行在ARM。后续应优先评估FPGA增加1×1卷积支持，沿用FP32参考和独立速度/精度门槛，先做HLS仿真、资源及时序检查，再实板测量。现有3×3核的输出尺寸限制为80×80，不能直接把160×160首层映射进去后就宣称完成加速。
'''
    dest=WORK/'ARM卷积优化实板验证_20261028.md';dest.write_text(report,encoding='utf-8')
    checkpoint=WORK/'当前运行检查点_摄像头道路检测_20261027.md'
    text=checkpoint.read_text(encoding='utf-8')
    first,rest=text.split('\n',1)
    checkpoint.write_text(first+'\n\n2026-10-28 最新：本轮ARM卷积优化已全部结束，R1/R3/R4/R5通过数值和视频校验，但未达到整次中位提速5%的门槛，均未保留；R2传输中断后已修复。最终恢复ABI15并重新启动摄像头，SD/Flash未写。详见[本轮实板报告]('+dest.as_posix()+')。没有后台训练或测试任务。\n\n## 本轮前的已验收记录\n'+rest,encoding='utf-8')
    checkpoint=WORK/'保存断点_CPU缓存加速_20261028.md';text=checkpoint.read_text(encoding='utf-8');first,rest=text.split('\n',1)
    checkpoint.write_text(first+'\n\n**最终状态：本轮已完成并恢复ABI15。** 四个候选质量检查通过、速度未达门槛；R2掉线已修复。R5未通过初步速度门槛，因此没有执行交替测速确认脚本。下文“正在测试”均为历史状态；以[最终报告]('+dest.as_posix()+')和R5的`round_summary.json`为准。没有后台训练或上板任务，SD/Flash未写。\n'+rest,encoding='utf-8')
    print(summary['status'],str(dest),flush=True)

if __name__=='__main__':main()
