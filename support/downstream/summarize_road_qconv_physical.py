"""Record measured results with model-quality boundaries and immutable runtime hashes."""
from pathlib import Path
import hashlib,json
import numpy as np
from PIL import Image
BASE=Path('E:/FPGA_Enhance_Work')
APP=BASE/'road_qconv_app_20261027'
OLD=BASE/'road_hybrid_20261027_r1'
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    session=json.loads((APP/'experiment_session_r1.json').read_text());assert session['numerics_validated'] and session['fp32_hybrid_restored']
    result=json.loads((APP/'physical_experiment_r1/validated.json').read_text());assert result['all86_integer_codes_exact'] and not result['accuracy_gate_passed']
    assert 'ROAD_HYBRID_CAMERA_LIVE_READY' in (APP/'restore_hybrid.log').read_text()
    for n,h in json.loads((OLD/'runtime_checksums.json').read_text()).items():assert sha(OLD/n)==h,n
    for n,h in json.loads((APP/'experiment_checksums.json').read_text()).items():assert sha(APP/n)==h,n
    image=APP/'physical_experiment_r1/first_fpga_full/screen_from_board.png'
    a=np.fromfile(image.with_name('frame.bgr'),np.uint8).reshape(480,800,3);Image.fromarray(a[:,:,::-1]).save(image)
    lines=['# 7020 整数检测加速实板结果（2026-10-27）','',
           '临时实板实验已完成，数值和摄像头/屏幕链路检查通过。结束后已恢复原 FP32 ARM/FPGA 协同版本，并确认该版本产生了至少两次摄像头检测结果。SD 卡和 Flash 未写入。',
           '', '当前实验版的独立夜间精度门槛仍未通过，因此没有将其设为正式版本。','',
           '## 摄像头连续检测','',
           '| 左侧预览目标间隔 | 右侧不同快照检测完成率 | 窗口内计入的结果数 | 最后一个结果显示完成时距取图的时间 |',
           '|---|---:|---:|---:|']
    for r in result['live']:
        lines.append(f"| {r['preview_period_ms']}ms | {r['unique_detection_fps']:.3f} FPS | {r['unique_completions']} | {r['last_visible_result_age_ms']}ms |")
    lines+=['', '完成率使用 ARM 记录的首末显示完成时间以及不同输入快照 ID 计算，测量窗口内没有 JTAG 轮询。最后一项是窗口末单个样本的结果年龄，不是平均延迟或最大延迟。每个窗口约 20 秒，尚未覆盖长期运行和不同路况。',
            '', '150ms 预览间隔在本轮最快，约 3.4 次检测/秒。更频繁的取图和整屏绘制占用 ARM 与共享 DDR，100ms、50ms 设置下整体检测反而变慢；它们尚不能改善到 10 FPS。',
            '', '## 固定图片同模型对照','',
            '| 运行方式 | 同一整数模型的单张处理耗时中位数 |', '|---|---:|',
            f"| ARM 整数程序 | {result['timing']['cpu']['median_total_seconds']:.6f}s |",
            f"| FPGA 全 60 卷积加速 | {result['timing']['fpga']['median_total_seconds']:.6f}s |", '',
            f"同一模型、同一输入的处理耗时加速比为 {result['integer_cpu_vs_fpga_speedup']:.2f} 倍。每种方式预热 1 次，测量 3 次取中位数。计时包含预处理、网络、解码/NMS 和期间的协同预览服务；不含 JTAG 传输、启动打包、计时前输入复制及最后一次结果复制/屏幕呈现。这个比值的基准是 ARM 整数程序。",'',
            '此前 FP32 协同版本摄像头检测约 0.396 FPS。与本轮整数候选的对照同时包含模型和场景差异，只作为体验参考。', '',
            '## 计算与显示验证','',
            '- 第一张固定道路图片读取全部 86 个张量：整数编码精确一致，浮点检测头符合既定容差。',
            '- 6 张固定道路图片及纯黑、随机两个控制输入，检测头、解码、框和类别均通过参考程序检查；本轮各检测头最大数值差为 0。',
            '- 摄像头缓存平均结果与 CPU 参考逐字节一致。屏幕帧缓存与独立主机绘图程序逐字节一致，VDMA 未报告错误。',
            '- 固定图片测试的原始屏幕读回如下。左侧是当时的摄像头预览，右侧是注入的固定夜间道路测试图；左右不构成同一场景的增强前后对比。该帧开启逐层追踪并暂停读回，画面上的 399ms 不计入上表常规测速。', '',
            f'![实板固定图测试原始帧]({image.as_posix()})', '',
            '## 仍需解决的模型问题','',
            '| 新 480 张独立测试集 | 原 FP32 模型 | 当前量化候选 |', '|---|---:|---:|',
            '| 全集 mAP@0.5 | 24.38% | 23.52% |', '| 夜间 mAP@0.5 | 24.23% | 22.58% |', '',
            '夜间 mAP 下降约 1.64 个百分点，未通过事先固定的精度保留门槛。本轮已测图片没有发现硬件计算偏差；继续改善识别效果需要在模型训练与量化上处理。当前结果不能支持“识别精度更好”或“达到 10 FPS 实时检测”的表述。','',
            '## 文件位置','',
            f'- 完整实测记录：{APP.as_posix()}/physical_experiment_r1/validated.json',
            f'- 实验结束及恢复确认：{APP.as_posix()}/experiment_session_r1.json',
            f'- 恢复过程：{APP.as_posix()}/restore_hybrid.log',
            f'- 实验代码和固件：{APP.as_posix()}/source、road_qconv.elf、display.bit',
            f'- 当前正式版本：{OLD.as_posix()}', '',
            '硬件为 100MHz，整个工程 26,917 LUT、35,484 寄存器、88.5 BRAM36、203 DSP；内部受约束路径 WNS +0.058ns、WHS +0.032ns。原厂工程继承的外部输入/输出延时约束仍不完整，尚不能宣称全面完成外部接口时序签核。','']
    report=HERE.parents[1]/'整数检测加速实板报告_20261027.md';report.write_text('\n'.join(lines),encoding='utf-8')
    receipt=dict(status='PHYSICAL_TESTS_PASS_FP32_HYBRID_RESTORED_QUANT_QUALITY_GATE_STILL_FAILED',report=str(report),report_sha256=sha(report),validated_sha256=sha(APP/'physical_experiment_r1/validated.json'),session_sha256=sha(APP/'experiment_session_r1.json'),runtime_artifacts_verified=True,live_fps=[{k:r[k] for k in ['preview_period_ms','unique_detection_fps']} for r in result['live']],accuracy_gate_passed=False,sd_written=False,flash_written=False)
    (APP/'physical_summary.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(json.dumps(receipt,indent=2),flush=True)
if __name__=='__main__':main()
