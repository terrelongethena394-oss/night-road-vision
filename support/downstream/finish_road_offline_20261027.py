"""Freeze honest outcome, package hashes, and the next physical-validation boundary."""
import shutil,subprocess,sys,zipfile,hashlib,json,re
from pathlib import Path
from road_integer_common import ROOT,LIGHT,FLOAT,BASE,read,write,sha
from package_road_q8_candidate import PACK
from select_road_light_candidates import gates
from prepare_road_lcd_static import ROOT as LCD
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[1]
SD=Path('E:/FPGA_Enhance_Work/road_sd_diagnostic_r1_20261027')

def pct(x):return f'{100*x:.2f}%'
def main():
    final=read(LIGHT/'optimization_complete.json');audit=read(LIGHT/'training_audit/complete.json');qapp=read(PACK/'offline_complete.json')
    assert final['status']=='ALL_FIXED_BUDGET_TRAINING_VALIDATION_AND_UNSEEN_EVALUATIONS_COMPLETE'
    assert final['frozen']['student'] is None and final['frozen']['quantized']['tag']=='m125'
    assert len(audit['architecture'])==18 and not qapp['board_run'] and not qapp['sd_written']
    val=read(ROOT/'c_validation320/complete.json')['metrics'];old=read(LIGHT/'baseline/teacher_metrics.json')
    newbase=final['metrics']['teacher'];newq=final['metrics']['q8'];fast=read(ROOT/'m125/fast_r1/complete.json')
    small256=read(Path('E:/FPGA_Enhance_Work/road_256_20261027/validation_complete.json'))['metrics'];small288=read(Path('E:/FPGA_Enhance_Work/road_288_20261027/validation_complete.json'))
    g256=gates(small256,old);g288=small288['gates'];assert not all(g256.values()) and not all(g288.values())
    baseline_bytes=(FLOAT/'weights.f32').stat().st_size;qb=(PACK/'runtime/model.bin').stat().st_size
    constants=4752*28+4752*24+86*28 # actual ARM nm sizes: Q_CHANNELS, Q_FAST, Q_NODES.
    constants_audit=dict(q_channels_bytes=133056,q_fast_bytes=114048,q_nodes_bytes=2408,total=constants)
    assert constants==249512
    result=dict(status='OFFLINE_OPTIMIZATION_FINISHED_AWAITING_PHYSICAL_AB_VALIDATION',default_model='Original verified FP32 teacher retained',
        candidate='m125 W8/A8 Conv plus FP32 raw heads/decode, exact integer threshold tables and exact search directories',
        reason_not_promoted='New holdout night AP50 drops from.2587135 to.2220297. Host Q8 remains slower than FP32. Compression alone is not a speed/accuracy upgrade.',
        old_validation=dict(teacher=old,q8_actual_c=val),unseen480=dict(teacher=newbase,q8=newq,diagnostic_gates=gates(newq,newbase)),
        weights_bytes=dict(fp32=baseline_bytes,q8_blob=qb,additional_compiled_constants=constants_audit,q8_blob_and_derived_constants=qb+constants,
             blob_reduction_fraction=1-qb/baseline_bytes,including_derived_constant_reduction_fraction=1-(qb+constants)/baseline_bytes),
        old_arena_bytes_unchanged=3276800,candidates_trained=3,epochs_each=40,student_checkpoints_evaluated=18,
        students_rejected=True,input256_rejected=g256,input288_rejected=g288,host_only_timing=fast['host_only_median_cpu_seconds'],
        candidate_elf_sha256=qapp['elf_sha256'],model_sha256=qapp['model_sha256'],ready_package=str(PACK),known_good_rollback=str(LCD/'00_install_ram.cmd'),
        no_hardware_access_this_offline_phase=True,sd_written=False,board_neon_numerics_not_yet_verified=True,sd_startup_diagnostic_not_board_verified=True)
    write(ROOT/'final_offline_outcome.json',result)
    lines=[]
    for tag in ['c0625','c09375','c1250']:
        rs=[r for r in final['frozen']['student_records'] if r['variant']==tag];best=max(rs,key=lambda r:r['night_ap'])
        lines.append(f"| {tag} | {best['macs']:,} | {pct(best['night_ap'])} | 未通过，保留失败记录 |")
    rows='\n'.join(lines)
    def n(m):return m['by_time']['night']
    report=f'''# 离线优化完成与上板检查点（2026-10-27）

## 结论

本轮离线训练、模型压缩、C实现核对和新测试集评估已完成，工作推进到必须实板比较的阶段。**默认保留原来的已验收FP32检测程序；没有获得识别更准确的新模型。** 量化版已编译成ARM候选程序，只用于下一次上板测正确性、耗时和压缩收益，不能当作已验证升级。

本轮没有连接JTAG、复位开发板、改写SD或Flash。板卡可以继续关电。SD启动工作仍未完成，旧文件和备份保留。

## 做了什么，哪些没有成功

1. 固定训练图2400张、旧验证图320张，按“800×480缩放→RGB565截位→2×2平均到400×240→精确整数双线性到320×320”的顺序准备输入。它是数据通路代理，并不模拟OV5640曝光、噪声、ISP或运动模糊。
2. 三种更窄网络各训练40轮；用原模型指导训练，仅在训练图上使用教师输出。评估了18个冻结检查点。所有变体均未通过事先设定的精度/召回/误检门槛，因此全部不部署。
3. 对原模型做W8/A8卷积量化，只用320张训练图校准范围，比较3种范围余量。m125在旧验证集满足门槛，按最小模型文件规则冻结，之后才读取新测试结果。
4. 检查256和288输入。256整体AP下降过多；288行人召回不足。两者仅在旧验证集评估，不继续搜索更多尺寸，也不进入新测试集选优。
5. 实现实际C整数卷积、逐通道精确SiLU量化阈值、Q20残差缩放。最后检测头、解码、NMS仍用FP32。另做不改输出的分桶索引，减少二分查表开销。

以下是三种窄网络在所查检查点中的最高夜间mAP50，全部来自旧验证集；表中不代表它们被新测试集验证过：

| 变体 | 320输入卷积MAC | 最佳夜间mAP50 | 决定 |
|---|---:|---:|---|
{rows}
| 原模型 | 517,657,600 | {pct(n(old)['mAP50'])} | 保留 |

## 精度结果与边界

新测试集480张：夜间240、黄昏/黎明96、白天144。按元数据确定样本，排除此前使用过的场景前缀组和文件哈希；新测试集的480组均未出现在之前3680张资料中。它与训练/旧验证组分离，但仍属于同一BDD100K来源，不能代表跨相机或实拍泛化。

| 数据 | 原FP32权重基线mAP50 | Q8候选mAP50 |
|---|---:|---:|
| 旧验证320张整体 | {pct(old['all']['mAP50'])} | {pct(val['all']['mAP50'])} |
| 旧验证夜间160张 | {pct(n(old)['mAP50'])} | {pct(n(val)['mAP50'])} |
| 新测试480张整体 | {pct(newbase['all']['mAP50'])} | {pct(newq['all']['mAP50'])} |
| 新测试夜间240张 | {pct(n(newbase)['mAP50'])} | {pct(n(newq)['mAP50'])} |

新夜间集含187个行人：原版TP/FP/FN={n(newbase)['classes']['person']['tp']}/{n(newbase)['classes']['person']['fp']}/{n(newbase)['classes']['person']['fn']}，Q8为{n(newq)['classes']['person']['tp']}/{n(newq)['classes']['person']['fp']}/{n(newq)['classes']['person']['fn']}；召回率分别为{pct(n(newbase)['classes']['person']['recall'])}和{pct(n(newq)['classes']['person']['recall'])}。车辆等其他类别完整结果见JSON。

量化版新夜间mAP50绝对下降{100*(n(newbase)['mAP50']-n(newq)['mAP50']):.2f}个百分点，相对下降{100*(1-n(newq)['mAP50']/n(newbase)['mAP50']):.1f}%。它减少了一些误检，也增加了漏检，不能称为“识别更好”。不根据这个测试集再调整量化范围或挑另一检查点。

统计使用四类平均AP，IoU0.5以及完整0.5:0.95结果均保存；运行点TP/FP/FN使用置信度0.25、匹配IoU0.5。AP推理最低置信度0.001，NMS IoU0.6、最多300框。基线GPU用FP16，量化参考为精确整数卷积加FP32检测头，数值方式有差异；Q8旧验证320张已另外使用实际C程序跑完，整体和夜间AP与整数参考一致。旧FP32实际C夜间AP为0.305931，与这里GPU基线0.305867接近。

新测试并未验证图像增强有助检测。本轮道路检测输入为原图支路，增强支路不启用；此前增强损伤检测的结论没有被推翻。

## 压缩、性能与数值核对

原权重文件{baseline_bytes:,}字节；Q8模型文件{qb:,}字节，减少{100*(1-qb/baseline_bytes):.1f}%。但C程序还内置阈值通道元数据和加速索引{constants:,}字节；计入这些新增常量，总计{qb+constants:,}字节，相对原权重减少约{100*(1-(qb+constants)/baseline_bytes):.1f}%。没有把编译进程序的表藏到“零成本”里。

内部特征存储类型从FP32改为int8，实际有效数据字节数下降；为了保守兼容，预留arena仍为3,276,800字节，**没有宣称DDR分配大小缩小四倍**。输入RGB使用无符号8位码值，最终检测头为FP32。

完成：

- 六张真实图片、黑图和随机图，共8个用例的全部86个张量、解码及NMS核对；内部整数码值逐字节相等，检测头/解码按记录的浮点容差验收。
- 标量C与SSE2对照；阈值边界和分桶目录核对；实际C程序对全部320张旧验证图评估，指标与参考一致。
- Cortex-A9硬浮点/NEON交叉编译，确认存在vmlal.s16指令，检查ELF装载区间与DDR缓冲区无重叠。
- 便携验证包，包含参考输出、全层读回、检测框、帧缓冲、DMA状态校验；原FP32实板记录会被新固件身份校验拒绝，不能冒充新版本通过。

主机配对计时中位数：FP32 {fast['host_only_median_cpu_seconds']['fp32']:.4f}s，普通Q8 {fast['host_only_median_cpu_seconds']['q8plain']:.4f}s，查表优化Q8 {fast['host_only_median_cpu_seconds']['q8fast']:.4f}s。仅是本机SSE2结果，训练进程当时也存在。Q8仍慢于FP32，不能宣称加速；ARM NEON与主机差异必须上板测量。原FP32实板固定图约2.27秒，不能拿它换算成已验证摄像头视频帧率。

窄网络训练的一个日志问题也已查清：上游train.main复用了默认Callbacks，旧目录CSV会追加后续实验的日志。原始CSV不删除，已分别提取各自前40轮，并逐个核对18个冻结权重的哈希、宽度与参数量；模型文件是不同变体，评估直接读取冻结权重，没有依据混合CSV选结果。后续多次train.run必须使用独立Callbacks。

## 硬件分工与下一次上板

本候选的卷积和检测仍由ARM执行，PL沿用既有显示逻辑；**没有新增FPGA卷积加速器**。测试为固定图片，不启用摄像头，界面标有CAMERA OFF。它还不是实时辅助驾驶系统。

候选目录：`{PACK.as_posix()}`。

下次上电后按README进行JTAG RAM测试：先首张固定图，读取全部86层；再运行其余真实图和黑图/随机图；比较原版与Q8的实际板上网络/预处理/NMS/显示耗时。首张主机输出15框，数量不等于15个真实目标。

上板之前不把候选写SD。若板上结果不一致或耗时没有实质改善，继续保留原FP32默认版本，不能为体现“新模型”而替换。

原程序恢复入口：`{(LCD/'00_install_ram.cmd').as_posix()}`。

## SD启动任务

此前自包含SD应用的JTAG测试报权重FNV错误10，未通过启动验收；最前1024字节正确不足以证明整份权重正确。处理器单独复位后的缓存覆盖只是待验证假设。

新诊断目录：`{SD.as_posix()}`。已离线生成带源权重、复制后、flush/invalidate后分阶段全量FNV检查的程序与BOOT.BIN，检查启动头、分区及嵌入数据，并加入从系统复位/PS初始化开始的测试脚本。该构建**尚未实板运行、没有写入SD、没有证明独立冷启动可用**。

下一次需要先验自启动和数值，再执行原先分阶段备份/暂存/整文件读回/提交的写卡流程；不跳过旧BOOT备份，不格式化卡。

## 可复查资料

- `{(LIGHT/'optimization_complete.json').as_posix()}`：三个轻量模型、新测试结果及冻结候选。
- `{(LIGHT/'training_audit/complete.json').as_posix()}`：训练日志与权重身份核对。
- `{(ROOT/'final_offline_outcome.json').as_posix()}`：本次最终结论与大小/性能边界。
- `{(ROOT/'c_validation320/complete.json').as_posix()}`：实际C全旧验证集结果。
- `{(PACK/'host_numerical_proof.json').as_posix()}`：逐层核对记录。

数据和YOLOv5许可沿用原项目的来源、固定版本和GPL-3.0记录；包内保留许可。候选仍待实板验收，不覆盖已有成功版本。
'''
    report_path=WORK/'离线优化完成与上板检查点_20261027.md';report_path.write_text(report,encoding='utf-8')
    (ROOT/'离线优化完成与上板检查点_20261027.md').write_text(report,encoding='utf-8')
    (PACK/'离线优化结果.md').write_text(report,encoding='utf-8');shutil.copy2(ROOT/'final_offline_outcome.json',PACK/'offline_outcome.json')
    shutil.copy2(LIGHT/'optimization_complete.json',PACK/'training_and_new_holdout.json')
    for name in ['selection/frozen_candidates.json','training_audit/complete.json','fresh/complete.json']:
        shutil.copy2(LIGHT/name,PACK/('evidence_'+name.replace('/','_')))
    for file in [WORK/'暂停断点_道路SD启动_20261027.md',WORK/'道路感知项目当前进度_20261026.md']:
        if file.exists():
            with file.open('a',encoding='utf-8') as f:f.write('\n\n2026-10-27补充：用户随后授权离线优化，已完成固定预算训练、量化和新测试集评估。原FP32保留，Q8只作待上板A/B候选。本轮未操作板卡/SD；SD自启动仍待复验。最新交接见 [离线优化完成与上板检查点](离线优化完成与上板检查点_20261027.md)。\n')
    verification='''"""Read-only package SHA256 preflight; never accesses the board."""
import json,hashlib
from pathlib import Path
root=Path(__file__).resolve().parent
manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
for name,expected in manifest['files'].items():
    p=root/name
    assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==expected, name
print('Q8_PACKAGE_ALL_HASHES_PASS',len(manifest['files']))
'''
    (PACK/'verify_files.py').write_text(verification,encoding='ascii')
    cmd=(PACK/'00_install_ram.cmd').read_text();needle='call "E:\\Xilinx\\Vitis\\2020.2\\bin\\xsct.bat"'
    assert cmd.count(needle)==1
    cmd=cmd.replace(needle,'"E:\\FPGA_Enhance_Work\\nn_env312\\Scripts\\python.exe" "%~dp0verify_files.py"\nif errorlevel 1 exit /b 1\n'+needle)
    (PACK/'00_install_ram.cmd').write_text(cmd,encoding='ascii')
    files={p.relative_to(PACK).as_posix():sha(p) for p in sorted(PACK.rglob('*')) if p.is_file() and p.name!='manifest.json'}
    write(PACK/'manifest.json',dict(status='OFFLINE_CANDIDATE_NOT_BOARD_VERIFIED',files=files,board_downloaded=False,sd_written=False))
    p=subprocess.run([sys.executable,str(PACK/'verify_files.py')],capture_output=True,text=True,check=True);assert 'Q8_PACKAGE_ALL_HASHES_PASS' in p.stdout
    archive=PACK.with_suffix('.zip');assert not archive.exists()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(PACK.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(PACK))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name,digest in files.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest,name
    receipt=dict(status='OFFLINE_MODEL_EXPERIMENTS_ARCHIVED_AND_CANDIDATE_WAITING_FOR_BOARD',archive=str(archive),archive_bytes=archive.stat().st_size,archive_sha256=sha(archive),
      files=len(files),manifest_sha256=sha(PACK/'manifest.json'),report=str(report_path),no_board_access=True,no_sd_write=True,default_model_unchanged=True)
    write(ROOT/'release.json',receipt);write(WORK/'离线优化交付_20261027.json',receipt)
    print('ROAD_OFFLINE_OPTIMIZATION_READY_FOR_PHYSICAL_VALIDATION',str(archive),receipt['archive_sha256'],flush=True)
if __name__=='__main__':main()
