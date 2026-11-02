"""Save reviewed evidence and local recovery/upgrade entries, without SD I/O."""
from pathlib import Path
import hashlib,json,shutil,sys,zipfile
from road_accuracy_common import *
HERE=Path(__file__).resolve().parent
WORK=Path('C:/Users/曹/Documents/ChatGPT/FPGA创新设计大赛')
APP=ROOT/'firmware'
LOW=BASE/'road_accuracy_lowlight_20261030_r1'
PY='E:\\FPGA_Enhance_Work\\nn_env312\\Scripts\\python.exe'

def stage():
    assert read(LOW/'result.json')['accepted']
    shutil.copy2(HERE/'road_accuracy_entry.py',ROOT/'road_accuracy_entry.py')
    for n in ['road_arm_common.py','road_adapt_common.py','road_numpy_eval.py','road_retinex_noiseguard.py','road_retinex_project.py','road_local_enhance_v2.py']:
        if (HERE/n).resolve()!=(ROOT/'source'/n).resolve():shutil.copy2(HERE/n,ROOT/'source'/n)
    for pattern in ['*road_accuracy*.py','road_vehicle_multiview.*','confirm_road_lowlight.py']:
        for p in HERE.glob(pattern):
            if p.resolve()!=(ROOT/'source'/p.name).resolve():shutil.copy2(p,ROOT/'source'/p.name)
    # Keep obsolete displays as history, including the visually daytime image.
    history=ROOT/'examples/history';history.mkdir(exist_ok=True)
    for n in ['03_b8c60cba-d52cfc92.png','03_b9117002-f2ff0c31.png']:
        src=ROOT/'examples'/n;dst=history/n
        assert src.resolve().is_relative_to(ROOT.resolve()) and dst.resolve().is_relative_to(ROOT.resolve())
        if src.exists() and not dst.exists():src.rename(dst)
    commands={
        '01_verify_all_and_start.cmd':[str(ROOT/'source/run_road_accuracy_upgrade.py')],
        '02_start_verified_demo.cmd':[str(ROOT/'road_accuracy_entry.py'),'start','5'],
        '03_show_first_night.cmd':[str(ROOT/'road_accuracy_entry.py'),'show','1'],
        '04_show_second_night.cmd':[str(ROOT/'road_accuracy_entry.py'),'show','2'],
        '05_show_dusk_labelled.cmd':[str(ROOT/'road_accuracy_entry.py'),'show','3'],
        '06_show_day_labelled.cmd':[str(ROOT/'road_accuracy_entry.py'),'show','4'],
        '07_show_dark_success.cmd':[str(ROOT/'road_accuracy_entry.py'),'show','5'],
        '08_show_black_control.cmd':[str(ROOT/'road_accuracy_entry.py'),'show','6'],
        '00_restore_previous_fixed.cmd':[str(BASE/'road_retinex_noiseguard_arm_20261029_r1/retinex_fixed_entry.py'),'start','1','full'],
        '00_restore_camera.cmd':[str(BASE/'road_conv13_p16_runtime_20261028_r1/firmware/user_start.py')],
    }
    for name,args in commands.items():
        line='@echo off\r\n"'+PY+'" '+' '.join('"'+v+'"' for v in args)+'\r\nset "task_exit=%errorlevel%"\r\npause\r\nexit /b %task_exit%\r\n'
        (ROOT/name).write_text(line,encoding='ascii',newline='')
    for root in [DATA/'assets',DATA/'yolov5']:
        names=['BDD_DATA_LICENSE.txt'] if root.name=='assets' else ['LICENSE']
        for n in names:
            if (root/n).exists():shutil.copy2(root/n,ROOT/('BDD_DATA_LICENSE.txt' if root.name=='assets' else 'YOLOv5_LICENSE'))
    board=(ROOT/'board_verified.json').exists()
    state='已取得实板验收收据。' if board else '尚未完成实板验收：当前JTAG未识别芯片，程序只完成编译和电脑端验证。'
    restart='本机已经完成完整验收。以后断电重新运行可直接执行02_start_verified_demo.cmd；03–08切图。只有重新做完整验收才需要01。' if board else '首次上板需先执行01_verify_all_and_start.cmd；通过后才能使用快捷启动和切图入口。'
    text=f'''# ABI23 固定图片识别实验使用说明

{state}

{restart}

目录：`{ROOT.as_posix()}`。

1. 开发板独立供电，保持摄像头、屏幕和JTAG下载器连接，使用此前验证过的JTAG启动配置。
2. 首次使用执行 `01_verify_all_and_start.cmd`。它先下载旧ABI22，取得相同输入的实际ARM/FPGA神经网络输出；再下载ABI23核对四路输出、融合框和屏幕帧。失败则尝试恢复原固定图片版。需要数分钟，不能只看进程退出码判断成功，要看到 `ROAD_ACCURACY_UPGRADE_DONE`。
3. 全部通过后，可用 `02_start_verified_demo.cmd` 直接启动。03–08切换固定图片，07是事后挑选的暗光说明例，08是纯黑对照。没有实板验收收据时，快捷启动入口会拒绝运行，需先执行01。
4. `00_restore_previous_fixed.cmd` 恢复原ABI22固定图；`00_restore_camera.cmd` 恢复原ABI18摄像头。

固定图左侧：原图＋单次原图检测框。右侧：增强显示＋四次原图检测融合框。增强没有作为检测输入，右侧新增框不能归功于提亮。截图上的框数是预测数，不是正确目标数；正确率证据见《识别改进与验证报告.md》。移动手掌不会改变固定图片。

本轮没有重新训练检测网络。PC先生成800×480代理图、400×240全景及三个局部输入，通过JTAG上传；板上实际执行四次网络前向、框融合和增强显示。PL复用已验证的16路卷积核，ARM负责其余网络算子、调度、融合、传统Retinex增强及界面。还没有把三窗口采样接入实时摄像头流程；ABI23多视图模式只支持固定图片。

不会写SD卡或Flash。本版断电后需重新JTAG启动。依赖本机E盘Python、Xilinx 2020.2、旧版恢复目录及当前工作区源码路径，并非可直接搬到其他电脑的独立软件。

暗光确认使用另行预留的320张原图平均Y<=48图片，不能把该阈值解释为环境照度lux。源数据night标签中发现了实际白天图，旧展示图已移至examples/history，未用于最终暗光展示。完整原始JPEG仍留在本机数据目录；备份包不重复包含大批JPEG，保留标注、SHA、预测和协议用于追溯。
'''
    (ROOT/'如何启动与恢复.md').write_text(text,encoding='utf-8')
    write(WORK/'当前识别候选_20261030.json',dict(status='BOARD_VERIFIED_ABI23' if board else 'OFFLINE_LOWLIGHT_ACCEPTED_ABI23_COMPILED_AWAITING_CONNECTION',directory=str(ROOT),lowlight_confirmation=str(LOW/'result.json'),board_verified=board,enhancement_gain_proven=False,network_retrained=False,detector_passes=4,sd_written=False,formal_camera_fallback=str(BASE/'road_conv13_p16_runtime_20261028_r1/firmware')))
    (WORK/'当前项目检查点_识别提升_20261030.md').write_text('# 2026-10-30 识别改进检查点\n\n'+state+'\n\n'+restart+'\n\n已完成320张独立低亮度C验证：汽车AP@0.5 39.63%→44.54%，99%差值区间+3.86～+5.96个百分点。提升来自保留细节、多视图检测，未证明增强改善识别。\n\n工程：'+str(ROOT)+'\n\nSD未改，旧ABI22和ABI18保留。\n',encoding='utf-8')
    print('ACCURACY_LOCAL_ENTRIES_STAGED',state,flush=True)

