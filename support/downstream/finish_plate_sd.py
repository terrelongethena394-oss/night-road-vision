"""Record successful SD file replacement, separately from physical cold boot."""
from pathlib import Path
import json,shutil,hashlib,zipfile
HERE=Path(__file__).resolve().parent
ROOT=Path('E:/FPGA_Enhance_Work/plate_sd_20261026')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    receipt=json.loads((ROOT/'sd_write_receipt.json').read_text(encoding='utf-8'))
    assert receipt['sd_written'] and receipt['filesystem_unmounted']
    assert sha(ROOT/'BOOT.BIN')==receipt['boot_sha256']
    old=ROOT/'jtag_writer/card_backup/BOOT.BIN.original'
    assert sha(old)==receipt['old_boot_backup']['sha256']
    source=ROOT/'jtag_writer'
    for name in ['build_sd_jtag_writer.py','verify_sd_jtag_transfer.py','prepare_plate_sd.py','finish_plate_sd.py']:
        shutil.copy2(HERE/name,source/name)
    shutil.copy2('E:/Xilinx/Vitis/2020.2/data/embeddedsw/license.txt',source/'XILINX_BSP_LICENSE.txt')
    fatfs=Path('E:/FPGA_Enhance_Work/camera_nn_sd_20261018/vitis_ws/nn_sd_platform/ps7_cortexa9_0/standalone_domain/bsp/ps7_cortexa9_0/libsrc/xilffs_v4_4/src/ff.c')
    text=fatfs.read_text(encoding='utf-8')
    (source/'FATFS_LICENSE.txt').write_text(text.split('/**')[0],encoding='utf-8')
    # Include existing application/model notices in addition to the helper BSP notices.
    notices=ROOT/'application_notices';notices.mkdir(exist_ok=True)
    board=Path('E:/FPGA_Enhance_Work/camera_plate_guarded_20261026')
    for name in ['LICENSE','NOTICE','MODEL_CARD.md','THIRD_PARTY_NOTICES.md','LPRNET_LICENSE.txt','FONT_LICENSE.txt']:
        shutil.copy2(board/name,notices/name)
    guide=f'''# 车牌版已通过JTAG写入SD卡

2026-10-26，使用JTAG运行ARM裸机FatFs辅助程序，经板上PS SD0控制器写入TF卡。已完成写入和完整字节读回校验，未格式化，未写Flash。物理SD断电启动仍待用户确认，不以JTAG恢复运行代替验收。

## 当前文件

- SD卡根目录BOOT.BIN：新版车牌程序，{receipt['boot_bytes']}字节，SHA256为{receipt['boot_sha256']}。
- SD卡根目录B0000001.BIN：原启动程序，{receipt['old_boot_backup']['bytes']}字节，SHA256为{receipt['old_boot_backup']['sha256']}。
- 电脑旧版完整备份：{old}。
- 电脑新版启动包：{ROOT/'BOOT.BIN'}。

写入顺序：先读取并备份旧BOOT到电脑；将新图像以PLTNEW.BIN写卡并同步关闭；从卡读回，电脑逐字节和SHA256核对；重新核对旧BOOT未变；将旧BOOT改名B0000001.BIN，再把临时文件改名BOOT.BIN；再次读回新文件及卡上旧备份，分别核对；卸载文件系统。所有阶段状态和字节转储在jtag_writer目录。旧启动文件与2026-10-18保存的版本一致。

## 现在如何独立启动

1. 关闭开发板电源。
2. 拔掉板端JTAG下载器，SD卡保持插在开发板TF卡槽，摄像头和屏幕保持连接。
3. BOOT_CFG的1、2均设置OFF，以开关ON丝印的相反方向为准。依据当前V3.9原理图，SD为OFF/OFF，JTAG为ON/ON；只在断电时切换。
4. 使用独立电源开机，等待约10秒。应出现实时摄像头画面及RAW/NET/AUTO标签。
5. 镜头前移动手掌确认实时变化，再把七位蓝牌对准绿框。没有车牌时显示“--”可以是正常拒识。

当前JTAG写卡辅助程序占用ARM，完成写卡并不意味着摄像头应用已通过SD启动。请实际执行上述断电步骤；结果尚未收到时，记录为NOT_YET_TESTED。

## 保留的功能范围

当前BOOT来自camera_plate_guarded_20261026：PL运行Multinex增强，ARM NEON运行七位蓝牌ROI识别及一致性保护；没有全图自动车牌定位、八位新能源牌识别或SD图片浏览。车牌照片不需要复制到SD卡才能用摄像头测试。旧版来源及完整回放评测仍保留，增强普遍提高识别率尚未证明。

## 恢复旧SD版本

旧BOOT有电脑和卡上双份备份。若要恢复，可通过读卡器先备份当前新版BOOT.BIN，再将B0000001.BIN的副本命名BOOT.BIN。无需格式化。辅助写卡脚本采用阶段门控并保留本次备份，不能直接反复执行整个目录；将来的再次写入应创建独立记录，防止覆盖本次恢复证据。
'''
    (ROOT/'JTAG写卡完成与独立启动说明.md').write_text(guide,encoding='utf-8')
    initial=ROOT/'使用说明.md'
    previous=initial.read_text(encoding='utf-8')
    if not previous.startswith('> 历史准备记录'):
        initial.write_text('> 历史准备记录：现已完成JTAG写卡，当前状态请看[JTAG写卡完成与独立启动说明](JTAG写卡完成与独立启动说明.md)及sd_write_receipt.json。\n\n'+previous,encoding='utf-8')
    tracker=HERE.parents[1]/'车牌项目当前进度_20261026.md'
    current=tracker.read_text(encoding='utf-8')
    update=f'''# SD启动更新（2026-10-26）

用户已授权通过JTAG写板上SD卡，操作已完成：新BOOT.BIN写入并全字节读回验证，SD原BOOT保留为B0000001.BIN，电脑另存{old}。卡已卸载，当前ARM为写卡辅助程序；等待用户关电、拔JTAG、BOOT_CFG OFF/OFF独立开机确认。SD实物冷启动尚未验收。

当前写卡收据：{ROOT/'sd_write_receipt.json'}；操作说明：{ROOT/'JTAG写卡完成与独立启动说明.md'}。JTAG模式为ON/ON，SD模式OFF/OFF，均仅在断电时切换。

以下保留写SD之前的JTAG验证记录，其中“SD未写”是历史状态：

'''
    if not current.startswith('# SD启动更新'):
        tracker.write_text(update+current,encoding='utf-8')
    files=sorted(p for p in ROOT.rglob('*') if p.is_file() and p.name not in ['sd_package_manifest.json','sd_release.json'])
    manifest=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in files]
    (ROOT/'sd_package_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    archive=ROOT.parent/'plate_sd_jtag_written_20261026.zip';assert not archive.exists()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in files+[ROOT/'sd_package_manifest.json']:z.write(p,p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert all(hashlib.sha256(z.read(r['path'])).hexdigest()==r['sha256'] for r in manifest)
    release=dict(archive=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,crc_and_all_manifest_hashes_verified=True,physical_sd_boot='NOT_YET_TESTED')
    (ROOT/'sd_release.json').write_text(json.dumps(release,indent=2),encoding='utf-8')
    print('SD_WRITE_EVIDENCE_ARCHIVED',json.dumps(release),flush=True)
if __name__=='__main__':main()
