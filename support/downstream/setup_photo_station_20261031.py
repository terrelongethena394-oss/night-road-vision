from pathlib import Path
import numpy as np
from PIL import Image
from photo_station_core import DELIVERY,STAGING,BOARD
from car_roi_delivery_common import write,sha

def main():
    DELIVERY.mkdir(exist_ok=True);examples=DELIVERY/'示例照片';examples.mkdir(exist_ok=True)
    a=np.fromfile(BOARD/'fixtures/road0.bgr',np.uint8).reshape(480,800,3)[:,:,::-1]
    path=examples/'夜间道路示例.png';Image.fromarray(a).save(path)
    write(examples/'来源.json',dict(source='Existing real night-road fixture, already used in development/board tests; demonstration only, not a new accuracy test.',
       input_fixture=str(BOARD/'fixtures/road0.bgr'),input_fixture_sha256=sha(BOARD/'fixtures/road0.bgr'),sample_png_sha256=sha(path)))
    gui=Path(__file__).with_name('photo_station_gui.py').resolve();python=Path('E:/FPGA_Enhance_Work/nn_env312/Scripts/python.exe')
    # UTF-8 codepage is set before the Unicode path is parsed by cmd.exe.
    command='@echo off\r\nchcp 65001 >nul\r\n"'+str(python)+'" "'+str(gui)+'"\r\nif errorlevel 1 pause\r\n'
    (DELIVERY/'启动图片处理.cmd').write_text(command,encoding='utf-8')
    (DELIVERY/'使用说明.md').write_text(f'''# 单张照片上传、板上处理和回传

双击本文件夹的“启动图片处理.cmd”，点击“选择照片”，再点击“传给开发板处理”。可先选择“示例照片/夜间道路示例.png”，也可选择自己的JPG、PNG、BMP、WebP照片。

电脑与JTAG下载器相连，开发板独立供电，RGB屏和摄像头保持此前已验证的连接。当前固件初始化仍需要OV5640连接，照片模式不采集摄像头画面。启动模式沿用已经验证的JTAG设置。

程序自动检查现有处理程序，必要时加载已验收ABI30到运行内存。它不写SD卡或Flash。首次加载较慢；单张道路图板上处理约36秒，上传和回传另需时间。处理中保持供电，暂勿运行其他JTAG下载任务。完成后LCD停留在本张照片，移动手掌不会改变它；下一张照片需再次点击处理。

输入先等比例缩放并补黑边至800×480，板上增强图实际为400×240，LCD实际帧为800×480。保存结果不会伪装成原图分辨率。当前检测类别是汽车，尚不是车牌字符识别或通用障碍物识别。

结果位于本文件夹“输出/时间戳”，包括板卡输入、实际板上原图与增强图、带汽车框的照片、LCD实际读回、电脑对照图和处理结果JSON。检测框源于板上原图及ROI核验，再叠加到增强图展示；不能把它描述成增强后检测。电脑不运行增强网络或检测网络来替代板卡结果。

照片在本机与开发板间传输，不上传到互联网。原照片不修改。低层日志和实际二进制读回保留在`{STAGING}/jobs/时间戳`。

实现源码入口：`{gui}`；本机依赖既有Python、Pillow、NumPy及Xilinx 2020.2环境，不能直接当作其他电脑的一键安装包。断电后RAM程序消失，再次使用时由入口重新加载。
''',encoding='utf-8')
    print('PHOTO_STATION_SETUP_READY',DELIVERY,flush=True)

if __name__=='__main__':main()
