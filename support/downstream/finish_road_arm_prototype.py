"""Archive actual host/ARM evidence, frozen weights, code and explicit scope."""
from pathlib import Path
import hashlib,shutil,zipfile,statistics
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from road_arm_common import ROOT,BASE,DIAG,NAMES,WEIGHT,read,write,sha
HERE=Path(__file__).resolve().parent
def pct(v):return f'{100*v:.2f}%'
def main():
    export=read(ROOT/'export_complete.json');host=read(ROOT/'host_complete_r2.json');arm=read(ROOT/'arm_compile_complete_r2.json');graph=read(ROOT/'graph.json')
    batch=read(ROOT/'board_batch_r2/complete.json');final=read(ROOT/'board_final_r2/complete.json');checks=read(ROOT/'validator_selfcheck.json')
    name=export['fixtures'][0]['name'];a=read(ROOT/('board_readback_'+name)/'validated.json');b=read(ROOT/('board_readback_r2_'+name)/'validated.json')
    assert len(batch['fixtures'])==8 and len(final['fixtures'])==1 and not batch['sd_written']
    assert batch['elf_sha256']==final['elf_sha256']==arm['elf_sha256']==b['elf_sha256']
    assert sha(arm['elf'])==arm['elf_sha256'] and sha(ROOT/'weights.f32')==arm['weights_sha256']
    assert sha(ROOT/'source_r2/road_fp32.c')==arm['host_verified_kernel_sha256']==host['source_sha256']['road_fp32.c']
    old=statistics.mean(x['total_seconds'] for x in a['trace_disabled_timing']);new=statistics.mean(x['total_seconds'] for x in b['trace_disabled_timing']);speed=old/new
    cv=read(ROOT/'validation320/complete.json');scores=cv['metrics'];night=scores['by_time']['night']
    out=ROOT/'release';out.mkdir(exist_ok=False);records=out/'证据与评测';records.mkdir();weights=out/'权重';weights.mkdir()
    shutil.copy2(ROOT/'weights.f32',weights/'weights.f32');shutil.copy2(WEIGHT,weights/'source_road4_best.pt')
    for p in ROOT.glob('*.json'):shutil.copy2(p,records/p.name)
    shutil.copy2(ROOT/'validation320/c_fp32_320_metrics.json',records/'c_fp32_320_metrics.json');shutil.copy2(ROOT/'validation320/c_fp32_320_predictions.json',records/'c_fp32_320_predictions.json')
    # Preserve numerical golden arrays for a full first case and head-only checks on all cases.
    for fixture in export['fixtures']:
        case=ROOT/'cases'/fixture['name'];dest=out/'cases'/fixture['name'];dest.mkdir(parents=True)
        for p in case.glob('*'):
            if p.is_file():shutil.copy2(p,dest/p.name)
        (dest/'golden').mkdir()
        selected=list((case/'golden').glob('*.f32')) if fixture['name']==name else [case/'golden'/f'{i:03d}.f32' for i in graph['heads']]
        for p in selected:shutil.copy2(p,dest/'golden'/p.name)
    # Actual physical bytes, including all86 tensors for optimized firmware.
    for folder in ['board_readback_r2_'+name,'board_batch_r2','board_final_r2']:
        shutil.copytree(ROOT/folder,out/folder)
    # Earlier firmware readback remains intact locally; include its validated receipt for speed comparison.
    shutil.copy2(ROOT/('board_readback_'+name)/'validated.json',records/'baseline_arm_r1_validated.json')
    shutil.copytree(ROOT/'source_r2',out/'C推理源码')
    py=out/'导出编译与验证脚本';py.mkdir()
    for filename in ['road_arm_common.py','road_adapt_common.py','export_road_arm.py','verify_road_arm_host.py','build_road_arm_probe.py',
                     'prepare_road_probe_tools.py','prepare_road_probe_batch.py','validate_road_arm_probe.py','validate_road_probe_batch.py',
                     'selfcheck_road_probe_validator.py','evaluate_road_c_validation.py','finish_road_arm_prototype.py','road_fp32.c','road_fp32.h','road_fp32_host.c','road_fp32_unit.c','road_arm_probe.c']:
        shutil.copy2(HERE/filename,py/filename)
    probe=out/'ARM固定图片程序';probe.mkdir()
    for filename in ['road_probe.elf','road_probe.map','elf_attributes.txt','trace_map.json','download_probe.tcl','batch_probe.tcl','final_probe.tcl','ps7_init.tcl','Xilinx.spec','build.log']:
        shutil.copy2(Path(arm['elf']).parent/filename,probe/filename)
    shutil.copytree(Path(arm['elf']).parent/'source',probe/'source')
    shutil.copytree(BASE/'yolov5',out/'yolov5',ignore=shutil.ignore_patterns('__pycache__','runs','.git','*.pyc','*.pt'))
    shutil.copy2(ROOT/'YOLOv5_LICENSE',out/'YOLOv5_LICENSE');shutil.copy2(BASE/'assets/BDD_DATA_LICENSE.txt',out/'BDD_DATA_LICENSE.txt')
    # Derived illustration from real ARM readback coordinates; never call it a screen photograph.
    previews=out/'实板读回框对照图';previews.mkdir();font=lambda size:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',size)
    colors=[(255,170,30),(0,230,255),(220,130,255),(60,255,110)]
    for j,fixture in enumerate([x for x in export['fixtures'] if x['kind']=='validation'],1):
        n=fixture['name'];raw=np.fromfile(ROOT/'cases'/n/'input400.u32','<u4').reshape(240,400)
        rgb=np.stack([raw&255,(raw>>8)&255,(raw>>16)&255],2).astype(np.uint8)
        canvas=Image.new('RGB',(848,430),'#f3f6f9');d=ImageDraw.Draw(canvas)
        d.text((16,8),'固定图片检测｜实板ARM读回框｜非屏幕实拍',font=font(25),fill='#18293e')
        d.text((16,45),fixture['source']+'    '+fixture['timeofday'],font=font(18),fill='#405068')
        for col,(title,path) in enumerate([('电脑PyTorch参考',ROOT/'cases'/n/'boxes400.f32'),('开发板ARM NEON读回',ROOT/'board_batch_r2'/n/'boxes400.f32')]):
            x0=16+col*416;d.text((x0,80),title,font=font(21),fill='#18293e');im=Image.fromarray(rgb);draw=ImageDraw.Draw(im);occupied=[]
            boxes=np.fromfile(path,'<f4').reshape(-1,6)
            for x1,y1,x2,y2,score,k in boxes:
                color=colors[int(k)];draw.rectangle((x1,y1,x2,y2),outline=color,width=2)
                if x2-x1>=55 and y2-y1>=18:
                    text=f'{NAMES[int(k)]} {score:.2f}';rect=draw.textbbox((0,0),text,font=font(11));tw=rect[2]-rect[0];tx=min(max(0,x1),400-tw);ty=max(0,y1-13);area=(tx,ty,tx+tw,ty+13)
                    if not any(area[0]<q[2] and area[2]>q[0] and area[1]<q[3] and area[3]>q[1] for q in occupied):
                        draw.text((tx,ty),text,font=font(11),fill=color,stroke_width=1,stroke_fill=(0,0,0));occupied.append(area)
            canvas.paste(im,(x0,117));d.text((x0,363),f'预测框数量：{len(boxes)}',font=font(21),fill='#405068')
        d.text((16,401),'置信度0.25；实现一致不代表所有框都正确，未接入实时摄像头。',font=font(19),fill='#405068')
        canvas.save(previews/f'{j:02d}_{n}.png')
    lines=[]
    for row in batch['fixtures']:lines.append(f'| {row["name"]} | {row["kind"]} | {row["boxes"]["boxes400"]["count"]} | {row["total_seconds"]:.3f} | {max(x["max_abs"] for x in row["heads"]):.7f} |')
    table=[]
    for k,m in night['classes'].items():table.append(f'| {k} | {m["objects"]} | {pct(m["ap50"])} | {pct(m["recall"])} | {m["fp"]} | {m["fn"]} |')
    mem=[]
    for region in arm['work_regions']:mem.append(f'| {region["name"]} | 0x{region["start"]:08X} | 0x{region["end"]:08X} | {region["bytes"]} |')
    report=f'''# 道路检测ARM原型：实板验收与性能优化

2026-10-27。历史目录后缀20261026保留，物理读回和优化验收在27日完成。

**道路检测网络已在XC7Z020的ARM Cortex-A9 #0上真实运行。** 6张真实道路验证图与全黑/随机2张控制图共8组，三尺度原始输出、解码、NMS及400×240框坐标全部通过数值核对；首张真实图片额外核对完整86节点。相同图片单帧重复测量均值由{old:.3f}秒降为{new:.3f}秒，约{speed:.2f}倍速度、耗时减少{(1-new/old)*100:.1f}%。**仍是低帧率固定图片原型，不是实时摄像头系统。** 本次尚未把检测框接到LCD，报告中的图来自真实读回坐标叠加，不是屏幕实拍。

## 谁执行了哪些计算

本原型的60个卷积、SiLU、7个残差加法、13个通道拼接、3次SPPF池化、2次上采样、三尺度解码和NMS都由ARM #0执行。86个节点包括输入节点与85个运算节点。NEON用于四输出通道向量累加，卷积优化让相邻4个输出位置复用同一组权重；边界保留原计算路径。没有改变检测权重，也没有用电脑替板卡计算结果。

此前FPGA图像增强IP保持原文件，本轮没有新综合或下载道路卷积加速IP。当前固定图测试不调用该增强IP、不采集摄像头，也不使用显示输出；ARM和PL图像增强/摄像头的集成还需要后续实现。不能把本次道路检测称为FPGA逻辑中的YOLO加速。

## 模型与输入

采用首轮冻结YOLOv5n v7.0四类person/car/truck/bus，原始checkpoint SHA256={sha(WEIGHT)}。权重未重训；FP32打包权重SHA256={sha(ROOT/'weights.f32')}，包含融合BN后的卷积与偏置、通道补齐及对齐，共{export['weight_bytes']}字节。它是具体CPU浮点模型，不是INT8网络，也不是bit流。

原始道路照片来自既有320张验证集，按照前轮确定顺序取3张夜间、2张黎明/黄昏、1张白天。400×240输入来自已有“先RGB565量化、再2×2平均”的采集顺序代理，并不是摄像头现场照片。本次没有使用新的独立测试集。

400×240到320×192采用明确的整数双线性：源坐标=(10×目标坐标+1)/8，四点权重分母64，最近半入取整，再上下各填64像素114，归一化/255。C与NumPy输出逐字节一致。这个明确取整规则与OpenCV INTER_LINEAR在部分半值处可差1个字节，因此实现没有隐瞒这一输入差异，也没有直接沿用旧FP16/OpenCV的精度数字。

## 正确性证据链

1. 从可信冻结checkpoint导出图，在PyTorch原语中独立执行导出图，三尺度原始头与源模型完全一致；融合前后输出亦通过容差核对。
2. 8组输入在电脑上由实际C执行。86节点逐一与PyTorch CPU FP32比较，要求误差≤1e-4+1e-4×参考绝对值；解码框允许0.02像素、分数2e-4；坐标还原与NMS框数量/类别均需一致。所有控制通过。
3. 标量C与电脑SSE2解码逐字节一致；优化前后电脑8组解码亦逐字节一致。Cortex-A9 NEON虽使用相同累加语义，仍进行了独立实板读取验证，没有用电脑SIMD结果替代实板证据。
4. JTAG实际载入ELF、权重及输入。ARM对权重/输入算FNV32，完成序列和错误码须正确；读回RGB、三尺度头、解码及框。首图读取完整{arm['trace_bytes']}字节中间层数据，优化版86节点最大绝对差{max(x['max_abs'] for x in b['layers']):.8f}；首图框坐标最大差{b['boxes']['boxes400']['max_coordinate_error']:.8f}像素。
5. 读回校验器在物理数据的副本上注入5种错误：输入哈希、固件身份、中间层、类别及陈旧序列，全部拒绝。它们是校验器负向测试，不是额外实板成功案例；真实读回文件保持原样。

实现一致只说明移植计算正确，不说明所有预测框都是真目标。误检、漏检仍须由标注评测。

## 实板固定图片时延

基线和优化版各在同一张首图上关闭中间层拷贝后重复3次：

| 实现 | 三次总耗时（秒） | 均值（秒） |
|---|---|---:|
| 基线四输出通道NEON | {', '.join(f'{x["total_seconds"]:.3f}' for x in a['trace_disabled_timing'])} | {old:.3f} |
| 四位置权重复用NEON | {', '.join(f'{x["total_seconds"]:.3f}' for x in b['trace_disabled_timing'])} | {new:.3f} |

以下为优化版8组全部实板案例，不挑选速度最快的图片。总耗时包含预处理、权重/输入校验、网络、后处理和输出cache写回；**不含JTAG传输、摄像头采集及屏幕显示**。不是端到端摄像头帧率，也没有作大样本性能保证。

| 输入 | 类型 | 预测框数 | 总耗时秒 | 三尺度头最大误差 |
|---|---|---:|---:|---:|
{chr(10).join(lines)}

## 实际C实现的320图验证指标

全部320张既有验证图通过真实电脑C程序执行，包括显式预处理、完整FP32网络、解码及NMS；没有用PyTorch输出冒充C预测。夜间160张mAP50={pct(night['mAP50'])}，mAP50:95={pct(night['mAP50_95'])}。AP置信度下限0.001，NMS IoU0.6，最多300框；下表召回/漏检固定置信度0.25、匹配IoU0.5。mAP不是图片识别正确率。

| 类别 | 夜间标注目标 | AP50 | 召回率 | 误检框 | 漏检目标 |
|---|---:|---:|---:|---:|---:|
{chr(10).join(table)}

旧同尺寸FP16/OpenCV预处理对照夜间mAP50约30.74%；当前C为30.59%。二者同时存在运算精度与预处理半值取整差异，不能把差值解释为新模型训练收益或只归因于某个算子。C320图验证与实板8组移植核对是两种证据，不声称已经在实板上测试全部320张照片。

## 内存、工具链和当前状态

工作特征缓冲{export['arena_bytes']}字节，基于完整计算图活跃期分配；执行时输出不与仍需读取的输入重叠。ELF采用Cortex-A9、NEON-VFPv3、hard-float、O3，无fast-math。编译开启Wall/Wextra/Werror，主栈64KiB；源函数最大静态栈使用{max(x['bytes'] for x in arm['function_stack_usage'])}字节。ELF段保持在0x00100000–0x01000000之间，工作内存和旧图像系统保留地址均作过重叠检查。静态内存审查不替代当前已完成的数值实板验收，也不证明后续相机并发路径已正确。

| 区域 | 起始地址 | 结束地址（不含） | 字节 |
|---|---|---|---:|
{chr(10).join(mem)}

优化版ELF SHA256={arm['elf_sha256']}。本轮通过JTAG只把程序和数据装入内存，未写SD或Flash，未覆盖原车牌启动文件。板卡当前停留在固定图片探针等待命令；最后已恢复并核对首张真实道路图，检测框数{final['fixtures'][0]['boxes']['boxes400']['count']}。旧摄像头应用在本次ARM测试中被暂停/替换，检测框尚未接入LCD；屏幕上的旧画面不能作为本次测试结果。

## 下一阶段

当前单帧约2秒级，不能描述为实时辅助驾驶。下一阶段先接入固定图片LCD显示和分阶段计时，再依据实测选择更小检测器/量化或PL卷积加速；摄像头实时集成必须单独验证缓存切换、框与当前帧对齐及端到端延迟。原图检测与增强显示分别验收，现有增强未证明能提高道路检测。

包中包含真实C源码、FP32权重、已验证ARM ELF、下载脚本、原始读回与校验结果、参考框和PyTorch源码许可。为控制大小，仅首张图片包含完整层级golden，其余保留头输出golden；本机完整8组层级golden仍在原目录。脚本使用本机E盘绝对路径，依赖既有隔离Python环境、Xilinx2020.2工具链及BSP；异机需调整路径。重复运行会拒绝覆盖已有冻结目录/读回目录，不能把包当成通用一键安装器。
'''
    path=ROOT/'道路检测ARM原型实板验收_20261027.md';path.write_text(report,encoding='utf-8');(out/path.name).write_text(report,encoding='utf-8')
    release_summary=dict(status='REAL_ARM_FP32_ROAD_INFERENCE_PROTOTYPE_VERIFIED_AND_OPTIMIZED',model_weights_sha256=sha(ROOT/'weights.f32'),elf_sha256=arm['elf_sha256'],
          baseline_mean_seconds=old,optimized_mean_seconds=new,speedup=speed,physical_fixtures=8,full_layer_physical_fixtures=1,
          real_c_validation_night_map50=night['mAP50'],camera_integrated=False,lcd_integrated=False,sd_written=False)
    write(out/'验收摘要.json',release_summary)
    files=sorted(p for p in out.rglob('*') if p.is_file());manifest=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in files]
    write(out/'manifest.json',manifest);archive=ROOT.parent/'road_arm_prototype_verified_20261027.zip';assert not archive.exists()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in files+[out/'manifest.json']:z.write(p,p.relative_to(out).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert all(hashlib.sha256(z.read(r['path'])).hexdigest()==r['sha256'] for r in manifest)
    write(ROOT/'release.json',dict(**release_summary,archive=str(archive),bytes=archive.stat().st_size,archive_sha256=sha(archive),all_hashes_verified=True))
    tracker=HERE.parents[1]/'道路感知项目当前进度_20261026.md';previous=tracker.read_text(encoding='utf-8')
    previous+=f'\n\n## 2026-10-27：ARM道路检测固定图片原型已实板验收\n\n报告：{path}。包：{archive}。YOLOv5n首轮权重不变，完整FP32道路检测已由A9#0/NEON执行，非FPGA道路卷积IP。8组实板三尺度头/解码/NMS通过，首图完整86节点通过；单帧同图均值{old:.3f}秒降至{new:.3f}秒（约{speed:.2f}倍），仍非实时。电脑实际C验证320张夜间mAP50={pct(night["mAP50"])}。SD/Flash未写。板卡当前为固定图探针，最终恢复首张真实图并核对14框，摄像头/LCD未接入，旧画面不代表新检测。下一步先做可见的固定图片显示，再按速度瓶颈推进更小模型/量化/PL加速，不可宣传增强已提高识别。\n'
    tracker.write_text(previous,encoding='utf-8')
    print('ROAD_ARM_PHYSICAL_RELEASE_VERIFIED',archive,sha(archive),flush=True)
if __name__=='__main__':main()
