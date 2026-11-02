"""Record candidate status; only install after actual A/B acceptance."""
from pathlib import Path
import argparse,shutil
from car_roi_delivery_common import BASE,read,write,sha
from photo_station_core import DELIVERY,STAGING

OUT=BASE/'workbench_optimization_20261031_r1'

def main():
    p=argparse.ArgumentParser();p.add_argument('--install',action='store_true');a=p.parse_args()
    source=Path(__file__).parent
    names=['photo_station_core.py','camera_station_core.py','camera_preview_stream.py']
    candidate=OUT/'candidate_source';candidate.mkdir(exist_ok=True)
    for name in names:shutil.copy2(source/name,candidate/name)
    original=OUT/'stable_ui_source_backup';original.mkdir(exist_ok=True)
    for name in names:
        old=DELIVERY/'程序'/name
        if old.exists() and not (original/name).exists():shutil.copy2(old,original/name)
    screen=read(OUT/'current_model_screen/confidence_screen.json');assert not screen['qualified']
    offline=read(OUT/'offline_stream_tests/verified.json');assert offline['status']=='OFFLINE_IPC_AND_SHUTDOWN_TESTS_PASS'
    actual=OUT/'actual_benchmark_verified.json'
    measured=read(actual) if actual.exists() else None
    if a.install:
        assert measured and measured['status']=='ACTUAL_WORKBENCH_OPTIMIZATION_VERIFIED'
        assert measured['full_readback_verification_retained'] and not (STAGING/'jtag.lock').exists()
        from install_photo_station_ui_v2 import main as install
        install()
        preview=measured['preview'];repeat=measured['repeated_photo']
        text=f'''\n## 本次速度优化验收\n\n持续取景在同一个下载器连接内完成，固定103680字节预览包的稳态回传间隔中位数由 {preview['baseline_median_seconds']:.2f} 秒降至 {preview['optimized_steady_median_seconds']:.2f} 秒。第一次连接仍需等待初始化。\n\n重复处理同一张照片时，在板上保留的输入通过指纹匹配后跳过重复上传，板上仍会重新计算并校验输入。实测该重复照片完整流程由 {repeat['baseline']['wall_seconds']:.1f} 秒变为 {repeat['optimized']['wall_seconds']:.1f} 秒；更换照片的上传不会跳过。此结果不代表神经网络计算加速。\n\n完整源图、原图像素、增强图、检测框、摄像头缓存和LCD帧缓冲校验均保留。模型、阈值、FPGA位流及SD卡未更换。\n'''
        with (DELIVERY/'使用说明.md').open('a',encoding='utf-8') as f:f.write(text)
        shutil.copy2(OUT/'current_model_screen/汽车误检阈值检查.md',DELIVERY/'资料/汽车误检阈值检查.md')
        write(DELIVERY/'资料/workbench_optimization_verified.json',measured)
    record=dict(status='INSTALLED_AFTER_ACTUAL_BOARD_AB' if a.install else ('ACTUAL_BOARD_AB_PASSED_NOT_INSTALLED' if measured else 'CANDIDATE_OFFLINE_TESTED_AWAITING_BOARD'),
        sources={name:sha(candidate/name) for name in names},offline=offline['status'],
        confidence_screen=screen['status'],threshold_changed=False,model_changed=False,sd_written=False,installed=a.install)
    write(OUT/'candidate_status.json',record)
    print('WORKBENCH_OPTIMIZATION',record['status'],flush=True)

if __name__=='__main__':main()
