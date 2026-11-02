"""Publish a truthful offline-ready package when physical JTAG is unavailable."""
from pathlib import Path
import json,shutil,zipfile
from recognition_upgrade_common import ROOT,BASE,sha,write
BOARD=BASE/'multinex_camera_digit_upgrade_20261026'
HERE=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def main():
    run=ROOT/'run03';held=read(run/'test/results.json');freeze=read(run/'frozen_candidate.json')
    compiled=read(BOARD/'offline_camera.json');proof=read(run/'native/complete.json');reg=read(run/'regression/results.json');fresh=read(run/'fresh_photos/results.json')
    assert held['accepted'] and reg['accepted']
    assert freeze['sha256']==held['model_sha256']==proof['model_sha256']==fresh['model_sha256']==sha(BOARD/'classifier.pth')
    assert sha(BOARD/'camera.elf')==compiled['elf_sha256'] and sha(BOARD/'camera.bit')==compiled['bit_sha256']
    assert sha(BOARD/'app_src/digit_arm_kernel.h')==proof['kernel_sha256'] and sha(BOARD/'app_src/cnn_weights.h')==proof['weights_header_sha256']
    assert sha(BOARD/'classifier_integer_weights.npz')==proof['integer_weights_sha256']
    assert sha(BASE/'real_digit_training_20261025/cnn_candidate/real_digit_cnn.pth')=='07478560652fdd4c73e6347f8494cdceecd90cda3f62d8705cbb229babc32493'
    dest=BOARD/'external_photo_check';dest.mkdir(exist_ok=True)
    for p in (run/'fresh_photos').iterdir():
        if p.is_file():shutil.copy2(p,dest/p.name)
    for name in ['sampling_protocol.json','annotations.json']:
        shutil.copy2(ROOT/'fresh_house_photos'/name,dest/name)
    for i in [0,1,5]:
        for ext in ['jpg','json']:shutil.copy2(ROOT/'fresh_house_photos'/f'photo_{i}.{ext}',dest/f'photo_{i}.{ext}')
    credits=read(dest/'credits.json')
    (dest/'CREDITS.md').write_text('# 原图及派生裁剪署名\n\n'+'\n\n'.join(f'- [{r["title"]}]({r["page"]})：{r["author"]}；[{r["license"]}]({r["license_url"]})。修改：人工裁剪数字、RGB565/灰度转换、缩放和添加边距；派生图片保留相应原图许可。' for r in credits),encoding='utf-8')
    for name in ['train_recognition_upgrade.py','recognition_upgrade_common.py','evaluate_recognition_upgrade.py','stage_upgrade_camera.py','prepare_upgrade_release.py','finish_upgrade_camera.py']:
        shutil.copy2(HERE/name,BOARD/name)
    shutil.copy2(HERE/'run_checked.tcl',BOARD/'run_checked.tcl')
    (BOARD/'download_jtag.cmd').write_bytes(b'@echo off\r\nsetlocal\r\ncd /d "%~dp0"\r\nif not exist "E:\\Xilinx\\Vitis\\2020.2\\bin\\xsct.bat" (\r\n echo XSCT not found at E:\\Xilinx\\Vitis\\2020.2\\bin\\xsct.bat\r\n pause\r\n exit /b 2\r\n)\r\n:choose_log\r\nset "runlog=%~dp0download_jtag_%RANDOM%_%RANDOM%.log"\r\nif exist "%runlog%" goto choose_log\r\ncall "E:\\Xilinx\\Vitis\\2020.2\\bin\\xsct.bat" "%~dp0run_checked.tcl" "%~dp0start_multinex_camera.tcl" >"%runlog%" 2>&1\r\ntype "%runlog%"\r\nfindstr /c:"MULTINEX_CAMERA_STARTED" "%runlog%" >nul\r\nset "result=%errorlevel%"\r\nif not "%result%"=="0" echo Download failed. Check board power, JTAG cable and boot switches.\r\nif "%result%"=="0" echo Download complete. Keep board powered for live camera operation.\r\npause\r\nexit /b %result%\r\n')
    names={'svhn':'SVHN街景数字','chars':'Chars74K场景字符','fonts':'合成字体（家族留出）','mnist':'MNIST手写数字','background':'平坦/噪声背景控制'}
    table='\n'.join(f'| {names[k]} | {r["n"]} | {100*r["old_raw"]["accuracy"]:.2f}% | {100*r["old_normalized"]["accuracy"]:.2f}% | {100*r["new_normalized"]["accuracy"]:.2f}% |' for k,r in held['results'].items())
    norm=read(ROOT/'normalization_proof/complete.json')
    text=f'''# 本轮模型改进结果（离线已完成，尚未上板）

新版识别器已训练、评测和编译完成，原有图像增强网络未改。当前JTAG扫描为全零，无法找到Zynq芯片；新ELF尚未下载，也没有新版实板速度或摄像头准确率结论。

## 已完成的改进

识别器为8/16通道两层卷积CNN，隐藏层从32扩大到128，共{freeze['parameters']}参数；三路使用同一对比度预处理。增加字体、手写数字、Chars74K真实字符和几何变化训练。训练/验证分开，官方评测图像不参与梯度训练，权重只按验证集选定。

这一轮改的是ARM数字识别器，FPGA PL仍运行原Multinex增强网络。不能把这些识别率变化写成图像增强网络本身的画质提升，也不能写成所有神经网络都部署在PL。

## 固定评测集结果

| 数据 | 数量 | 旧模型原输入 | 旧模型新预处理 | 新模型新预处理 |
|---|---:|---:|---:|---:|
{table}

前一个64隐藏单元候选场景字符109/120，没有达到110/120的预设门槛，已保留并拒绝上板。本轮128隐藏单元为112/120，通过原门槛。由于看过前一候选的汇总反馈，上表是固定评测集复测，不能说成一次新的盲测或无偏泛化估计；未按测试图个别错误训练，也未按测试结果挑训练轮次。

[Chars74K作者数据页](https://teodecampos.github.io/chars74k/)：引用de Campos、Babu、Varma，VISAPP2009。数据按原始场景分组，字体按家族分组；无跨分组的同一原始场景或完全相同数字裁剪。Windows字体文件不随包分发。

## 新实景照片暴露的不足（没有删掉失败）

预先选了8个公开门牌标题，其中5个在推理前遇到源站HTTP429，尚未获取；已下载的3张全部先标注数字区域，再统一测试。旧版对2/3，新版对1/3：蓝底白字6正确，石刻2和电线遮挡2被判为背景。原图、裁剪、分数、署名许可、下载失败记录见external_photo_check及原实验目录。

这些照片未参与拟合或挑选权重，结果没有用来修改裁剪或阈值。它们只覆盖2和6、且是人工区域裁剪，不代表任意实景识别率。新版在固定公开评测中总体更好，但**实景泛化仍未完成，不适合宣称任意数字、车牌或物体均可识别**。当前也未证明增强在真实暗光下普遍提高识别率。

## 计算与编译验证

新预处理C与NumPy共{norm['cases']}组/{norm['bytes']}字节完全一致；候选整数C与NumPy共{proof['cases']}组/{proof['logits']}个分类分数完全一致。各层做了绝对累加界限检查，安全时使用32位，其他保留64位。ARM ELF共{(BOARD/'camera.elf').stat().st_size}字节，编译通过并检查加载区域；bit与先前实板验证版本完全相同。

已重放三张旧门牌照片的既有实板缓冲：正常光RAW/NET/AUTO各对1/3，人工0.25和0.125亮度各对1/3，旧版这两档为0/3。它们是三张以前看过的照片，不是九个独立暗光场景，也不是新上板结果。实际新板卡计算、LCD显示、更新频率还要完成下一步核对。

## 准备上板

目录：E:/FPGA_Enhance_Work/multinex_camera_digit_upgrade_20261026

1. 开发板接独立电源，下载器两端接牢。改启动拨码前先关电；按此前JTAG方式将BOOT_CFG设为ON/ON后再上电。
2. 可双击download_jtag.cmd下载；也可由我在确认板卡在线后执行start_multinex_camera.tcl。前者使用电脑现有E:/Xilinx/Vitis/2020.2/bin/xsct.bat。
3. 下载后还需运行13个固定输入的实板测试、一个真实摄像头帧核对和连续更新频率测量；这些完成前不能把离线包称为实板验证完成版。

屏幕默认左原图、右保护结果；RAW/NET/AUTO为同一绿框内单数字识别，背景类显示“-”。不是自动找数字或车牌OCR。JTAG版本断电失效。

SD卡未修改，旧模型及旧恢复包未覆盖。模型SHA256：{freeze['sha256']}。
'''
    (ROOT/'本轮离线改进结果.md').write_text(text,encoding='utf-8');(BOARD/'本轮离线改进结果.md').write_text(text,encoding='utf-8')
    write(BOARD/'ready_for_board.json',dict(status='OFFLINE_ACCEPTED_ARM_COMPILED_WAITING_PHYSICAL_JTAG',model_sha256=freeze['sha256'],elf_sha256=sha(BOARD/'camera.elf'),bit_sha256=sha(BOARD/'camera.bit'),main_benchmark_accepted=True,fresh_photo_correct_new=1,fresh_photo_correct_old=2,fresh_photo_n=3,real_scene_reliability_established=False,new_board_programmed=False,new_board_verified=False,sd_written=False))
    files=sorted(p for p in BOARD.rglob('*') if p.is_file() and 'obj' not in p.relative_to(BOARD).parts and p.name not in ['ready_manifest.json','ready_release.json'])
    write(BOARD/'ready_manifest.json',[dict(path=p.relative_to(BOARD).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in files])
    archive=BASE/'multinex_recognition_upgrade_ready_v2_20261026.zip';assert not archive.exists()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in files+[BOARD/'ready_manifest.json']:z.write(p,p.relative_to(BOARD).as_posix())
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    write(BOARD/'ready_release.json',dict(archive=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,crc_ok=True,new_board_verified=False))
    print('OFFLINE_READY_PACKAGE',str(archive),sha(archive),flush=True)
if __name__=='__main__':main()
