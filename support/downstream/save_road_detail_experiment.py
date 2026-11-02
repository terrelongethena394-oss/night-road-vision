"""Save a reviewable experimental bundle and independent ABI13 recovery; no board calls."""
from pathlib import Path
import shutil,zipfile
from road_roi_spatial_common import ROOT,BASE,GUARD,read,write,sha
HERE=Path(__file__).resolve().parent
WORK=HERE.parents[1]
APP=ROOT/'firmware_experiment'
CURRENT=BASE.parent/'road_enhance_20261027/firmware'
DEST=BASE.parent/'road_detail_experiment_20261028'

def main():
 assert read(APP/'entries_complete.json')['hardware_test_status']=='PENDING_USER_EXPLICITLY_DEFERRED_BOARD_TEST'
 assert (ROOT/'native_detector_complete.json').exists();DEST.mkdir(exist_ok=False);firmware=DEST/'firmware';shutil.copytree(APP,firmware,ignore=shutil.ignore_patterns('obj','*.log','static_readback'))
 for n,h in read(firmware/'runtime_checksums.json').items():assert sha(firmware/n)==h,n
 recovery=DEST/'previous_verified';recovery.mkdir()
 for name,h in read(CURRENT/'runtime_checksums.json').items():
  p=CURRENT/name;assert sha(p)==h;target=recovery/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
 for n in ['runtime_checksums.json','arm_complete.json','session_r1.json']:shutil.copy2(CURRENT/n,recovery/n)
 for name,h in read(recovery/'runtime_checksums.json').items():assert sha(recovery/name)==h,name
 entries={'01_load_experiment_default.cmd':('firmware\\experiment.py','start'),'02_camera_detail_x2.cmd':('firmware\\experiment.py','switch 1'),'03_camera_single_pass.cmd':('firmware\\experiment.py','switch 0'),'00_restore_previous.cmd':('previous_verified\\start_auto_live.py','')}
 first=read(APP/'arm_complete.json')['cases'][0]['name'];entries.update({'04_static_first_raw.cmd':('firmware\\experiment.py',f'static {first} 0'),'05_static_first_detail.cmd':('firmware\\experiment.py',f'static {first} 1')})
 for name,(program,args) in entries.items():
  (DEST/name).write_text('@echo off\r\n"E:\\FPGA_Enhance_Work\\nn_env312\\Scripts\\python.exe" "%~dp0'+program+'" '+args+'\r\npause\r\n',encoding='ascii')
 license=BASE/'yolov5/LICENSE';shutil.copy2(license,DEST/'YOLOv5_LICENSE')
 evidence=DEST/'evidence';evidence.mkdir()
 files={'guard_first_test.json':GUARD/'fresh_complete.json','guard_old_selection.json':GUARD/'selected.json','second_test_with_verifier.json':ROOT/'fresh_complete.json','same_images_ablation.json':ROOT/'fresh_ablation/complete.json','both_detector_views_C_proof.json':ROOT/'native_detector_complete.json','verifier_C_proof.json':ROOT/'native_verifier/complete.json','verifier_pipeline800_C_proof.json':ROOT/'native_pipeline/complete.json','first_test_manifest.json':GUARD/'fresh/manifest.json','second_test_manifest.json':ROOT/'fresh/manifest.json','first_test_protocol.json':GUARD/'fresh_protocol.json','second_test_protocol.json':ROOT/'fresh_protocol.json'}
 for name,p in files.items():shutil.copy2(p,evidence/name)
 sources=DEST/'research_source';sources.mkdir();names=['road_roi_guard_common.py','analyze_road_roi_errors.py','evaluate_road_roi_guard.py','fetch_road_roi_guard_test.py','test_road_roi_guard.py','road_roi_verifier_common.py','prepare_road_roi_verifier.py','train_road_roi_verifier.py','evaluate_road_roi_verifier.py','road_roi_spatial_common.py','train_road_roi_spatial.py','evaluate_road_roi_spatial.py','fetch_road_roi_verifier_test.py','fetch_road_roi_spatial_test.py','test_road_roi_verifier.py','test_road_roi_spatial.py','ablate_road_roi_spatial.py','prove_road_roi_guard_c.py','prove_road_roi_spatial_c.py','prove_road_roi_verified_pipeline.py','prove_road_roi_detector_views.py','build_road_roi_experiment.py','prepare_road_roi_entries.py','save_road_detail_experiment.py']
 for name in names:shutil.copy2(HERE/name,sources/name)
 # The verifier is retained as a failed research trial, never runtime firmware.
 discarded=DEST/'research_verifier_discarded';discarded.mkdir();choice=read(ROOT/'selected.json')['chosen'];shutil.copy2(choice['checkpoint'],discarded/'model_epoch20.pt')
 for n in ['protocol.json','training_config.json','training_complete.json','selected.json']:shutil.copy2(ROOT/n,discarded/n)
 write(discarded/'NOT_IN_RUNTIME.json',dict(reason='Same-cohort ablation: no FP reduction, one fewer person TP, slightly lower mAP. Runtime intentionally uses geometry only.',verifier_in_firmware=False))
 one=read(GUARD/'fresh_complete.json');two=read(ROOT/'fresh_complete.json');ablation=read(ROOT/'fresh_ablation/complete.json');pairs=[('第一批独立图片',one['baseline'],one['candidate']),('第二批独立图片',two['baseline'],ablation['geometry_only'])]
 lines=['# 高细节道路检测实验版（2026-10-28）','',
  '**已按要求单独保存，本轮没有上板。现有板上程序、SD 卡和 Flash 均未修改。**','',
  '本次有效改进是保留中心区域更多像素，并在全景检测后增加一次中心区域检测。网络继续使用原 YOLOv5n 四类权重，FPGA bit 保持不变。传统 Gamma 仅负责显示提亮。', '',
  '## 新功能与真实测试结果','',
  '800×480 原始帧一方面做全景缩小，另一方面直接取中心 400×240 像素。两路分别运行同一检测器，将中心框映射回全景，用固定的区域边界、行人宽高比、重叠过滤、置信度校准和分类 NMS 合并。中心目标进入网络后的尺寸约为原来的两倍；这是保留已有像素，不能称为超分辨率。','',
  '两批各480张新图片，均排除之前训练、验证和旧测试的文件前缀组及图片哈希；各有160张黎明／黄昏、192张夜间、128张日间。第二批下面列的是同批消融得到的无复核网络版本，不能把不同批次的绝对分数互相比高低。','',
  '| 图片批次 | 黎明／黄昏 mAP@0.5 | 行人检出 / 总数 | 行人误检 |','|---|---:|---:|---:|']
 totals={'n':0,'raw_tp':0,'raw_fp':0,'detail_tp':0,'detail_fp':0}
 for title,a,b in pairs:
  ap=a['by_time']['dawn/dusk'];bp=b['by_time']['dawn/dusk'];p=ap['classes']['person'];q=bp['classes']['person'];lines.append(f"| {title} | {ap['mAP50']*100:.2f}% → {bp['mAP50']*100:.2f}% | {p['tp']} → {q['tp']} / {p['objects']} | {p['fp']} → {q['fp']} |")
  totals['n']+=p['objects'];totals['raw_tp']+=p['tp'];totals['raw_fp']+=p['fp'];totals['detail_tp']+=q['tp'];totals['detail_fp']+=q['fp']
 lo,hi=one['paired_bootstrap']['interval95'];lines += ['',f"第一批黎明／黄昏 mAP 差值的1000次配对 bootstrap 95%区间为 [{lo*100:+.2f}, {hi*100:+.2f}] 个百分点。第二批的无复核网络结果是固定策略的后续消融分析，不冒充预先登记的独立主终点。",'',
  f"合计351个黎明／黄昏行人：检出 {totals['raw_tp']} → {totals['detail_tp']}；误检 {totals['raw_fp']} → {totals['detail_fp']}。召回 {totals['raw_tp']/totals['n']*100:.2f}% → {totals['detail_tp']/totals['n']*100:.2f}%，精确率 {totals['raw_tp']/(totals['raw_tp']+totals['raw_fp'])*100:.2f}% → {totals['detail_tp']/(totals['detail_tp']+totals['detail_fp'])*100:.2f}%。这些是同一固定策略的汇总工作点结果，不是整张图片的“识别准确率”。",'',
  '第一批的行人误检超过事先设定的默认升级上限；提高召回伴随更多误检。因此它仍是可切换的实验模式，默认关闭，未替换原来运行版本。黎明与黄昏是数据集的合并标签；这些结果不能证明真实黄昏行驶视频或本机摄像头已经达到同样效果。','',
  '我们还实际训练了一个12993参数候选框复核网络，但同批对照显示误检没有减少、还少检出一个行人，已从运行版移除。训练代码、检查点与失败结果留在研究记录中，不能作为有效模块介绍。','',
  '## 速度和 ARM／FPGA 分工','',
  '- 单次模式：每帧一次 YOLO；高细节模式：全景与中心各一次。预计检测耗时接近翻倍，实际板上耗时、帧率和画面尚未测量，不能称作实时加速版。',
  '- ARM：图像缓存、缩小／裁剪、显示 Gamma、未卸载的网络层、激活、解码、结果合并和屏幕绘制。',
  '- FPGA：沿用原12个3×3卷积层的加速路径；高细节模式每个结果执行两次，合计24次卸载调用。bit与主检测器权重未改。','',
  '## 保存位置与以后使用顺序','',
  f'目录：`{DEST.as_posix()}`。本次只保存，下面的命令尚未在板卡上执行。', '',
  '1. 以后方便上板时，保持开发板独立供电、JTAG连接，使用此前验证过的 JTAG 启动配置。',
  '2. `01_load_experiment_default.cmd` 下载实验程序，默认保持单次检测，界面仍显示增强图、检测使用原图。',
  '3. `02_camera_detail_x2.cmd` 开启中心双次检测；右侧标注 `DETAIL X2 / EXPERIMENT`，左侧继续最新预览，右侧更新周期会更长。',
  '4. `03_camera_single_pass.cmd` 恢复单次检测。',
  '5. `04_static_first_raw.cmd` 与 `05_static_first_detail.cmd` 用同一固定图片对比，显示后保持暂停。再运行摄像头切换命令即可恢复活动画面。保留之前的读回文件，重复同一测试前需归档 `firmware/static_readback`，程序不会覆盖它。',
  '6. `00_restore_previous.cmd` 从随包保留的已验证 ABI13 文件恢复原版本。', '',
  '上述都是 JTAG／RAM 操作，程序没有 SD／Flash 写入功能。断电后本次 RAM 程序不保留。所需 Python、XSCT 路径沿用本机 E 盘已安装环境，压缩包不是独立安装器。','',
  '## 已完成与未完成的验证','',
  '- 两路检测输入各8个样本的全部86层、检测头和解码，已完成主机 C／PyTorch 数值检查，沿用原FP32容差。实板夹具选择其中6张真实图片加黑图，随机算子测试图不充当同源传感器双视图。',
  '- 7组固定输入已检查全景缩小与中心像素的一致性；16字界面结构和14次主机绘制保护区检查通过。',
  '- 被移除的小网络6034个样本的C概率误差最大约0.000001、裁剪字节一致；800张图片的新后处理 C 流程也已核对。这些是被移除模块的研究记录，不能算作运行版的精度收益。',
  '- ARM实验程序已编译；ELF地址与新增DDR区域检查通过；bit与权重校验一致。',
  '- **尚未完成：新程序实板数值、摄像头输入一致性、显示、持续运行、处理延迟及切换／恢复验证。**', '',
  '## 主要文件','',
  '- `firmware/road_detail.elf`：ABI15实验程序，默认中心额外检测关闭。',
  '- `firmware/source/road_camera_main.c`、`road_roi_guard.c`：本次ARM推理流程与结果过滤代码。',
  '- `firmware/runtime/weights.f32`：原YOLOv5n权重，保持不变。',
  '- `previous_verified/`：校验完整的原ABI13恢复快照。',
  '- `evidence/`：分组信息、固定协议、指标、消融与数值验证。',
  '- `research_source/`、`research_verifier_discarded/`：研究与失败记录；研究脚本依赖原工程环境，不是独立运行教程。','',
  'FPGA硬件逻辑、既有HLS／Vivado工程沿用此前已验证版本；这里保存本次改动的ARM源码、编译产物和已有bit/XSA。保留YOLOv5 GPL-3.0及原驱动版权标识。']
 report=WORK/'高细节检测实验版说明_20261028.md';report.write_text('\n'.join(lines)+'\n',encoding='utf-8');shutil.copy2(report,DEST/'README_CN.md')
 write(DEST/'saved_state.json',dict(status='SAVED_ONLY_BOARD_TEST_EXPLICITLY_DEFERRED_BY_USER',version=15,default_detail=0,verifier_in_runtime=False,board_downloaded=False,sd_written=False,flash_written=False,default_upgrade_accepted=False,prototype_elf_sha256=sha(firmware/'road_detail.elf'),original_elf_sha256=sha(recovery/'road_enhance.elf'),point_summary=totals,source_unchanged_abi13_checks_verified=True))
 manifest={str(p.relative_to(DEST)):sha(p) for p in DEST.rglob('*') if p.is_file()};write(DEST/'bundle_checksums.json',manifest)
 archive=DEST.with_suffix('.zip');assert not archive.exists()
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
  for p in sorted(DEST.rglob('*')):
   if p.is_file():z.write(p,DEST.name+'/'+p.relative_to(DEST).as_posix())
 with zipfile.ZipFile(archive) as z:assert z.testzip() is None
 for name,h in read(firmware/'runtime_checksums.json').items():assert sha(firmware/name)==h
 for name,h in read(recovery/'runtime_checksums.json').items():assert sha(recovery/name)==h
 receipt=dict(status='EXPERIMENT_AND_INDEPENDENT_RECOVERY_ARCHIVED_CRC_SHA_VERIFIED',directory=str(DEST),archive=str(archive),archive_sha256=sha(archive),bytes=archive.stat().st_size,files=len(manifest),report=str(report),board_downloaded=False,sd_written=False,flash_written=False);write(ROOT/'saved_experiment_complete.json',receipt);write(DEST.with_name(DEST.name+'_archive.json'),receipt);print('DETAIL_EXPERIMENT_SAVED_VERIFIED',archive,archive.stat().st_size,flush=True)
if __name__=='__main__':main()
