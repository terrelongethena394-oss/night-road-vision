# 暗路明察 技术报告同版代码

## GitHub 下载说明
本仓库与技术报告对应的源代码保持一致。三个较大的已验收编译产物（ABI32 ELF、ABI30 BOOT.BIN及SD ELF）放在 [Release](https://github.com/terrelongethena394-oss/night-road-vision/releases/tag/report-abi32-20261101) 中，下载地址和SHA256见 docs/published_artifacts.json。
克隆或下载源码后，先运行 python docs/restore_release_artifacts.py 恢复这三个文件，再运行 python docs/verify_release.py 检查完整快照。也可按JSON清单手动下载并放回相应路径。
原本地RAR代码包的完整性清单另存于 docs/local_release_manifest.json；GitHub版本仅增加下载说明及清单，算法、模型与GUI运行源码未改动。

本地整理日期：2026-11-02。主运行版本 ABI32，自然增强与照片/摄像头工作台；SD 独立演示版本 ABI30。与2026-11-01实物完善版及中英文文献补充版技术报告一致。

## 目录
- runtime_abi32：本次主运行快照。ARM C 源码、411参数学生网络权重、自然亮度约束、固件 ELF、BIT/XSA、链接对象及四场景/摄像头验收记录。
- host/photo_station：与ABI32交付指纹一致的桌面界面、照片传输、摄像头预览和抓拍模块。
- support/downstream：训练、导出、主机C参考、构建、验证等项目脚本；其中实验候选用于研究复核，不代表当前默认运行版本。
- runtime_abi30：前期区域核验基线及模型导出、原始权重，用于报告离线对照及底层通信支持。
- sd_release：已验证的 ABI30 独立启动源码、BOOT.BIN、ELF和启动资料；不将ABI32冒称为SD启动版。
- hardware：16路 FP32 HLS 卷积核、导出IP、板级视频IP、Vivado工程源/BD/XDC、资源与时序报告。
- toolchain_support：原编译环境 standalone BSP 的头文件和库。
- host/vendor：原界面使用的CustomTkinter及其依赖，第三方授权原样保留。
- docs：环境映射、构建说明、版本对照及文件完整性校验脚本。

入口：host/photo_station/photo_station_gui.py。其原始路径常量和硬件通信逻辑保持不变。请先阅读 docs/REPRODUCTION.md；该代码包是原环境快照，不是自动安装包。未访问或改写开发板、SD或Flash，未公开上传。

发布主固件：runtime_abi32/firmware/road_detail.elf
SHA256：dae88aea72b3838fedd5147805f6f1060f8122bfaf156f662ff99d8833a49c80

运行源码保持原样，含真实类别定义和模型输出处理；演示视频中的文字剪辑不会改变代码或类别。Python入口、训练代码和硬件源码各有环境依赖，见说明。模型训练原始数据集和商业Xilinx工具未打入代码包。
