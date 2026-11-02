"""Package the physically validated fixed-photo LCD road detector."""
from pathlib import Path
import hashlib,shutil,zipfile,tkinter
from road_arm_common import ROOT as NN,read,write,sha
from prepare_road_lcd_static import ROOT
HERE=Path(__file__).resolve().parent
def main():
    o=read(ROOT/'offline_complete.json');photos=read(ROOT/'photos.json');human=read(ROOT/'user_visual_confirmation.json')
    folders=['board_'+photos[0]['fixture'],'board_switch_photo04','board_final_photo01']
    results=[read(ROOT/f/'validated.json') for f in folders]
    assert human['physical_panel_visually_confirmed'] and all(r['render_matches_host_every_byte'] and r['dma_errors']==0 for r in results)
    assert all(r['elf_sha256']==o['elf_sha256'] and r['bit_sha256']==o['bit_sha256'] for r in results)
    assert sha(ROOT/'source/road_fp32.c')==read(NN/'arm_compile_complete_r2.json')['host_verified_kernel_sha256']
    assert [r['frame_slot'] for r in results]==[1,0,1]
    assert sha(ROOT/'runtime/weights.f32')==o['weights_sha256'] and sha(ROOT/'road_lcd.elf')==o['elf_sha256']
    for p in photos:
        assert sha(ROOT/'inputs'/p['input_file'])==p['sha256']
    # Syntax AND dictionary semantics, not just balanced Tcl braces.
    interp=tkinter.Tcl();line=next(x for x in (ROOT/'switch_photo.tcl').read_text().splitlines() if x.startswith('set cases [dict create '))
    interp.eval(line);assert int(interp.eval('dict size $cases'))==6
    for p in photos:
        value=interp.eval('dict get $cases '+str(p['index']));assert value.split()[0]==p['fixture'] and int(value.split()[1])==p['fnv32']
    for name in ['switch_photo.tcl','install_ram.tcl']:assert int(interp.call('info','complete',(ROOT/name).read_text()))==1
    out=ROOT/'release';out.mkdir(exist_ok=False)
    for name in ['road_lcd.elf','display.bit','display.xsa','ps7_init.tcl','Xilinx.spec','install_ram.tcl','switch_photo.tcl','photos.json']:
        shutil.copy2(ROOT/name,out/name)
    for p in ROOT.glob('*.cmd'):shutil.copy2(p,out/p.name)
    shutil.copytree(ROOT/'source',out/'source');shutil.copytree(ROOT/'inputs',out/'inputs');shutil.copytree(ROOT/'runtime',out/'runtime')
    code=out/'构建与验证脚本';code.mkdir()
    for name in ['prepare_road_lcd_static.py','prepare_road_lcd_tools.py','prepare_road_lcd_switches.py','validate_road_lcd_static.py','finish_road_lcd_static.py',
                 'road_arm_common.py','road_adapt_common.py','build_road_arm_probe.py','verify_road_arm_host.py','road_lcd.c','road_lcd.h','road_lcd_draw.c','road_lcd_draw.h','road_lcd_draw_host.c']:
        shutil.copy2(HERE/name,code/name)
    record=out/'实板证据';record.mkdir()
    for f in folders:shutil.copytree(ROOT/f,record/f)
    for name in ['offline_complete.json','renderer_host_proof.json','download_tools.json','switch_tools.json','user_visual_confirmation.json','build.log','road_lcd.map']:
        shutil.copy2(ROOT/name,record/name)
    for name in ['road_lcd_download_20261027.log','road_lcd_recover_readback_20261027.log','road_lcd_switch04_r1_20261027.log','road_lcd_final_photo01_20261027.log']:
        shutil.copy2(ROOT.parent/name,record/name)
    shutil.copy2(NN/'YOLOv5_LICENSE',out/'YOLOv5_LICENSE');shutil.copy2(NN/'release/BDD_DATA_LICENSE.txt',out/'BDD_DATA_LICENSE.txt')
    # Keep prior numeric and model-format evidence without duplicating its full archive.
    for name in ['graph.json','host_complete_r2.json','arm_compile_complete_r2.json','export_complete.json']:
        shutil.copy2(NN/name,record/('prior_'+name))
    image_dir=out/'显示缓冲读回图';image_dir.mkdir()
    for index,(folder,result) in enumerate(zip(folders,results),1):
        shutil.copy2(ROOT/folder/'actual_framebuffer.png',image_dir/f'{index:02d}_{result["fixture"]}.png')
    photo_rows='\n'.join(f'| {p["index"]:02d}_photo.cmd | {p["source_name"]} | {p["timeofday"]} |' for p in photos)
    measured_rows='\n'.join(f'| {p["fixture"]} | {p["frame_slot"]} | {p["boxes"]["boxes400"]["count"]} | {p["inference_seconds"]:.3f} | {p["render_and_present_seconds"]:.3f} | 是 |' for p in results)
    readme=f'''# 固定道路图片识别与LCD显示：已上板验收

2026-10-27，领航者XC7Z020 V3.9，ATK-MD0700R-800480。

**已完成“固定道路图片→ARM神经网络检测→绘框→PL视频输出→LCD显示”的闭环，并获得用户确认：有固定道路图片和检测框，文字、颜色正常。** 当前屏幕恢复PHOTO01夜间道路图，显示14个预测框。它们是模型预测，不能将框数当作正确目标数。

这是固定图片验证版，界面标注STATIC ROAD TEST和CAMERA OFF。未接入摄像头，也没有在这一版加入图像增强；不宣称增强提高识别。识别计算约2.2秒/张，尚未达到实时检测。显示时序约60Hz只是面板刷屏频率，不能当作识别帧率。

## 现在怎么用

当前已运行，不需要再次安装。保持板卡供电，当前固定图片可以持续显示。

将下载器接好后，逐个双击本目录的01_photo.cmd至06_photo.cmd即可换照片。等待窗口出现ROAD_LCD_PHOTO_SWITCH_COMPLETE后再切下一张。脚本只传新输入到DDR、触发板上计算，不重启CPU或重新下载权重；不会写SD。每次切换包含传图和约2.2秒推理，不能按摄像头即时预览理解。

| 双击文件 | 原照片 | 标注时段 |
|---|---|---|
{photo_rows}

dawn/dusk为黎明/黄昏合并标注。六张都是真实BDD100K道路验证帧，来自此前已固定的示例顺序，不是新独立测试集。本轮实际逐字节读回抽查PHOTO01、PHOTO04，再恢复PHOTO01；不能称为六张LCD全部逐帧验收。此前ARM探针已对这六张及两个控制输入做过神经网络输出核对。

断电后这份内存程序会丢失。需要恢复此固定图版本时，可在同一硬件和工具路径下双击00_install_ram.cmd：它经JTAG配置现有显示bit、初始化PS并下载ARM程序/内存数据，不格式化、不写SD或Flash。当前电脑XSCT路径为E:/Xilinx/Vitis/2020.2/bin/xsct.bat；换电脑或安装路径时需编辑cmd中的工具路径。RAM重装脚本由已执行的加载流程整理并修正地址映射，发布目录中的便携副本尚未再作一次断电重装测试。

## 屏幕含义

- STATIC ROAD TEST：固定道路图片测试。
- PHOTO01至PHOTO06：当前输入编号。
- BOXES：置信度高于0.25、NMS之后的预测框数。
- DETECT ... MS：这一张的计算耗时，含输入/权重校验、预处理、网络、后处理及检测输出cache写回，不含JTAG传输和LCD绘图/帧切换。
- 橙色PERSON、青色CAR、紫色TRUCK、绿色BUS：行人、汽车、卡车、公交车。小框仅画边线，较大框附类别和置信度，避免标签大量重叠。

道路图400×240按2倍显示到800×480，检测框也按相同倍率映射；上、下状态栏覆盖部分图像区域。右下角CAMERA OFF表示本应用不采集摄像头输入。

## 做了什么，谁负责什么

沿用上一轮已实板验收的YOLOv5n四类FP32模型、同一份C/NEON推理内核和固定权重。卷积/C3/SPPF/SiLU、检测头、解码、NMS与软件绘框由ARM Cortex-A9 #0执行。

PL沿用原已验证显示硬件：VDMA读取DDR显示帧、时钟与VTC产生LCD视频时序。显示bit内容没有修改，本轮经JTAG重新配置这份已有bit；没有新综合道路卷积IP，也没有把道路CNN计算移进FPGA逻辑。旧Multinex增强IP仍包含在该bit中，但固定图显示版没有启动它。

显示帧使用0x02000000起始的三个预留缓冲，实际在前两个之间切换；仅绘制当前未显示的帧，flush后请求VDMA切换，并等待当前读帧号确认。检测器仍使用0x10000000以上的既有区域，ELF在0x00100000至0x01000000范围内，已检查不重叠。

## 本轮实板验收

三次读取均核对：输入/权重FNV、三尺度原始输出、解码与NMS框、LCD型号0x7084、无VDMA错误、实际活动缓冲槽，以及整个1152000字节BGR显示帧。显示帧使用实板计算得到的框在电脑上重绘，逐字节完全一致。不是把电脑生成的框直接下载到屏幕。

| 照片 | 显示槽 | 框数 | 检测计算秒 | 绘图及帧切换秒 | 完整画面字节一致 |
|---|---:|---:|---:|---:|---|
{measured_rows}

缓冲槽按1→0→1切换，确认照片变化和双缓冲交换。用户对第一次夜间显示作了实物确认；显示缓冲读回PNG是板上内存图像，不是屏幕拍照。实物反馈记录在user_visual_confirmation.json。

首次调试在只读VDMA状态时，XSCT因未加载XSA地址映射拒绝访问PL地址。ARM显示程序本身已经完成。随后loadhw读取正确硬件映射并补齐状态读回；当前安装工具已加入该步骤。首次保留DDR中的权重校验不符时，ARM也拒绝使用，工具重新传入冻结权重后才允许推理。不能只根据XSCT进程返回0判定成功；cmd会检查专用完成标记，完整验收还需要数值/画面校验。

## 文件和边界

- road_lcd.elf、display.bit、display.xsa、ps7_init.tcl：当前程序与现有硬件描述。
- runtime/weights.f32与输入数据：真实冻结权重和400×240输入；权重SHA256={o['weights_sha256']}。
- source/：推理、绘图、显示胶水及原厂驱动源码，保留版权头。
- 实板证据/与显示缓冲读回图/：实际寄存器/张量/框/画面、校验结果及用户确认。
- 构建与验证脚本/：本机编译、工具准备、帧校验代码；构建依赖既有Xilinx2020.2 BSP和隔离Python环境，非通用安装器。

ELF SHA256={o['elf_sha256']}；bit SHA256={o['bit_sha256']}。SD卡原车牌启动文件未更改；本次程序只存在于配置RAM和DDR中。更换图片仍需JTAG，当前版本没有增加SD图片读取或脱机自动轮播。

下一阶段应优先降低检测耗时，再接入摄像头并分别测量采集、识别与显示延迟。当前完成的是可在实物屏幕观察的固定图道路检测原型。
'''
    path=ROOT/'固定图片道路检测_LCD使用与验收.md';path.write_text(readme,encoding='utf-8');(out/path.name).write_text(readme,encoding='utf-8')
    summary=dict(status='STATIC_ROAD_DETECTION_LCD_PHYSICALLY_CONFIRMED_AND_FRAMEBUFFER_VERIFIED',photos_available=6,
       physical_frame_checks=3,distinct_photos_physically_readback=2,buffer_slots=[r['frame_slot'] for r in results],
       physical_panel_visually_confirmed=True,final_photo=1,final_boxes=results[-1]['boxes']['boxes400']['count'],
       final_frame_sha256=results[-1]['frame_sha256'],inference_seconds=results[-1]['inference_seconds'],camera_enabled=False,enhancement_active=False,sd_written=False,
       elf_sha256=o['elf_sha256'],bit_sha256=o['bit_sha256'])
    write(out/'验收摘要.json',summary)
    files=sorted(p for p in out.rglob('*') if p.is_file());manifest=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in files];write(out/'manifest.json',manifest)
    archive=ROOT.parent/'road_lcd_static_verified_20261027.zip';assert not archive.exists()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in files+[out/'manifest.json']:z.write(p,p.relative_to(out).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert all(hashlib.sha256(z.read(r['path'])).hexdigest()==r['sha256'] for r in manifest)
    write(ROOT/'release.json',dict(**summary,archive=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),all_hashes_verified=True))
    tracker=HERE.parents[1]/'道路感知项目当前进度_20261026.md';old=tracker.read_text(encoding='utf-8')
    old+=f'\n\n## 2026-10-27：固定图道路检测已接LCD并获得实物确认\n\n目录{ROOT}；报告{path}；包{archive}。使用同一已验收ARM NEON内核，沿用PL显示bit，三次完整1152000字节帧读回一致，照片1→4→1、缓冲1→0→1均通过。用户确认固定道路图/框/文字/颜色正常。六图切换cmd已准备，最后恢复PHOTO01夜间14框，检测约{results[-1]["inference_seconds"]:.2f}秒/张。尚无摄像头输入、无图像增强调用、无SD写入；旧SD程序保留。下一步优先压低耗时再做摄像头延迟验收。\n'
    tracker.write_text(old,encoding='utf-8');print('ROAD_STATIC_LCD_RELEASE_VERIFIED',archive,sha(archive),flush=True)
if __name__=='__main__':main()
