from pathlib import Path
from car_roi_delivery_common import BASE,read,write,sha
from photo_station_core import DELIVERY

def main():
    root=BASE/'workbench_optimization_20261031_r1';r=read(root/'actual_benchmark_verified.json');assert r['status']=='ACTUAL_WORKBENCH_OPTIMIZATION_VERIFIED'
    p=r['preview'];a=r['repeated_photo']['baseline'];b=r['repeated_photo']['optimized'];screen=read(root/'current_model_screen/confidence_screen.json')
    assert not screen['qualified'] and all(r['repeated_photo']['payload_byte_exact'].values())
    before,after=screen['records'][:2]
    text=f'''# 工作台优化验收

已用真实开发板完成对比，保留完整读回校验。模型、置信度阈值、FPGA位流及SD卡均未更换。

| 项目 | 优化前 | 优化后 |
|---|---:|---:|
| 电脑预览稳态回传间隔中位数 | {p['baseline_median_seconds']:.2f}秒 | {p['optimized_steady_median_seconds']:.2f}秒 |
| 重复同一张照片的处理与回传 | {a['wall_seconds']:.1f}秒 | {b['wall_seconds']:.1f}秒 |

预览保持连接后回传约快{p['speedup']:.1f}倍；第一次连接仍需初始化。重复照片通过输入指纹匹配后跳过再次上传，板上仍会重新计算。更换照片的测试已确认重新上传。以上为本机本次实测，不代表神经网络计算提速或实时车辆检测。

相同照片两次的原始输入、原图像素、增强像素及检测框逐字节一致。每次LCD帧缓冲均独立实际读回，和对应渲染结果逐字节核对通过。摄像头抓拍源图与冻结的摄像头缓存也逐字节一致。没有减少这些检查来换取速度。

## 识别参数的选择

在480张已用于开发的图片、4308个汽车标注上，置信度由0.25升到0.30会令误检从{before['fp']}降到{after['fp']}，但正确检出也由{before['tp']}降到{after['tp']}，召回率由{before['recall']:.2%}降到{after['recall']:.2%}。没有候选通过全部预设门槛，因此保留0.25。完整表见《汽车误检阈值检查.md》。本轮没有读取确认集来选择阈值，也没有新的准确率提升结论。

## 使用

打开E盘“启动图片处理.cmd”，进入“摄像头”，点击“开启取景”，然后“抓拍处理”。原图不加框，右侧可切换识别框。检测仍使用原图，增强用于显示。

SD卡启动程序保持原版；电脑工作台通过JTAG运行已验证的摄像头接口。结果保存在E盘“FPGA图像处理/结果”。
'''
    (root/'优化验收结果.md').write_text(text,encoding='utf-8');(DELIVERY/'资料/优化验收结果.md').write_text(text,encoding='utf-8')
    print('WORKBENCH_OPTIMIZATION_REPORT_SAVED',flush=True)
    print('REPEAT_TRANSFER_TIMINGS',b['transport_timings'],flush=True)
    print('CAMERA_TRANSFER_TIMINGS',r['camera_regression']['transport_timings'],flush=True)

if __name__=='__main__':main()
