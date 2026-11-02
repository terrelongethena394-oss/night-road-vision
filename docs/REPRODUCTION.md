# 原环境对应与复现说明
## 本次版本
ABI32主固件与工作台的五个入口模块均逐项核对2026-11-01 delivery_verified.json中的SHA256。build_verified.json是构建阶段记录，后续实际上板验收以board_verified.json、delivery_verified.json、released.json为准。
技术报告中的52.09% AP50、FP824来自ABI30阶段240张低亮度图像的离线对照；ABI32为自然增强和双输入界面验收版本。各版本不得混作一个新增精度结论。

## 原路径映射
- E:/FPGA_Enhance_Work/natural_exposure_guard_20261101_r1 对应 runtime_abi32
- E:/FPGA图像处理/程序 对应 host/photo_station（入口）和support/downstream（完整脚本集）
- E:/FPGA_Enhance_Work/road_car_roi_delivery_20261031_r1/board_candidate/firmware 对应 runtime_abi30/firmware
- E:/FPGA_Enhance_Work/photo_station_20261031/preferred_runtime.json 对应 host/preferred_runtime.json
- E:/FPGA_Enhance_Work/photo_ui_lib 对应 host/vendor
- E:/FPGA_Enhance_Work/photo_station_sd_20261031_r1 对应 sd_release
- 原standalone BSP的bspinclude/bsplib 对应 toolchain_support
工作台导入依赖从support/downstream提供；启动前将host/photo_station、support/downstream、host/vendor加入Python模块搜索路径，并配置原路径或在独立副本中统一改路径。不要只改界面入口而遗漏Tcl、偏好JSON和子模块路径。

## 环境
原工具为Vivado/Vitis/Vitis HLS 2020.2及Windows ARM交叉工具链；工作台使用Python、NumPy、Pillow和CustomTkinter，训练脚本还需要PyTorch等依赖。GUI原始启动脚本保留在host/start_original_environment.cmd。XSCT连接127.0.0.1:3121，硬件通路、DDR布局和XSA必须匹配。
runtime_abi32/build_verified.json保留实际编译和链接命令；固件source及obj、原BSP库随包提供。重编译须逐项调整命令路径并保留浮点选项，不能将构建脚本当作安全的一键重建器在旧验收目录直接运行。
hardware/system_road_conv_bd.tcl与project_sources提供BD和工程源，hardware/hls及ip提供HLS源码和导出IP；修正ip_repo_paths后在新目录重建。Xilinx工具自带IP由本机安装提供。
本轮只整理并校验快照，不重新构建硬件或运行JTAG。文件完整性脚本运行：python docs/verify_release.py。重建后仍需做对应协议的像素、框数据、程序指纹和LCD读回验证。
