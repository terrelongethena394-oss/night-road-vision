"""Archive actual photo roundtrips and the local desktop entry point."""
from pathlib import Path
import json,shutil,zipfile
import numpy as np
from photo_station_core import DELIVERY,STAGING,APP,write_previews,rgb
from car_roi_delivery_common import read,write,sha

def main():
    jobs=sorted(p for p in (STAGING/'jobs').glob('*/complete.json'))
    assert len(jobs)>=2,'Wait for GUI roundtrip completion.'
    records=[read(p) for p in jobs]
    assert all(r['physical_readback'] and r['status']=='ACTUAL_PHOTO_UPLOAD_PROCESS_RETURN_PASS' and not r['sd_written'] for r in records)
    for r in records:
        packet=Path(r['packet_evidence']);out=Path(r['output']);boxes=np.fromfile(packet/'boxes.f32','<f4').reshape(-1,6)
        write_previews(rgb(packet/'raw.u32'),rgb(packet/'enhanced.u32'),boxes,out)
        assert sha(packet/'enhanced.u32')==r['enhanced_payload_sha256'] and sha(packet/'boxes.f32')==r['boxes_payload_sha256']
    last=records[-1];write(STAGING/'actual_roundtrip_verified.json',last);write(DELIVERY/'实际上板传输验收.json',dict(status='CLI_AND_GUI_ACTUAL_ROUNDTRIPS_PASS',records=records,sd_written=False))
    first=records[0]
    panel_path=DELIVERY/'实物屏幕确认.json'
    panel=read(panel_path) if panel_path.exists() else None
    panel_text='LCD帧缓冲与显示状态已自动核对；本轮实物面板光学确认另等用户反馈，不能将帧缓冲检查写成用户已确认。'
    if panel and panel.get('packet_evidence')==last['packet_evidence']:
        panel_text='用户已确认实物屏幕“'+panel['response']+'”：同一张固定夜间道路图同步显示，左侧原图、右侧更亮，且两侧有汽车框。记录见“实物屏幕确认.json”。'
    # The GUI run uses the identical user-selected PNG; compare board payloads exactly.
    for key in ['source_sha256','enhanced_payload_sha256','boxes_payload_sha256']:
        assert first[key]==records[1][key],key
    source=DELIVERY/'源码';source.mkdir(exist_ok=True)
    for name in ['photo_station_core.py','photo_station_gui.py','setup_photo_station_20261031.py','test_photo_station_host.py','verify_photo_station_roundtrip_20261031.py','finalize_photo_station_20261031.py','add_photo_station_wide_example_20261031.py']:
        shutil.copy2(Path(__file__).with_name(name),source/name)
    text=f'''# 单张照片系统实际验收

已完成命令入口及实际窗口按钮共{len(records)}次“图片上传→板上增强和汽车检测→结果回传→LCD显示”。前两次同一PNG输入的源图、板上增强像素和检测框逐字节一致。示例为已用于开发/板测的真实夜间道路图，仅用于系统传输验收，不作为新增准确率测试。

首次加载模式：{first['firmware_load_mode']}；板上耗时{first['board_processing_seconds']:.2f}秒，包含程序初始化、传输与读回的总耗时{first['wall_seconds']:.2f}秒。

窗口按钮模式：{last['firmware_load_mode']}；板上耗时{last['board_processing_seconds']:.2f}秒，含传输总耗时{last['wall_seconds']:.2f}秒。返回{last['car_count']}个汽车检测框，至多{last['roi_count']}个二次核验区域，实际PL卷积调用{last['pl_conv_calls']}次。

最后一次输入照片尺寸为{last['input']['oriented_original_size']}，实际缩放为{last['input']['resized_size']}、补边起点{last['input']['padding_xy']}。原始宽幅JPEG保留比例后上传，检测坐标另映射回原照片坐标系。

逐项检查：800×480上传源图与实际读回源图逐字节一致；板上400×240原图与源图降采样逐字节一致；模型指纹、无错误状态、调用次数和汽车框范围通过；800×480 LCD帧缓冲与绘制预期逐字节一致。增强图和检测框来自板上实际读回。电脑不执行增强或检测网络；仅解码缩放、传输、校验和绘制返回框。

检测权重、算子及增强算法沿用已验收ABI30；新的等比例补边输入流程未进行准确率评测，本轮未宣称新增识别准确率或增强后检测收益。图像保持比例补黑边；增强原始输出400×240，不伪装成原照片分辨率。照片模式当前固件仍需摄像头连接以完成初始化。

主机准备检查覆盖横图、竖图、EXIF旋转、透明图、中文带空格文件名及坐标映射。实际窗口已检查选择照片、预览和开始处理。输入在本机与板卡间传输，无互联网上传；SD卡和Flash没有修改。

{panel_text}

最新结果：`{last['output']}`。底层证据：`{last['packet_evidence']}`。启动入口为本目录“启动图片处理.cmd”。输出目录包含7张PNG和处理结果JSON。
'''
    (DELIVERY/'验收记录.md').write_text(text,encoding='utf-8')
    archive=STAGING/'photo_station_local_delivery_20261031.zip';manifest={}
    def add(z,p,name):
        z.write(p,name);manifest[name]=dict(bytes=p.stat().st_size,sha256=sha(p))
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
        for p in DELIVERY.rglob('*'):
            if p.is_file() and p.name!='归档校验.json':add(z,p,'photo_station/'+p.relative_to(DELIVERY).as_posix())
        for r in records:
            packet=Path(r['packet_evidence']);job=packet.parent
            for p in job.rglob('*'):
                if p.is_file() and p.name!='expected_frame.bgr':add(z,p,'actual_board/'+job.name+'/'+p.relative_to(job).as_posix())
        add(z,STAGING/'host_tests/complete.json','host_preparation_checks.json')
        z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    sd_release=STAGING.parent/'photo_station_sd_20261031_r1/sd_release_verified.json'
    sd=read(sd_release) if sd_release.exists() else None
    receipt=dict(status='ACTUAL_PHOTO_SYSTEM_DELIVERED',archive=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),crc_verified=True,
                 source_sha256={p.name:sha(p) for p in source.glob('*.py')},firmware_expected_elf_sha256=sha(APP/'road_detail.elf'),latest_output=last['output'],
                 sd_written=bool(sd and sd['sd_written']),physical_sd_cold_boot_verified=bool(sd and sd['physical_sd_cold_boot_verified']),
                 photo_roundtrip_tests_sd_written=False,sd_deployment_release=sd)
    write(DELIVERY/'归档校验.json',receipt);print('PHOTO_STATION_LOCAL_DELIVERY_VERIFIED',json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
