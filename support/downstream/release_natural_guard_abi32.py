"""Install only the fully board-verified display guard, keeping SD untouched."""
from pathlib import Path
import shutil
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from natural_guard_lab import ROOT,CASES,PROFILES,table
from photo_station_core import STAGING,DELIVERY
from car_roi_delivery_common import read,write,sha

def main():
    board=read(ROOT/'board_verified.json');assert board['status']=='NATURAL32_ACTUAL_ARM_PHOTO_AND_CAMERA_PASS'
    assert board['enhancement_pixels_byte_exact_to_reference'] and board['detector_bytes_unchanged_on_all_four']
    assert not (STAGING/'jtag.lock').exists()
    archive=ROOT/'desktop_backup';archive.mkdir(exist_ok=True)
    for name in ['photo_station_core.py','camera_station_core.py','camera_preview_stream.py','photo_station_gui.py']:
        p=DELIVERY/'程序'/name
        if p.exists() and not (archive/name).exists():shutil.copy2(p,archive/name)
    preference=STAGING/'preferred_runtime.json'
    if preference.exists() and not (archive/'preferred_runtime.json').exists():shutil.copy2(preference,archive/'preferred_runtime.json')
    write(preference,dict(status='ACTUAL_BOARD_PHOTO_CAMERA_VERIFIED',root=str(ROOT),version=32,
        proof_sha256=sha(ROOT/'board_verified.json'),elf_sha256=read(ROOT/'build_verified.json')['elf_sha256'],sd_written=False))
    from install_photo_station_ui_v2 import main as install
    install()
    pack=DELIVERY/'自然增强对照';pack.mkdir(exist_ok=True);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14)
    canvas=Image.new('RGB',(1200,1120),(12,18,28));d=ImageDraw.Draw(canvas);rows=[]
    for i,r in enumerate(sorted(board['photos'],key=lambda r:r['case'])):
        old=Path(r['baseline_output']);new=Path(r['output']);case=r['case']
        paths=[old/'02_板上原图400.png',old/'03_板上增强400.png',new/'03_板上增强400.png']
        means=[]
        for col,(label,path) in enumerate(zip(['RAW BOARD INPUT','OLD BOARD ENHANCEMENT','NATURAL BOARD ENHANCEMENT'],paths)):
            with Image.open(path) as im:
                im=im.convert('RGB');canvas.paste(im,(col*400,i*280+40));a=np.asarray(im,np.float32);means.append(float((a*np.array([54,183,19],np.float32)).sum(2).mean()/256))
            d.text((col*400+5,i*280+5),f'CASE {case} {label}',font=font,fill='white')
        shutil.copy2(new/'07_电脑对照图.png',pack/f'{case:02d}_{r["title"]}_原图与自然增强.png')
        canvas.crop((0,i*280,1200,(i+1)*280)).save(pack/f'{case:02d}_三列实板对照.png')
        rows.append(dict(case=case,title=r['title'],raw_mean_y=means[0],old_mean_y=means[1],natural_mean_y=means[2],car_boxes=r['car_count'],
            board_seconds=r['board_processing_seconds'],source_output=str(new),baseline_output=str(old),pixels_byte_exact=r['guard_pixels_byte_exact_to_reference'],detector_unchanged=r['detector_payload_byte_exact_to_ABI31']))
    canvas.save(pack/'四场景_原图_旧增强_自然增强.png')
    lines=['# 自然增强版验收','','新版本在原有增强后增加整数亮度约束：保护接近黑色的区域与灯光，限制暗部过大增益。没有增加空间模糊滤波，没有训练或替换模型。',
        '表中四张均为真实板上处理并读回的结果。原图、旧增强、新增强用于同一张输入，四张的汽车检测框与旧版逐字节一致。',
        '新结果与“旧版真实增强像素经过新整数约束”的参考结果逐字节一致；LCD实际帧缓冲也核对通过。','',
        '| 场景 | 原图均值 | 旧增强均值 | 自然增强均值 | 检测框数（与旧版相同） |',
        '|---|---:|---:|---:|---:|']
    for r in rows:lines.append(f"| {r['title']} | {r['raw_mean_y']:.1f} | {r['old_mean_y']:.1f} | {r['natural_mean_y']:.1f} | {r['car_boxes']} |")
    lines+=['','均值包含处理图中的补边，仅描述提亮幅度，不是画质评分。',
        '从这组已曝光场景的视觉对比看，新版减轻了灰雾、色块和过亮灯光，同时仍保留比原图更高的暗部可见性。原始图片中缺少的细节不能据此恢复；没有独立PSNR/SSIM提升结论。',
        '车辆识别输入仍是原图，误检和漏检没有因本次画质约束而改善。完整的标注核对见“道路场景验收”文件夹。',
        '摄像头快速取景和抓拍通过实板检查。电脑工作台默认通过JTAG加载自然增强版到运行内存，SD卡仍保留原来的独立启动程序。','',
        '打开“启动图片处理.cmd”即可。第一次连接或断电后需要重新加载运行程序，后续操作复用现有程序。']
    (pack/'验收说明.md').write_text('\n'.join(lines),encoding='utf-8')
    write(pack/'实板核对.json',dict(status='NATURAL32_BOARD_VERIFIED_RELEASED',rows=rows,
        camera=board['camera'],preview_job=board['preview_job'],models_changed=False,detection_accuracy_gain_claimed=False,sd_written=False))
    shutil.copy2(pack/'验收说明.md',DELIVERY/'资料/自然增强版说明.md')
    with (DELIVERY/'使用说明.md').open('a',encoding='utf-8') as f:f.write('\n\n## 自然增强版\n\n当前工作台默认使用已通过四场景与摄像头实板核对的自然增强版。它限制暗部过大增益并保护灯光，原有识别模型与阈值保持固定。三列实板对照与说明位于“自然增强对照”文件夹。SD卡启动程序没有改写。\n')
    write(ROOT/'released.json',dict(status='NATURAL32_RELEASED_AFTER_ACTUAL_BOARD_CHECKS',application=str(DELIVERY),comparison_folder=str(pack),rows=rows,sd_written=False))
    print('NATURAL32_RELEASED',pack,flush=True)

if __name__=='__main__':main()
