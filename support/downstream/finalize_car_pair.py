"""Summarize actual board evidence and make a verified, recoverable archive."""
import hashlib,json,shutil,zipfile
import numpy as np
from car_pair_common import *
from road_numpy_eval import correct

def main():
 proof=read(ROOT/'board_verified.json');assert proof['status']=='ABI26_CAR_PAIR_ALL_INPUTS_AND_OUTPUTS_BOARD_VERIFIED'
 assert proof['elf_sha256']==sha(APP/'road_detail.elf') and proof['bit_sha256']==sha(APP/'display.bit')
 assert all(sha(APP/n)==h for n,h in read(APP/'runtime_checksums.json').items())
 evidence=Path(proof['evidence']);gt=np.asarray(read(ROOT/'fixtures/road/fixture.json')['ground_truth'],np.float32).reshape(-1,5);case={}
 for name,file in [('stable','baseline.f32'),('candidate','boxes.f32')]:
  p=np.fromfile(evidence/'road_revisit'/file,'<f4').reshape(-1,6);ok=correct(p,gt,np.array([.5],np.float32))[0][:,0];case[name]=dict(boxes=len(p),true_positive=int(ok.sum()),false_positive=int((~ok).sum()),ground_truth_cars=int((gt[:,0]==1).sum()))
 packets=proof['photo_results']+proof['camera_results']+[proof['road_revisit']];comparisons=[c for p in packets for c in p['neural_comparisons']]
 summary=dict(status='ABI26_CAR_PAIR_ACTUAL_BOARD_VERIFIED',packets=len(packets),neural_comparisons=len(comparisons),neural_max_abs=max(c['max_abs'] for c in comparisons),neural_mean_abs_max=max(c['mean_abs'] for c in comparisons),seconds_min=min(p['total_seconds'] for p in packets),seconds_max=max(p['total_seconds'] for p in packets),camera_seconds=[p['total_seconds'] for p in proof['camera_results']],camera_car_counts=[dict(stable=p['stable_cars'],candidate=p['candidate_cars']) for p in proof['camera_results']],observed_limitation='Indoor background produced car boxes in camera_2 for both models; no labelled real-camera accuracy study performed.',all_PL_calls408=all(p['pl_calls']==408 for p in packets),all_enhancement_byte_exact=all(p['enhancement_max_abs']==0 for p in packets),source_camera_banks=[p['source_bank'] for p in proof['camera_results']],revisit_all8_outputs_exact=proof['revisited_all8_decodes_pixels_boxes_byte_exact'],final_example=case,last_frame=str(Path(proof['last_packet'])/'lcd_readback.png'),physical_screen_check=proof['physical_screen_check'],sd_written=False)
 write(ROOT/'board_summary.json',summary)
 (ROOT/'使用说明.md').write_text('''# 已通过上板验收的汽车专项对照版

左侧STABLE CAR MODEL为稳定模型，右侧NEW CAR MODEL为微调模型。两侧背景都是同一张增强图；两套检测网络都读取同一冻结画面的四个未增强视图，只显示汽车框。

当前屏幕保留固定夜间道路示例，移动手掌不会改变图片。每次计算两套模型约19秒，属于单帧对照，JTAG传输与核对时间另计。

- 02_capture_again.cmd：摄像头重新拍摄一帧并运行两模型，期间保持镜头稳定。
- 04_fixed_road_photo.cmd：返回固定道路图对照。
- 01_start_car_comparison.cmd：断电后通过JTAG重新加载并拍摄一帧。
- 00_restore_stable_ABI24.cmd：恢复原稳定摄像头单帧版。
- 03_full_acceptance.cmd：重新执行完整验收，通常不需要重复运行。

本次只写运行内存，SD卡和Flash未改。断电后不会自动保存当前程序，需要JTAG重新加载。原稳定工程保留。

本版按用户选择优先比较汽车；此前四类综合验收失败的结论保留，不能称为四类全面提升。增强本轮未改，显示更亮不等于增强提高了识别。没有标注的实拍摄像头画面只用于功能和数值核对。
''',encoding='utf-8')
 workspace=Path(__file__).resolve().parents[2];path=workspace/'汽车专项对照版上板验收_20261030.md';text=['# 汽车专项对照版：上板验收（2026-10-30）','',
 '汽车专项ABI26已通过真实开发板的功能与数值验收。它保留原四类神经网络结构，后处理只显示car。两模型分别读取同一冻结帧的相同四个未增强视图；两侧背景均使用同一张Retinex增强图。左稳定模型，右第4轮微调模型。此前四类综合验收的失败结论没有被改写，本次不声称四类全面提升。','',
 f"共{summary['packets']}个实际板上数据包，包含真实道路图、灰图、黑图、3次摄像头采集和道路图复访。两模型全部{summary['neural_comparisons']}组解码输出均通过与独立x86 C的比较；最大绝对误差{summary['neural_max_abs']:.8f}，最大单组平均误差{summary['neural_mean_abs_max']:.8f}，门限分别为0.001和0.00002。",'',
 '每次快照有8次网络前向和408次PL卷积调用。增强像素、汽车后处理和LCD帧均通过逐字节核对；三次实际摄像头捕获均核对冻结源与被保护VDMA缓冲区相同。复访道路图的8组网络输出、原图、增强图、两侧汽车框与第一次运行逐字节一致。','',
 f"整对模型的板端处理时间范围{summary['seconds_min']:.2f}–{summary['seconds_max']:.2f}秒，摄像头3次分别为"+'、'.join(f'{v:.2f}' for v in summary['camera_seconds'])+'秒。JTAG上传、回读与电脑校验耗时另计。本工程是单帧对照，不能称为实时检测。','',
 '## 当前显示的固定道路示例','',
 f"稳定模型：{case['stable']['boxes']}个框，其中按原始标注、IoU0.5匹配的正确检出{case['stable']['true_positive']}个，误检{case['stable']['false_positive']}个。",
 f"新模型：{case['candidate']['boxes']}个框，其中正确检出{case['candidate']['true_positive']}个，误检{case['candidate']['false_positive']}个。",'',
 '这是按结果选择的展示案例，不替代全部320张独立暗光图片的统计。整体汽车AP50证据仍见scope.json及暗光分场景模型报告；图像增强只改变显示，本实验不能证明增强导致识别收益。没有标注的实物摄像头画面只核对功能、冻结输入和计算，不作为识别准确率证据。',
 '实际摄像头第二帧中，两套模型都在室内背景产生了汽车框（各2个），可见实拍背景误检仍存在。本次功能与数值通过不等于实际道路识别准确率已经达标，尚需对实际道路画面采集标注后评测。','',
 '## 使用','',
 '- 当前保留固定夜间道路图；移动手掌不会改变它。左右分别标为STABLE CAR MODEL和NEW CAR MODEL。',
 '- 02_capture_again.cmd：用摄像头重新拍摄一帧，等两套模型算完后更新。',
 '- 04_fixed_road_photo.cmd：重新运行固定道路示例。',
 '- 01_start_car_comparison.cmd：JTAG重新加载后拍摄一帧，适用于断电后重启。',
 '- 00_restore_stable_ABI24.cmd：恢复原稳定摄像头单帧版。',
 '- 本次只写运行内存，SD卡和Flash未改；断电后不会自动保留当前RAM程序。','',
 f'实际证据目录：`{evidence}`。',f'最终屏幕回读：`{summary["last_frame"]}`。','实物屏幕观察状态：'+proof['physical_screen_check']+'。','']
 path.write_text('\n'.join(text),encoding='utf-8')
 write(workspace/'当前汽车专项对照版_20261030.json',dict(status='ABI26_BOARD_VERIFIED',root=str(ROOT),report=str(path),board_summary=str(ROOT/'board_summary.json'),last_frame=summary['last_frame'],original_ABI24_preserved=True,sd_written=False))
 for p in Path(__file__).parent.glob('*car_pair*.py'):shutil.copy2(p,ROOT/'source'/p.name)
 archive=BASE/'road_car_pair_ABI26_board_verified_20261030.zip';assert not archive.exists();keep=[]
 for folder in ['firmware','tools','fixtures','source',evidence.name]:
  keep +=[p for p in (ROOT/folder).rglob('*') if p.is_file() and 'obj' not in p.parts and '__pycache__' not in p.parts and p.suffix not in ['.map','.su']]
 keep +=[p for p in ROOT.iterdir() if p.is_file() and p.suffix in ['.json','.cmd','.md']];keep=sorted(set(keep));hashes={p.relative_to(ROOT).as_posix():sha(p) for p in keep}
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in keep:z.write(p,p.relative_to(ROOT).as_posix())
  z.writestr('package_checksums.json',json.dumps(hashes,indent=2));z.write(path,'汽车专项对照版上板验收_20261030.md')
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  for name,h in hashes.items():assert hashlib.sha256(z.read(name)).hexdigest()==h
 receipt=dict(status='ABI26_BOARD_VERIFIED_ARCHIVE_CRC_AND_SHA_PASS',archive=str(archive),sha256=sha(archive),files=len(hashes),sd_written=False);write(ROOT/'verified_archive.json',receipt);print('CAR_PAIR_BOARD_FINALIZED',summary,receipt,flush=True)

if __name__=='__main__':main()
