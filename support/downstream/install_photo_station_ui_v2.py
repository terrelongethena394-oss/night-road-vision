"""Install the refreshed local UI on E:, preserving prior results and evidence."""
from pathlib import Path
from datetime import datetime
import json,shutil
import numpy as np
from PIL import Image
from photo_station_core import DELIVERY,RESULT_ROOT,STAGING,rgb,write_previews
from car_roi_delivery_common import read,write,sha

def main():
    old=Path(__file__).resolve().parents[2]/'图片传输与板卡处理_20261031'
    if (STAGING/'jtag.lock').exists():raise RuntimeError('A board task is active. Wait until it finishes before replacing the interface.')
    marker=DELIVERY/'资料/ui_v2_installation.json'
    if DELIVERY.exists() and any(DELIVERY.iterdir()) and not marker.exists():raise RuntimeError('Preserve existing E folder: installation marker missing.')
    DELIVERY.mkdir(exist_ok=True);RESULT_ROOT.mkdir(exist_ok=True);program=DELIVERY/'程序';program.mkdir(exist_ok=True);docs=DELIVERY/'资料';docs.mkdir(exist_ok=True)
    backup=STAGING/'ui_backups'/datetime.now().strftime('%Y%m%d_%H%M%S');backup.mkdir(parents=True)
    for name in ['photo_station_gui.py','photo_station_core.py','camera_station_core.py']:
        if (program/name).exists():shutil.copy2(program/name,backup/name)
    if (old/'源码/photo_station_gui.py').exists():shutil.copy2(old/'源码/photo_station_gui.py',backup/'legacy_photo_station_gui.py')
    if (STAGING/'gui_last_result.json').exists():shutil.copy2(STAGING/'gui_last_result.json',backup/'gui_last_result.json')
    if (old/'示例照片').exists():shutil.copytree(old/'示例照片',DELIVERY/'示例照片',dirs_exist_ok=True)
    if (old/'SD卡启动').exists():shutil.copytree(old/'SD卡启动',docs/'SD卡启动',dirs_exist_ok=True)
    # Runtime modules are kept on E alongside the public entry point.
    runtime_files=[]
    for p in Path(__file__).parent.glob('*.py'):
        dest=program/p.name;shutil.copy2(p,dest);runtime_files.append(dict(name=p.name,sha256=sha(dest)))
    relocated={}
    old_outputs=old/'输出'
    if old_outputs.exists():
        for source in sorted(p for p in old_outputs.iterdir() if p.is_dir()):
            target=RESULT_ROOT/source.name
            if target.exists() and not (target/'处理结果.json').exists():raise RuntimeError('Preserve unrelated output folder: '+str(target))
            shutil.copytree(source,target,dirs_exist_ok=True)
            receipt=target/'处理结果.json'
            if receipt.exists():
                r=read(receipt);r['copied_from_output']=str(source);r['output']=str(target);write(receipt,r)
                packet=Path(r['packet_evidence']);raw=rgb(packet/'raw.u32');enh=rgb(packet/'enhanced.u32');boxes=np.fromfile(packet/'boxes.f32','<f4').reshape(-1,6)
                write_previews(raw,enh,boxes,target)
                with Image.open(target/'07_电脑对照图.png') as im:
                    assert np.array_equal(np.asarray(im)[30:270,:400],raw),'Comparison original must have no overlay.'
                relocated[str(source)]=r
    previous=STAGING/'gui_last_result.json'
    if not previous.exists():previous=STAGING/'actual_roundtrip_verified.json'
    if previous.exists():
        r=read(previous)
        if r['output'] in relocated:write(STAGING/'gui_last_result.json',relocated[r['output']])
    command='@echo off\r\nchcp 65001 >nul\r\nstart "" "E:\\FPGA_Enhance_Work\\nn_env312\\Scripts\\pythonw.exe" "'+str(program/'photo_station_gui.py')+'"\r\nexit /b\r\n'
    (DELIVERY/'启动图片处理.cmd').write_text(command,encoding='utf-8')
    # Existing shortcut continues to open the refreshed E-drive application.
    (old/'启动图片处理.cmd').write_text(command,encoding='utf-8')
    (DELIVERY/'使用说明.md').write_text('''# 夜视工作台

双击“启动图片处理.cmd”。点击“选择照片”，再点击“开始处理”。左侧始终显示不带框的原图；右侧显示增强与汽车识别结果，可用“识别框”开关查看纯增强图。

## 摄像头抓拍

切换到“摄像头”，点击“开启取景”。板上RGB屏持续取景，电脑周期性回传预览，速度受下载器连接影响。构图完成后点击“抓拍处理”，程序自动停止取景并固定同一帧，在开发板上完成增强和汽车检测，回传结果并同步显示在RGB屏上。完成后可再次开启取景，拍下一张。

抓拍检测为单帧处理，板上耗时随画面内容变化：正常室内场景实测约7秒，本次夜间道路照片实测约37秒，另需上传和回传时间。室内抓拍从发起到保存结果实测约25秒。取景和检测互斥；处理时请保持供电和JTAG连接。关闭窗口时会等待当前任务结束。摄像头取景本身不执行汽车检测，手掌不属于识别类别。

点击“查看结果”打开本次文件夹。所有新结果保存在 `E:\\FPGA图像处理\\结果`，此前三次已验收结果也已复制到此目录。旧C盘记录保留，防止丢失。

界面已移除任务日志、长路径和底部技术说明，只保留简短状态及进度。底层诊断仍写入原有E盘工作目录，处理失败时会提示。

开发板独立供电，处理新照片时接好JTAG、摄像头和RGB屏。SD独立启动保持此前OFF/OFF设置；SD程序本轮没有改动。等待启动示例处理完后即可上传新照片。

图像增强和检测在板上完成。当前检测输入为原图，增强用于显示。摄像头功能复用同一模型及FPGA硬件，增加了取景和抓拍控制接口，没有训练或更换模型。照片输入等比例适配800×480，摄像头抓拍源帧为800×480，真实增强输出400×240。

首次开启摄像头会通过JTAG加载摄像头接口版到运行内存，可能比后续取景慢一些。本次不写SD卡；断电后仍从原来的稳定版SD程序启动，下次打开工作台可再次开启摄像头。

这是本机安装目录，依赖已有 `E:\\FPGA_Enhance_Work` 与Xilinx 2020.2环境。样例、程序及历史SD交付资料都在本文件夹内；结果不会上传互联网。
''',encoding='utf-8')
    (docs/'界面依赖.md').write_text('界面采用 CustomTkinter 5.2.2（MIT），仅安装于 E:/FPGA_Enhance_Work/photo_ui_lib，不修改全局Python。\n官方来源：https://pypi.org/project/customtkinter/5.2.2/\n',encoding='utf-8')
    record=dict(status='E_DRIVE_UI_V2_INSTALLED',application=str(DELIVERY),results=str(RESULT_ROOT),runtime=str(program),
        old_results_copied=len(relocated),originals_preserved=True,comparison_left_pixel_exact_raw=True,
        ui='Dark responsive photo/camera workbench; unannotated original; optional boxes on enhanced view; no log pane or technical footer',
        runtime_files=runtime_files,hardware_access=False,sd_written=False,model_changed=False,ui_backup=str(backup))
    write(marker,record);print('PHOTO_UI_V2_INSTALLED',DELIVERY,'RESULTS',RESULT_ROOT,'PREVIOUS_RESULTS',len(relocated),flush=True)

if __name__=='__main__':main()
