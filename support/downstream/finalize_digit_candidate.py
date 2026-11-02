"""Gate and archive a new, NOT physically verified, volatile-JTAG candidate."""
from pathlib import Path
import csv
import hashlib
import json
import re
import shutil
import struct
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=Path('E:/FPGA_Enhance_Work/digit_recognition_20261023')
BUILD=Path('E:/FPGA_Enhance_Work/camera_nn_digit_20261023')
OLD=Path('E:/FPGA_Enhance_Work/camera_nn8_verified_20261023')
PACKAGE=Path('E:/FPGA_Enhance_Work/camera_nn_digit_candidate_20261023')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    log=(BUILD/'build_board.log').read_text(encoding='utf-8',errors='replace')
    timing=re.search(r'DIGIT_BOARD_BUILD_PASS WNS=([-\d.]+) WHS=([-\d.]+)',log)
    assert timing and min(map(float,timing.groups()))>=0,'Require successful routed candidate'
    dsps={k:int(n) for k,n in re.findall(r'^NEURAL_CORE_DSP (\S+) (\d+)\s*$',log,re.M)}
    assert set(dsps)=={'nanodce8_full_0','raw_digit_0','enhanced_digit_0'} and min(dsps.values())>0
    bus=(BUILD/'bus_skew.rpt').read_text(encoding='ascii')
    section=bus.rsplit('1. Bus Skew Report Summary',1)[-1].split('2. Bus Skew Report Per Constraint',1)[0]
    slack=[float(v) for v in re.findall(r'^\s*(?:Slow|Fast)\s+[-\d.]+\s+[-\d.]+\s+([-\d.]+)\s*$',section,re.M)]
    assert len(slack)==5 and min(slack)>=0
    assert json.loads((BUILD/'integration_audit.json').read_text(encoding='utf-8'))['status']=='PASS'
    assert 'DIGIT_RTL_COSIM_PASS' in (ROOT/'hls/cosim.log').read_text(encoding='utf-8',errors='replace')
    assert 'DIGIT_INTEGER_PIXEL_MATCH_PASS frames=6 pixels=545946' in (ROOT/'hls/cosim.log').read_text(encoding='utf-8',errors='replace')
    assert 'DIGIT_STREAM_AUTORESTART_BACKPRESSURE_RESET_PASS frames=5 pixels=123339' in (ROOT/'rtl_stream/simulate.log').read_text(encoding='utf-8',errors='replace')
    assert 'DIGIT_ARM_BUILD_PASS' in (BUILD/'build_app.log').read_text(encoding='utf-8',errors='replace')
    # Exact generated driver offsets must match the ARM definitions.
    registers=json.loads((BUILD/'digit_register_map.json').read_text(encoding='utf-8'))
    header=ROOT/'hls/digit_project/solution_100mhz/impl/ip/drivers/digit_monitor_v1_0/src/xdigit_monitor_hw.h'
    parsed={n:int(v,16) for n,v in re.findall(r'#define\s+XDIGIT_MONITOR_CONTROL_ADDR_(\w+)_DATA\s+(0x[0-9a-fA-F]+)',header.read_text(encoding='ascii'))}
    for name,value in registers.items():
        assert parsed[name]==value
        assert f'#define DIGIT_REG_{name} 0x{value:X}U' in (BUILD/'app_src/digit_regs.h').read_text(encoding='ascii')
    with zipfile.ZipFile(BUILD/'camera_digit.xsa') as z:
        assert z.testzip() is None
        ps=[n for n in z.namelist() if Path(n).name=='ps7_init.tcl'];assert len(ps)==1
        data=z.read(ps[0]);assert data==(OLD/'ps7_init.tcl').read_bytes()
        (BUILD/'ps7_init.tcl').write_bytes(data)
        bits=[n for n in z.namelist() if n.endswith('.bit')];assert len(bits)==1
        assert z.read(bits[0])==(BUILD/'system_wrapper.bit').read_bytes()
    assert sha(BUILD/'system_wrapper.bit')!=sha(OLD/'system_wrapper.bit')
    assert sha(BUILD/'camera_app.elf')!=sha(OLD/'camera_app.elf')
    assert sha(BUILD/'rtl/axis_rgb_bridge.v')==sha(Path('E:/FPGA_Enhance_Work/camera_nn8_20261023/rtl/axis_rgb_bridge.v'))
    # ELF32 load regions, including zero-initialized heap/stack, must precede video buffers.
    elf=(BUILD/'camera_app.elf').read_bytes()
    assert elf[:6]==b'\x7fELF\x01\x01'
    entry,phoff=struct.unpack_from('<II',elf,24)
    phsize,phnum=struct.unpack_from('<HH',elf,42)
    regions=[]
    for i in range(phnum):
        kind,offset,vaddr,paddr,filesz,memsz,flags,align=struct.unpack_from('<8I',elf,phoff+i*phsize)
        if kind==1 and memsz:
            assert paddr>=0x100000 and paddr+memsz<=0x01100000,(hex(paddr),hex(memsz))
            regions.append(dict(start=hex(paddr),end_exclusive=hex(paddr+memsz)))
    assert regions and entry==0x100000
    util=(BUILD/'utilization.rpt').read_text(encoding='ascii')
    def resource(name):
        m=re.search(r'\|\s*'+re.escape(name)+r'\s*\|\s*([\d.,]+)',util);assert m,name
        return float(m[1].replace(',',''))
    resources={n:resource(n) for n in ['Slice LUTs','Slice Registers','Block RAM Tile','DSPs']}
    assert resources['DSPs']==sum(dsps.values())
    drc=(BUILD/'drc.rpt').read_text(encoding='ascii')
    rows=re.findall(r'^\|\s*(\S+)\s*\|\s*(Warning|Advisory|Error|Critical Warning)\s*\|',drc,re.M)
    assert rows and all(severity in ('Warning','Advisory') for _,severity in rows)
    for name,limit in [('Slice LUTs',53200),('Slice Registers',106400),('Block RAM Tile',140),('DSPs',220)]:
        assert 0<resources[name]<=limit
    # Preserve the previously observed successful NN8 build and original SD boot file.
    assert sha(OLD/'system_wrapper.bit')=='18d510023d6968cd5821dc67ba6a971593751931c199e862dfd93853136145d9'
    assert sha(OLD/'camera_app.elf')=='06ded76e5c2a859f732e2fb3995240f2217fb2edda897663ef1e99d6c3ccb2d1'
    assert sha(Path('E:/FPGA_Enhance_Work/camera_nn_sd_20261018/BOOT.BIN'))=='e0d606c4c623463e01e6b4123ad127a63d0103c046674514bec01891e9ad67d3'
    training=json.loads((ROOT/'training_validation.json').read_text(encoding='utf-8'))
    evaluation=json.loads((ROOT/'downstream_evaluation/results.json').read_text(encoding='utf-8'))
    assert training['status']=='PASS' and training['parameters']==25483
    assert training['recognizer_sha256']==evaluation['recognizer_sha256']==sha(ROOT/'digit_model.pth')
    assert len(evaluation['records'])==180*6
    status=dict(date='2026-10-23',stage='BUILT_AND_SIMULATED_NOT_DOWNLOADED',
        board='XC7Z020CLG400-2 / V3.9 / OV5640 / LCD800x480',enhancer='NanoDCE8-Cal',
        digit_recognizer='trained 784->32ReLU->11 MLP; 25483 parameters; same weights in both PL cores',
        roi=dict(x=480,y=112,width=224,height=224),result_register_offsets=registers,
        routed_resources=resources,neural_hierarchy_dsps=dsps,WNS_ns=float(timing[1]),WHS_ns=float(timing[2]),
        bus_skew_min_slack_ns=min(slack),core_clock_mhz=100,
        drc_summary=[dict(rule=rule,severity=severity) for rule,severity in rows],
        c_rtl_cosim=dict(frames=6,pixels=545946),native_rtl=dict(frames=5,pixels=123339,auto_restart=True,random_backpressure=True,reset=True),
        elf_entry=hex(entry),elf_load_regions=regions,ps7_init_byte_identical_to_verified_NN8=True,
        clean_offline_recognition=training['clean_test'],old_recovery_files_hash_checked_unchanged=True,
        sd_written=False,hardware_contacted=False,physical_validation='PENDING',real_camera_accuracy='NOT_MEASURED',
        real_fps='NOT_MEASURED',latency='NOT_MEASURED',power='NOT_MEASURED',
        constraints_note='Inherited official PCLK dedicated-route exception and incomplete external I/O timing constraints remain; no DRC severity downgrade.',
        limitations=['Fixed ROI single centered white digit on black, not full plate OCR.',
                     'Synthetic darkening coefficients are not lux or camera exposure.',
                     'Normal-light regression and Gamma wins are retained in the full benchmark.',
                     'Physical camera, color, stability, performance and accuracy remain unverified.'])
    shutil.copy2(HERE/'download_digit_jtag.tcl',BUILD/'download_digit_jtag.tcl')
    names=['system_wrapper.bit','camera_app.elf','camera_digit.xsa','ps7_init.tcl','download_digit_jtag.tcl']
    status['artifact_sha256']={n:sha(BUILD/n) for n in names}
    (BUILD/'build_status.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
    assert not PACKAGE.exists(),'Preserve any existing candidate package'
    PACKAGE.mkdir()
    for name in names+['build_status.json','integration_audit.json','digit_register_map.json','windows_driver_fix.json']:
        shutil.copy2(BUILD/name,PACKAGE/name)
    shutil.copytree(OLD/'notices',PACKAGE/'notices')
    shutil.copytree(ROOT/'demo_targets',PACKAGE/'demo_targets')
    shutil.copytree(BUILD/'app_src',PACKAGE/'sources/app_src')
    shutil.copytree(HERE,PACKAGE/'sources/downstream',ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(BUILD/'system_digit_bd.tcl',PACKAGE/'sources/system_digit_bd.tcl')
    shutil.copy2(BUILD/'rtl/axis_rgb_bridge.v',PACKAGE/'sources/axis_rgb_bridge.v')
    for source,name in [(ROOT/'hls/digit_project/solution_100mhz/impl/ip','digit_monitor'),
                         (Path('E:/FPGA_Enhance_Work/model_upgrade_20261023/hls8/full_network_project/solution_100mhz/impl/ip'),'nanodce8_full')]:
        shutil.copytree(source,PACKAGE/'ip'/name,ignore=shutil.ignore_patterns('*.log','*.jou','.Xil'))
    for name in ['digit_model.pth','digit_weights_integer.npz','training_validation.json','mnist_manifest.json','downstream_test_inputs.npz']:
        (PACKAGE/'model').mkdir(exist_ok=True)
        shutil.copy2(ROOT/name,PACKAGE/'model'/name)
    shutil.copy2(ROOT/'hls/digit_weights.h',PACKAGE/'sources/digit_weights.h')
    shutil.copytree(ROOT/'downstream_evaluation',PACKAGE/'evaluation')
    evidence=PACKAGE/'evidence';evidence.mkdir()
    for name in ['build_board.log','build_app.log','timing_summary.rpt','bus_skew.rpt','utilization.rpt','utilization_hierarchy.rpt','drc.rpt']:
        shutil.copy2(BUILD/name,evidence/name)
    for source,name in [(ROOT/'hls/cosim.log','digit_c_rtl_cosim.log'),(ROOT/'rtl_stream/simulate.log','digit_stream_rtl.log'),
                         (ROOT/'training.log','training.log'),(ROOT/'hls/build.log','digit_hls_build.log')]:
        shutil.copy2(source,evidence/name)
    shutil.copytree(ROOT/'rtl_stream',PACKAGE/'sources/rtl_stream',ignore=shutil.ignore_patterns('xsim.dir','*.log','*.jou','*.wdb','*.pb','*.mem'))
    shutil.copy2(ROOT/'hls/cases.json',evidence/'digit_cases.json')
    shutil.copy2(HERE/'验证与展示说明.md',PACKAGE/'验证与展示说明.md')
    table='| 合成亮度系数 | 原图 | Gamma 0.5 | 旧增强 | NN8-Cal |\n|---|---:|---:|---:|---:|\n'
    for row in evaluation['summary']:
        table+='| '+f'{row["alpha"]:g}'+' | '+' | '.join(f'{row["methods"][m]["accuracy"]*100:.2f}%' for m in ['raw','gamma05','old_nn','new_nn'])+' |\n'
    metrics='''# 离线数字识别对比（固定识别器）

每个亮度160个数字：120个未见字体样本+40个MNIST测试样本。另有20个空背景控制样本。所有输入先加同一噪声并截成RGB565精度，再分别处理；两路使用同一份冻结识别权重。完整1080条结果见results.json，不筛掉失败样本。

亮度系数是在编码RGB上乘系数的合成测试，不是实际lux、曝光时间或摄像头实测。

'''+table+'''
正常亮度下NN8-Cal低于原图，部分亮度Gamma更好；极暗合成输入下NN8-Cal在本小样本中更高。该结果仅支持继续实物验证，不证明普遍优于Gamma，更不证明完整车牌识别提升。20个空背景测试中本次未见误报，不能据此宣称任意背景都无误报。
'''
    (PACKAGE/'evaluation/结果说明.md').write_text(metrics,encoding='utf-8')
    with (PACKAGE/'实物验证记录.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['样本编号','真值0-9或blank','照明设置','照度lux可空','曝光增益状态','距离与角度','RAW结果','ENH结果','RAW是否正确','ENH是否正确','串口帧号','备注'])
        for light in ['正常','较暗','很暗']:
            for repeat in range(2):
                for digit in range(10):writer.writerow([f'{light}-{repeat+1}-{digit}',digit,light,'','当前默认自动曝光，正式测试需记录','','','','','','',''])
    readme=f'''# 图像增强 + 同区域数字识别 JTAG 候选版

2026-10-23，已编译、仿真，尚未下载到开发板；SD卡未改。面向7020/V3.9/OV5640/800×480屏。

新增实际训练的单数字MLP，25,483参数。增强前后两个识别器都在PL，使用相同权重、同一ROI、同帧结果匹配。原有NanoDCE8-Cal增强仍在PL。ARM仅负责初始化、控制和结果配对。首版只识别黑底白色、居中的单个0–9，不能做完整车牌定位/中文OCR。

## 编译结果

实际整板资源：LUT {resources['Slice LUTs']:g}，FF {resources['Slice Registers']:g}，BRAM36等效 {resources['Block RAM Tile']:g}，DSP {resources['DSPs']:g}/220。100 MHz约束，WNS {float(timing[1]):.3f} ns，WHS {float(timing[2]):.3f} ns，5项总线偏斜检查最小余量 {min(slack):.3f} ns。继承的外部接口约束限制见build_status.json。

C/RTL 6帧545,946像素通过；连续流RTL 5帧123,339像素，随机背压、自动重启、复位及原子帧号结果通过。板上颜色、稳定性、准确率、帧率、延迟、功耗均待验证。

## 回来后才执行的临时下载

板卡断电时设置BOOT_CFG两位ON/ON，接JTAG、摄像头和屏幕，再上电。在PowerShell运行：

```powershell
& 'E:\\Xilinx\\Vitis\\2020.2\\bin\\xsct.bat' 'E:\\FPGA_Enhance_Work\\camera_nn_digit_candidate_20261023\\download_digit_jtag.tcl'
```

此脚本只写易失FPGA配置及ARM内存，不写SD/QSPI/eMMC；本次没有执行。下载后先确认实时图像和红蓝颜色，再把demo_targets中的单数字对准右侧绿色框。RAW/ENH都指同一个框的增强前/后识别，`-`表示blank或初始无结果；不是两个不同物体。标签是已完成帧结果，存在显示滞后。

详细操作和指标见《验证与展示说明.md》，合成测试完整结果见evaluation。MNIST离线准确率95.46%不是板卡准确率。增强在正常亮度也有退步，Gamma在部分条件更好，完整对比已保留。

## 恢复到此前已确认有画面的NN8

```powershell
& 'E:\\Xilinx\\Vitis\\2020.2\\bin\\xsct.bat' 'E:\\FPGA_Enhance_Work\\camera_nn8_verified_20261023\\download_nn_jtag.tcl'
```

此前NN8和旧SD用BOOT.BIN的电脑原文件均通过哈希核对，未改动。JTAG新版断电丢失，SD仍保留原有内容；SD冷启动是否成功需实际验证。

sources保存本次源码、app_src、BD导出及测试准备脚本，ip包含两个HLS核，model保存训练权重和元数据，evidence保存编译/仿真报告。脚本仍引用本机已存在的原厂工程和ASCII工作目录，不是通用一键移植工程。源码不包含Windows字体或原始MNIST数据；重新运行训练会校验下载数据。
'''
    (PACKAGE/'README_zh.md').write_text(readme,encoding='utf-8')
    manifest={p.relative_to(PACKAGE).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in PACKAGE.rglob('*') if p.is_file()}
    (PACKAGE/'artifact_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    archive=PACKAGE.with_suffix('.zip');assert not archive.exists()
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in PACKAGE.rglob('*'):
            if p.is_file():z.write(p,arcname=p.relative_to(PACKAGE))
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    print('DIGIT_CANDIDATE_PREFLIGHT_AND_PACKAGE_PASS',json.dumps(resources),'zip_bytes',archive.stat().st_size,flush=True)

if __name__=='__main__':main()
