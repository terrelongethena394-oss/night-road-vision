"""Collect current model sources and weights without altering deployed artifacts."""
from pathlib import Path
import hashlib,json,shutil,zipfile
HERE=Path(__file__).resolve().parent
BASE=Path('E:/FPGA_Enhance_Work')
BOARD=BASE/'camera_plate_guarded_20261026'
OUT=HERE.parents[1]/'当前模型代码_20261026'
def main():
    OUT.mkdir(exist_ok=False)
    py=OUT/'01_车牌模型与训练';py.mkdir()
    for name in ['tiny_plate_model.py','plate_common.py','train_tiny_plate.py','tiny_plate_integer.py','evaluate_tiny_plate.py','prepare_plate_training_data.py','plate_native_host.c','plate_native_kernel.h']:
        shutil.copy2(HERE/name,py/name)
    shutil.copytree(BOARD/'app_src',OUT/'02_板上车牌识别与应用')
    model=OUT/'03_权重与验证记录';model.mkdir()
    for name in ['plate_model.pth','plate_integer_weights.npz','plate_frozen.json','plate_numeric_proof.json','plate_offline_results.json','board_deployed.json','consistency_policy.json','车牌训练与实板验证.md']:
        shutil.copy2(BOARD/name,model/name)
    shutil.copy2(BASE/'license_plate_20261026/tiny_student01/protocol.json',model/'training_protocol.json')
    pl=OUT/'04_FPGA图像增强_HLS';pl.mkdir()
    hls=BASE/'multinex_hls_r4d_20261026'
    for p in hls.iterdir():
        if p.is_file() and (p.suffix in ['.cpp','.h'] or p.name in ['architecture.json','LICENSE','MODEL_CARD.md','NOTICE','THIRD_PARTY_NOTICES.md']):shutil.copy2(p,pl/p.name)
    shutil.copy2(BASE/'multinex_fixed_w18_20261025/fixed_multinex.py',pl/'fixed_multinex.py')
    shutil.copy2(BASE/'multinex_fixed_w18_20261025/upstream_reference/MultinexNano_arch.py',pl/'上游MultinexNano_arch.py')
    licenses=OUT/'开源许可';licenses.mkdir()
    for name in ['LPRNET_LICENSE.txt','FONT_LICENSE.txt','LICENSE','NOTICE','THIRD_PARTY_NOTICES.md']:
        shutil.copy2(BOARD/name,licenses/name)
    (py/'inspect_model.py').write_text('''from pathlib import Path
import torch
from tiny_plate_model import TinyPlate
root=Path(__file__).resolve().parent.parent
torch.set_num_threads(4)
model=TinyPlate().eval()
model.load_state_dict(torch.load(root/'03_权重与验证记录/plate_model.pth',map_location='cpu',weights_only=True))
with torch.inference_mode():
    y=model(torch.zeros(1,1,32,96))
assert tuple(y.shape)==(1,68,24)
print(model)
print('parameters:',sum(p.numel() for p in model.parameters()))
print('input: [1,1,32,96], output:',list(y.shape))
''',encoding='utf-8')
    (OUT/'先看这里.md').write_text('''# 当前模型代码入口

本目录是当前车牌版代码的独立副本，原工程和板上程序不修改。

## 车牌识别

先看01_车牌模型与训练/tiny_plate_model.py。这是TinyPlate网络定义，PyTorch实现，93252参数，输入灰度96×32，输出68类别×24时间步。三组深度可分离卷积提特征，时序卷积输出序列，CTC训练及贪心解码得到完整车牌；不是YOLO，也没有全图定位。

train_tiny_plate.py：CTC主损失、训练集教师蒸馏和非车牌空白约束；plate_common.py：字符表及CTC解码；tiny_plate_integer.py：独立NumPy整数推理、BN融合及量化；evaluate_tiny_plate.py：定点评估与原生C数值比较。源码保持原路径配置，重训依赖E:/FPGA_Enhance_Work/license_plate_20261026中的数据、教师源码和缓存；本包未重复携带原始数据及完整训练环境。不要直接在已完成的实验目录重跑训练以覆盖成果。

仅查看网络并验证权重可加载：用现有Python环境运行01_车牌模型与训练/inspect_model.py，不需要数据集。

## 板上推理

02_板上车牌识别与应用/plate_native_kernel.h：标量整数卷积和预处理；plate_arm_kernel.h：ARM NEON提速；plate_weights.h：固化权重；digit_camera_adapter.h：当前实际是车牌ROI、CTC及一致性保护，digit名字是兼容旧主循环保留的接口；main.c：摄像头、增强、识别和屏幕流程。识别当前在ARM Cortex-A9运行，不是在PL卷积IP内。

03_权重与验证记录/plate_model.pth是已训练权重，不是训练代码；plate_integer_weights.npz是导出的整数权重，评测和校验记录也在此。训练模型SHA256为f1fea0af6bc03b4670a2010681f53ec74025ac91962bfb47d81a9d6631736b9d。

## FPGA图像增强

04_FPGA图像增强_HLS/multinex_hls.cpp是当前r4d的HLS C++计算调度，配套头文件包含算术与固化参数；fixed_multinex.py是定点参考；上游MultinexNano_arch.py是参考网络定义。HLS源码需Vitis HLS综合，再集成到Vivado，不能把C++当作Verilog直接加入综合。此目录是模型核心源码集合，不是完整Vivado工程；对应完整工程仍在E:/FPGA_Enhance_Work/multinex_fast_static_r4d_20261026/prj。原工程包含摄像头、显示、AXI及约束。

## 如何验证

识别效果：1200张按完整号码划分的测试裁剪，整牌准确率正常亮度81.83%，人工亮度0.25倍81.67%，0.125倍80.92%。同批图片暗化不算新增独立场景，教师预训练重叠未知，不能称新盲测。

部署正确性：独立NumPy整数参考与ARM实板灰度、Q10张量、CTC分数、token、字形逐项相同；PL增强与独立C++参考像素核对。14回放加1个摄像头帧通过。这只证明计算一致，不保证识别正确或增强有效。真实暗光是否改善识别仍需新场景对照。

当前仅给定ROI七位蓝牌，不支持自动找车牌及八位新能源牌。版权与第三方许可按各目录文件保留。
''',encoding='utf-8')
    files=sorted(p for p in OUT.rglob('*') if p.is_file())
    manifest=[dict(path=p.relative_to(OUT).as_posix(),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files]
    (OUT/'文件校验.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    archive=OUT.with_suffix('.zip');assert not archive.exists()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in files+[OUT/'文件校验.json']:z.write(p,p.relative_to(OUT).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert all(hashlib.sha256(z.read(r['path'])).hexdigest()==r['sha256'] for r in manifest)
    print('MODEL_SOURCE_PACKAGED',archive,archive.stat().st_size,flush=True)
if __name__=='__main__':main()
