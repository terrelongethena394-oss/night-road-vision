"""Save honest physical evidence and a compact restore-capable local release."""
from pathlib import Path
import json,shutil,zipfile
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from road_enhance_common import ROOT,OLD,NN,sha,write
HERE=Path(__file__).resolve().parent
APP=ROOT/'firmware'
def rgb(path):
 a=np.fromfile(path,'<u4').reshape(240,400);return np.stack([a&255,(a>>8)&255,(a>>16)&255],2).astype(np.uint8)
def main():
 session=json.loads((APP/'session_r1.json').read_text(encoding='utf-8'));assert session['status']=='ENHANCED_VIEW_RAW_DETECTION_DEPLOYED_AND_LIVE'
 proof=json.loads((APP/'board_fixed_r1/validated.json').read_text(encoding='utf-8'));assert proof['default_view_all86_bytes_exact_to_original_arm']
 for n,h in json.loads((APP/'runtime_checksums.json').read_text(encoding='utf-8')).items():assert sha(APP/n)==h,n
 assert 'ROAD_ENHANCE_CAMERA_LIVE_READY' in (APP/'activate_auto.log').read_text(encoding='utf-8')
 physical=APP/'board_fixed_r1/first_view_full';a=rgb(physical/'raw_result400.u32');b=rgb(physical/'result400.u32');im=Image.new('RGB',(800,328),'#0e1722');im.paste(Image.fromarray(a),(0,48));im.paste(Image.fromarray(b),(400,48));d=ImageDraw.Draw(im)
 font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',20);small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',13)
 d.text((12,13),'RAW / SAME SNAPSHOT',font=font,fill='white');d.text((412,13),'AUTO GAMMA / BOARD OUTPUT',font=font,fill='white')
 d.text((12,300),'Unscaled original RGB pixels from board DDR. Detection uses RAW; enhancement is display-only by default.',font=small,fill='white')
 preview=ROOT/'增强前后_实板固定夜景.png';im.save(preview)
 t=proof['timing'];frame=proof['frame_checks'][0]['ui_stats'];reg=json.loads((ROOT/'regression480/complete.json').read_text(encoding='utf-8'))
 report=HERE.parents[1]/'图像增强接入与实板验收_20261027.md'
 content=f'''# 图像增强接入与实板验收（2026-10-27）

已通过 JTAG 将增强显示功能加入当前摄像头道路检测版本，并保留连续运行。SD 卡和 Flash 未改动，断电后需再次 JTAG 加载本目录启动程序。

## 当前实际工作方式

摄像头原始快照分成两路：原图进入原有 FP32 道路检测器；同一张图经过 ARM 自适应 Gamma 与亮部保护后用于显示，检测框叠加在该增强图上。增强仅改变亮度，没有几何变换，所以框的位置对应同一冻结快照。

增强是传统整数查表算法，运行于 ARM，**不是新训练的神经网络增强器，也没有新增 FPGA 增强核**。道路检测权重和 bitstream 保持原版，仍有 12 个卷积层由 FPGA 计算，其余计算由 ARM 完成。此前约 3.4FPS 的整数检测实验版没有作为本次基础。

- 左侧 `LIVE RAW`：最新摄像头原图预览。
- 右侧 `ENH VIEW / RAW DET`：最近完成检测的增强快照，框来自这张快照的原图识别。
- `ENH …%`：自动混合强度；`BYPASS`：当前帧未进行提亮。它们不是识别置信度或提高的亮度百分比。
- 左右快照时间可能不同，画面有 SNAP ID 和 AGE。画质对比应使用同一冻结快照，不能把运动中的左右画面当作同步对照。

## 增强规则

Gamma 基础曲线为 0.65；单像素共用 RGB 增益，尽量保持通道比例；最大通道值低于 192 的区域逐渐允许提亮，高亮区域保留。增益上限约 2 倍，基础抬升上限 32 级；整帧亮度均值不高于 40 时全强度，高于等于 80 时旁路，中间线性过渡。像素黑值保持为黑，不恢复原本没有记录的细节；没有去噪、去模糊或超分辨模块。

浮点幂函数只用于电脑生成 256 项常量表，板上每帧执行整数统计、查表和乘法。

## 为什么默认不把增强图送入检测器

参数只在既有 320 张验证图片上选择，随后在既有 480 张留出图片上回归。该 480 图此前用于量化实验，不能再称全新盲测。全部结果保留，没有根据回归结果重选增强强度。

| 同一固定检测器、同一回归输入流程 | 原图检测 | 增强后检测 |
|---|---:|---:|
| 全集 mAP@0.5 | {reg['raw']['all']['mAP50']*100:.2f}% | {reg['auto']['all']['mAP50']*100:.2f}% |
| 夜间 mAP@0.5 | {reg['raw']['by_time']['night']['mAP50']*100:.2f}% | {reg['auto']['by_time']['night']['mAP50']*100:.2f}% |

直接增强后识别出现退步。因此默认采用“原图识别、增强显示”，保留识别器原来的输入；变亮本身不能证明识别更准。实验性“增强后识别”模式已接通，但默认关闭。

## 实板验证

- 默认增强显示模式：首张固定输入的全部 86 层检测张量，与原版实板记录逐字节一致。
- 6 张真实道路固定输入，以及纯黑和随机两个控制输入：增强像素、预处理、检测头、解码/NMS 和框检查通过。
- 实验性增强输入模式：首张图片的增强像素、检测输入、检测头和框通过独立参考检查；这证明接通了该路径，不代表检测收益。
- 摄像头真实输入、缓存平均、默认模式下增强后的结果画面、文字与整幅屏幕帧缓存通过检查，VDMA 未报错。
- 成功启动后确认产生至少两次摄像头检测结果。启动日志与当前程序文件哈希均已保存。

该固定暗光样本的亮度均值从 {frame['mean_in']} 到 {frame['mean_out']}（8 位像素值，非照度测量），最大单通道增量 {frame['max_delta']}；同一输入的实板读回如下。图片保持原像素和原尺寸，没有事后提亮。

![同一固定夜间输入的原图与实板增强结果]({preview.as_posix()})

## 同一固定输入的耗时

各模式预热 1 次、测量 3 次取中位数；这是预处理、检测及后处理的处理耗时，包含期间协同预览服务，不含最后一次结果复制和呈现。增强阶段记录可能包含服务回调，不能当作纯计算时间。未另行统计本版长期摄像头 FPS。

| 模式 | 处理耗时中位数 | 增强阶段跨度中位数 |
|---|---:|---:|
| 原图显示、原图识别 | {t['raw']['median_seconds']:.4f}s | {t['raw']['median_enhancement_span_ms']:.3f}ms |
| 实验：增强输入识别 | {t['input']['median_seconds']:.4f}s | {t['input']['median_enhancement_span_ms']:.3f}ms |
| 当前默认：增强显示、原图识别 | {t['view']['median_seconds']:.4f}s | {t['view']['median_enhancement_span_ms']:.3f}ms |

## 使用与恢复

- 当前程序：`{APP.as_posix()}/road_enhance.elf`。
- 断电后的 JTAG 启动：`{APP.as_posix()}/00_start_enhanced_detection.cmd`。
- `02_switch_raw.cmd` 切到原图显示和识别；`02_switch_auto.cmd` 恢复默认增强显示。两者在板卡保持供电且 JTAG 连接时运行，下一次结果开始生效。
- `02_switch_enhanced_input_experiment.cmd` 是实验性的增强后识别开关，已有精度退步记录。默认启动不会启用它。
- 恢复此前无增强的原版：`{OLD.as_posix()}/00_start_hybrid_ram.cmd`。
- 当前模式控制地址 `0x13800140`：0=原图，1=实验增强输入，2=增强显示/原图识别；程序 ABI 13。

此次途中曾发生 JTAG DAP 传输中断，首次回滚无法连接；重新连接后的首次相机启动未换帧，再次加载原版后恢复。随后完整重跑了本轮实板采集。初次主机绘图校验工具因引用旧的 11 字段界面头文件，而非候选的 15 字段头文件，读取退出；修正主机工具的引用路径后，同一批原始读回通过全部校验，板上程序和容差未改动。失败日志、修正说明及原会话均保留于 attempts、reconnect 日志和 renderer_repair.json。

文件：`{APP.as_posix()}/board_fixed_r1/validated.json`、`session_r1.json`、`activate_auto.log`。功能说明不包含“增强普遍提升检测精度”或“已达到实时检测”的结论。
'''
 report.write_text(content,encoding='utf-8')
 release=ROOT/'release';release.mkdir(exist_ok=False)
 def copy(src,dest):
  p=release/dest;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,p)
 for d in ['source','runtime']:
  for p in (APP/d).rglob('*'):
   if p.is_file():copy(p,'firmware/'+str(p.relative_to(APP)))
 for n in ['road_enhance.elf','display.bit','display.xsa','ps7_init.tcl','Xilinx.spec','runtime_checksums.json','start_auto_live.py','start_auto_live.tcl','camera_common.tcl','scan_only.tcl','test_ram.tcl','arm_complete.json','test_prepared.json','session_r1.json','activate_auto.log','validation.log','validation_repaired.log','restore_after_reconnect_retry1.log']:
  copy(APP/n,'firmware/'+n)
 for p in APP.glob('*.cmd'):copy(p,'firmware/'+p.name)
 copy(APP/'board_fixed_r1/validated.json','evidence/physical_validation.json')
 for n in ['protocol.json','numeric_complete.json','selected.json','integration_addendum.json','regression480/complete.json','regression480/protocol.json','renderer_repair.json']:
  copy(ROOT/n,'evidence/'+n)
 for n in ['road_enhance.c','road_enhance.h','road_enhance_common.py','prepare_road_enhance.py','evaluate_road_enhance.py','regress_road_enhance.py','prepare_road_enhance_app.py','build_road_enhance_app.py','prepare_road_enhance_tools.py','validate_road_enhance.py','run_road_enhance.py','repair_road_enhance_renderer.py','activate_road_enhance_after_repair.py','finish_road_enhance.py']:
  copy(HERE/n,'reproduce/'+n)
 copy(report,report.name);copy(preview,preview.name)
 restore=Path('E:/FPGA_Enhance_Work/road_hybrid_verified_20261027_r1.zip');assert sha(restore)=='4350f7bb5c4f150f5857f13730f2e185293edaae7f56f567afb78877e79019de';copy(restore,'rollback/verified_fp32_hybrid.zip')
 license=Path('E:/FPGA_Enhance_Work/road_conv_hls_20261027/YOLOv5_LICENSE');copy(license,'YOLOv5_LICENSE')
 (release/'README.md').write_text('当前默认为 ARM 自适应Gamma增强显示、原图FP32道路检测，程序 ABI13。增强后识别属于可选实验，已有离线退步记录，默认关闭。SD/Flash未写。\n\n本包是本机检查点，脚本使用 E:/FPGA_Enhance_Work/road_enhance_20261027 等绝对路径。移到其他电脑需调整路径并提供原工具链/BSP和项目依赖。原始摄像头缓存和全部中间张量保存在工作目录，未全部重复打包；图像展示仅使用公开固定道路测试输入。\n\n保留YOLOv5 GPL-3.0及原厂代码中的版权声明。\n',encoding='utf-8')
 hashes={str(p.relative_to(release)):sha(p) for p in release.rglob('*') if p.is_file()};write(release/'checksums.json',hashes)
 target=ROOT.with_suffix('.zip');assert not target.exists()
 with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in sorted(release.rglob('*')):
   if p.is_file():z.write(p,str(p.relative_to(release)))
 with zipfile.ZipFile(target) as z:assert z.testzip() is None
 status=dict(status='ENHANCED_VIEW_RAW_DETECTION_DEPLOYED_VERIFIED_AND_PACKAGED',elf_sha256=sha(APP/'road_enhance.elf'),bit_sha256=sha(APP/'display.bit'),default_mode=2,enhancement_processor='ARM',detection_input='RAW',neural_enhancement=False,all86_detection_tensors_unchanged=True,sd_written=False,flash_written=False,report=str(report),archive=str(target),archive_bytes=target.stat().st_size,archive_sha256=sha(target))
 write(ROOT/'release_complete.json',status);print(json.dumps(status,indent=2,ensure_ascii=True),flush=True)
if __name__=='__main__':main()
