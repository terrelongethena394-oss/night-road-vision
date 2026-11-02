# 当前状态：新版已上板，计算/显示/速度核对完成

## 2026-10-26恢复连接后的最终结果

用户确认已上电并连接后，成功识别APU/xc7z020，新版下载启动。当前恢复并运行实时摄像头；SD未写，旧模型未覆盖。

- 13个固定输入及一个真实摄像头帧：32928灰度字节、462个分类分数全部精确；增强/保护/LCD图像/显示数字均通过独立核对。摄像头帧也核对实际采集缓冲及2×2降采样。
- 连续10.351秒完成78次更新，7.535503816次/秒，DMA错误0。不是镜头到屏幕延迟测量。
- 本次live截图绿框内没有清晰数字，却输出5，拒识仍不可靠。不要把实际整数算对等同识别正确；仍保留新增三张门牌旧2/3、新1/3的失败事实。
- 新实板包：E:/FPGA_Enhance_Work/multinex_recognition_upgrade_verified_20261026.zip，SHA256 00a9bfb662f5b7749c429fef520824293a9bbad86505880bdbd85e1760bf10be，CRC通过。
- 当前报告：E:/FPGA_Enhance_Work/multinex_camera_digit_upgrade_20261026/本轮模型改进与实板验证.md；同文也在recognition_upgrade_20261026实验目录。
- 状态：待下载目录board_deployed.json=UPGRADED_RECOGNIZER_OFFLINE_ACCEPTED_AND_BOARD_NUMERICALLY_VERIFIED；ready_for_board.json标记为上板前历史。
- run03固定模型SHA保持75b88f...；FPGA增强bit保持原r4d，ARM识别器128隐藏单元。

下面保留首次成功下载前的历史与操作入口。原JTAG阻断已解决，原“恢复连接后”核对步骤均已完成；不要无理由重复训练或测试。

## 首次成功下载前的记录

用户要求持续自主改进，完善后再上板；保留旧版，禁止写SD。不要重复训练或降低已设置的验收门槛。

## 已固定的候选

- 实验：E:/FPGA_Enhance_Work/recognition_upgrade_20261026/run03
- 模型：best_eligible.pth，SHA256 75b88fdadfb35338a30c60a65ae0a895a162c0f6d394af006a46378994378c7b。
- CNN通道8/16，隐藏128，共103147参数；对比度预处理合同v2。ARM做识别，FPGA增强核未改。
- 固定评测：SVHN22948/26032=88.15%（旧22170=85.16%）；Chars112/120=93.33%（旧104）；字体1963/2000；MNIST9763/10000；背景1000/1000。原先五个门槛全部通过。
- 评测集已经经历迭代，不称为新的盲测；未用于梯度或训练轮次挑选。
- run01失败；run02字符109/120未达门槛拒绝部署；都保留。
- 新照片三张（预选8张中5个HTTP429），旧2/3，新1/3。石刻2、遮挡2仍失败。全部错误和署名保留，不要隐藏或据此调测试裁剪/阈值。
- 三张旧门牌回归正常光三路各1/3；人工暗化0.25/0.125每档三路各1/3（旧两档全0）。只有三个原始场景，不证明一般增强收益。
- C/NumPy新预处理2256组1768704字节完全一致；整数分类146组1606分数全一致。新权重绝对前缀累加界限conv1/conv2/fc1安全32位，fc2保持64位。

## 编译及待下载目录

E:/FPGA_Enhance_Work/multinex_camera_digit_upgrade_20261026

camera.elf806764字节，编译/加载区/权重/bit散列检查通过。bit保持先前r4d实板验证版本。下载脚本、13个固定测试输入、snapshot、cadence、验证器均已放入此目录。SD未写。

最新待上板包：E:/FPGA_Enhance_Work/multinex_recognition_upgrade_ready_v2_20261026.zip，SHA256 0397709417e1ce103d0e63e06a8643b2c27c275a64d07a175666da3a620ca689。

同名不带v2的早期包已被替代，下载入口对XSCT错误码的处理不完整，不推荐使用。当前目录download_jtag.cmd已经修正：按新的随机日志中的MULTINEX_CAMERA_STARTED判定成功。XSCT2020.2即使Tcl exit1也可能返回Windows进程0，不能只看退出码。wrapper_negative_control.cmd已证明失败不会被误报成功。

详细报告：E:/FPGA_Enhance_Work/recognition_upgrade_20261026/本轮离线改进结果.md

## 硬件阻断（不是许可阻断）

2026-10-26约14:03下载尝试，日志deploy.log：whole scan chain (DR shift through all zeroes)，没有APU，尚未reset/fpga/dow任何新版内容。USB Serial Converter VID0403/PID6014/210512180081状态OK；没有残留hw_server/xsct/python进程。需要开发板独立电源、JTAG板端接牢、JTAG启动ON/ON。

已向用户发出异步硬件状态问题，截至整理此文件时未收到回复。用户此前允许上板，本次只缺物理在线状态，不再要求额外批准。没有自动化、后台监控或goal。

## 恢复连接后连续完成（不要又停下让用户喊继续）

1. 用E:/Xilinx/Vitis/2020.2/bin/xsct.bat执行待下载目录中的run_checked.tcl和start_multinex_camera.tcl。必须读日志中MULTINEX_CAMERA_STARTED，退出0不可靠。
2. XSCT执行test_digit_camera.tcl，产生board_digit十三组；逐组用当前目录validate_digit_camera.py验证，确保输入合同2、全部灰度/33分数精确、增强/保护/LCD像素/数字字形精确。不能使用旧目录的模型验证器。SOURCE指向当前工作区starter/downstream。
3. XSCT执行snapshot_multinex_camera.tcl并传入新的live_snapshot目录；验证其真实camera capture、三路分类及显示。测试后需恢复实时画面。
4. XSCT执行measure_multinex_camera.tcl，产生11行live_cadence.csv；约10秒零DMA错误，预设至少6.5次完成显示更新/秒，不称为镜头到屏幕延迟或传感器FPS。
5. 执行工作区starter/downstream/finish_upgrade_camera.py。它要求上述全部实板证据、保留新照片失败，并归档verified包；不得在硬件证据缺失时绕过断言。
6. 若USB故障，先针对自己启动的进程做有限恢复；不要盲杀用户所有Vivado进程。仍全零则需要用户物理处理。

还没有新版实板准确率、速度或摄像头画质结论。当前只能称为离线评测改进版，不能称为完善的任意实景/车牌识别系统。


## 上板后拒识检查

已运行calibrate_digit_rejection.py，实验E:/FPGA_Enhance_Work/rejection_calibration_20261026。仅验证数据选阈值；在各正样本组保留至少95%原本正确数字时，最佳logit差门限0.5，使加权负样本误接受相对下降23.35%，但原live误报三路仍全部接受。deployment_decision.json明确DO_NOT_DEPLOY；板上程序未改。下一步需补真实非数字场景与正常/暗光配对验证，不能只把置信度门限调到足以拒绝这一个已知错误。