def archive():
    stage()
    verified=(ROOT/'board_verified.json').exists();tag='board_verified' if verified else 'offline_ready'
    target=BASE/f'road_accuracy_ABI23_{tag}_20261030.zip'
    assert not target.exists()
    files=[];allowed={c['name'] for c in read(APP/'cases.json')}
    for root in [ROOT,LOW]:
        for p in root.rglob('*'):
            if not p.is_file():continue
            parts=p.relative_to(root).parts
            if 'obj' in parts or 'scratch' in parts or '__pycache__' in parts:continue
            if parts[:2]==('fresh','images') or parts[:2]==('development','views'):continue
            if root==ROOT and parts[:3]==('firmware','runtime','cases') and len(parts)>3 and parts[3] not in allowed:continue
            if p.name in ['package_manifest.json']:continue
            files.append((p,root.name+'/'+p.relative_to(root).as_posix()))
    manifest={name:sha(p) for p,name in files};write(ROOT/'package_manifest.json',manifest)
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p,name in files:z.write(p,name)
        z.write(ROOT/'package_manifest.json',ROOT.name+'/package_manifest.json')
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        for name,digest in manifest.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
    write(BASE/f'road_accuracy_ABI23_{tag}_package_20261030.json',dict(path=str(target),bytes=target.stat().st_size,sha256=sha(target),crc_and_all_included_file_hashes_verified=True,board_verified=verified,sd_written=False))
    print('ACCURACY_ARCHIVE_VERIFIED',target,sha(target),flush=True)

if __name__=='__main__':{'stage':stage,'archive':archive}[sys.argv[1]]()
