"""Save reproducible research outcomes and weights, never mark failed tests accepted."""
import hashlib,json,shutil,zipfile
from road_brightness_route_common import *

def main():
 route=read(ROOT/'fresh_result.json');first=read(ADAPT/'fresh_result.json');workspace=Path(__file__).resolve().parents[2];dest=BASE/'road_model_research_package_20261030_r1';archive=BASE/'road_model_research_20261030_r1.zip';assert not dest.exists() and not archive.exists();dest.mkdir()
 def copy(src,relative):
  target=dest/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,target)
 for src,rel in [(ADAPT/'export/model.pt','weights/dark_epoch4.pt'),(ADAPT/'export/weights.f32','weights/dark_epoch4.f32'),(DATA/'frozen/road4_best.pt','weights/source_stable.pt'),(BASE/'road_accuracy_20261030_r1/firmware/runtime/weights.f32','weights/stable.f32'),(DATA/'yolov5/LICENSE','LICENSE_YOLOv5')]:copy(src,rel)
 for root,tag,names in [(ADAPT,'viewadapt',['protocol.json','training_config.json','training_complete.json','prepared.json','training_manifest.json','selected.json','selected_calibrated.json','selected_classcalibrated.json','calibration_protocol.json','class_calibration_protocol.json','c_development_result.json','fresh_protocol.json','fresh_result.json','fresh/manifest.json','export/complete.json','calibration_c/complete.json']),(ROOT,'brightness_route',['protocol.json','development.json','fresh_protocol.json','fresh_result.json','fresh/manifest.json','holdout_exclusions.json','router_c/build.json','router_c/complete.json','car_examples_with_regression.json','car_examples_with_regression.png'])]:
  for name in names:copy(root/name,'evidence/'+tag+'/'+name)
 for name in ['模型视图微调验收_20261030.md','暗光分场景模型验收_20261030.md','离线优化验收记录_20261030_类别校准.md']:copy(workspace/name,'reports/'+name)
 here=Path(__file__).resolve().parent;patterns=['*viewadapt*.py','*brightness_route*.py','road_score_*.*','native_road_accuracy.py','road_accuracy_common.py','road_classwise_common.py','road_classwise_native.py','road_numpy_eval.py','road_arm_common.py','road_adapt_common.py','road_vehicle_multiview.*','road_vehicle_classwise.*','export_road_twilight_weights.py','road_twilight_common.py','prepare_road_training_data.py','render_routed_car_examples.py','build_routed_camera.py','package_model_research.py']
 for p in sorted({p for pattern in patterns for p in here.glob(pattern)}):
  if p.is_file():copy(p,'source/'+p.name)
 for name in ['road_fp32.c','road_fp32.h','road_graph.h']:copy(BASE/'road_arm_prototype_20261026/source_r2'/name,'source/c_graph/'+name)
 examples=read(ROOT/'car_examples_with_regression.json')
 for r in examples:copy(Path(r['source']),'examples/'+r['name'])
 (dest/'README_CN.md').write_text('''# 模型实验留档（2026-10-30）

这是研究留档，不是已通过综合验收的替换固件。两次独立确认的失败项均保留，不能把研究候选标成正式稳定版。

新320张低亮度图片上，汽车AP50由44.94%提高到46.46%，汽车精确率和召回率均提高；描述性99.5%配对区间为+0.39至+2.81个百分点。同时卡车/公交车正确检出由34降到30，未达到预设的90%保留要求；大车精确率差值区间包含0。96张较亮图片使用原模型，四视图和融合输出均与独立执行的稳定版逐字节一致。

weights包含原权重和第4轮微调权重，FP32 f32文件采用现有C/FPGA图布局；pt文件需要配套YOLOv5模型代码加载。网络结构相同，增强算法本轮未改。本结果不能证明图像增强带来识别收益。

source保留训练、选择、C推理、路由、验收脚本及原C计算图。脚本中的E盘路径对应本机实验目录，重现时需要原数据与本地运行环境；本压缩包没有复制全部训练图片。训练输入、数据拆分、候选选择与每张新验收图片的哈希记录见evidence。三个示例含成功及退步场景，不能用示例代替全320张的统计。

build_routed_camera.py是尚未执行的固件构建脚本，完整离线通过门槛未满足时会拒绝构建。没有生成或宣称上板通过的新固件。当前已验收摄像头工程仍是ABI24；SD/Flash未修改。
''',encoding='utf-8')
 hashes={p.relative_to(dest).as_posix():sha(p) for p in dest.rglob('*') if p.is_file()};write(dest/'checksums.json',hashes)
 with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in sorted(dest.rglob('*')):
   if p.is_file():z.write(p,p.relative_to(dest).as_posix())
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  for name,digest in hashes.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
 receipt=dict(status='RESEARCH_PACKAGE_VERIFIED_NOT_DEFAULT_FIRMWARE',archive=str(archive),sha256=sha(archive),files=len(hashes)+1,viewadapt_independent_accepted=first['accepted'],route_independent_accepted=route['accepted'],active_verified_camera_version=24,sd_written=False);write(BASE/'road_model_research_package_20261030.json',receipt);print('MODEL_RESEARCH_PACKAGE_VERIFIED',receipt,flush=True)

if __name__=='__main__':main()
