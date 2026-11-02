"""Freeze actual ABI28 board receipts, runnable controls, and honest accuracy report."""
from pathlib import Path
import ast,csv,hashlib,json,shutil,zipfile
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from balanced_board_tools import ROOT,APP,STUDY
from car_box_refine_common import BASE,read,write,sha
from road_accuracy_common import truth
from road_numpy_eval import correct
from camera_snapshot_tools import rgb
HERE=Path(__file__).parent;WORK=HERE.parents[1]

def freeze_python(roots,dest):
 dest.mkdir(exist_ok=True);seen=set();todo=list(roots)
 while todo:
  name=todo.pop()
  if name in seen or not (HERE/(name+'.py')).exists():continue
  seen.add(name);p=HERE/(name+'.py');shutil.copy2(p,dest/p.name)
  for node in ast.walk(ast.parse(p.read_text(encoding='utf-8'))):
   if isinstance(node,ast.Import):todo.extend(a.name.split('.')[0] for a in node.names)
   elif isinstance(node,ast.ImportFrom) and node.module:todo.append(node.module.split('.')[0])
 return sorted(seen)

def main():
 board=read(ROOT/'board_verified.json');assert board['status']=='ABI28_BALANCED_CAR_ACTUAL_BOARD_VERIFIED'
 result=read(STUDY/'confirmation/fresh_result.json');assert result['accepted'];a=result['scores']['low']['baseline'];b=result['scores']['low']['candidate'];c=result['scores']['low']['unrefined_control']
 evidence=Path(board['evidence']);deps=[STUDY/'c_proof/refiner.dll',STUDY/'export/weights.f32',BASE/'road_car_zoom_20261030_r1/c_proof/zoom.dll',BASE/'road_brightness_route_20261030_r1/fresh_evaluation/routed_low/native/fusion.dll',BASE/'road_car_bright_20261030_r1/firmware/host/post.dll',BASE/'road_shadowlift_20261030_r1/c_proof/shadow.dll',BASE/'road_local_enhance_20261029_r2/host/road_ap.exe']
 write(ROOT/'runtime_dependencies.json',{str(p):sha(p) for p in deps})
 tools=ROOT/'tools';frozen=freeze_python(['balanced_board_entry','verify_balanced_board','validate_balanced_board','prepare_balanced_board_fixtures','train_car_boxrefine','prepare_car_boxrefine','study_car_verifier_veto','train_car_patch_verifier','prepare_car_patch_verifier'],tools)
 entries={'00_restore_ABI27':'restore27','01_start_camera':'start_camera','02_capture_again':'capture','03_start_fixed_photo':'start_photo','04_raw_vs_enhanced':'raw_enh','05_detector_comparison':'models','06_full_acceptance':'verify'}
 for name,mode in entries.items():(ROOT/(name+'.cmd')).write_text('@echo off\r\n"E:\\FPGA_Enhance_Work\\nn_env312\\Scripts\\python.exe" "%~dp0tools\\balanced_board_entry.py" '+mode+'\r\npause\r\n',encoding='ascii')
 readme='''# ABI28 平衡汽车识别版

已完成真实开发板读回验收；仅JTAG运行内存，SD卡和Flash未修改。旧ABI27完整保留。

- 03_start_fixed_photo.cmd：下载本版并运行固定道路图片，适合演示。
- 01_start_camera.cmd：下载本版并采集摄像头一帧。
- 02_capture_again.cmd：当前已运行本版时，再采集一帧。
- 04_raw_vs_enhanced.cmd：切换为原图/增强图；两边框来自同一候选检测结果。
- 05_detector_comparison.cmd：切换为4视图基线/自适应细节检测；两边使用相同增强背景。
- 06_full_acceptance.cmd：完整读回验收，需要保持板卡及JTAG在线，耗时数分钟。
- 00_restore_ABI27.cmd：恢复上一版并进入摄像头预览待命，不写SD卡。

这是单帧系统，拍摄新一帧需要触发。暗光图实测约15.6–17.5秒计算，不包含JTAG传输与电脑验收时间。较亮场景只跑4视图。

运行依赖本电脑现有E:/FPGA_Enhance_Work目录、Python环境和Vitis2020.2；请保留原目录结构。tools为冻结脚本，runtime_dependencies.json记录参考二进制哈希。源代码及已编译固件包含在此目录。simulated_reader_tests只是验证读回程序的模拟输入，里面的计时是人为测试值，不能用于测速；真实上板证据只看board_verified.json所指目录。
'''
 (ROOT/'使用说明.md').write_text(readme,encoding='utf-8')
 report=WORK/'平衡识别版验收_20261031';report.mkdir(exist_ok=True)
 fixture=read(ROOT/'fixtures/manifest.json');font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',13);canvas=Image.new('RGB',(1600,560),(15,15,15));case_stats=[]
 for row,rec in enumerate(fixture['roads']):
  packet=evidence/('photo_'+str(row));name=rec['source']['name'];g=truth(STUDY/'confirmation/fresh/labels'/(Path(name).stem+'.txt'));g=g[g[:,0]==1]
  raw=rgb(packet/'raw.u32');enh=rgb(packet/'enhanced.u32');panels=[('RAW',raw),('CURRENT ENHANCEMENT',enh)];counts=[]
  for label,file in [('BASE4','baseline.f32'),('BALANCED7','boxes.f32')]:
   p=np.fromfile(packet/file,'<f4').reshape(-1,6);ok=correct(p,g,np.array([.5],np.float32))[0][:,0];im=Image.fromarray(enh);d=ImageDraw.Draw(im)
   for box,hit in zip(p,ok):d.rectangle(tuple(box[:4]),outline=(30,255,70) if hit else (255,70,100),width=1)
   counts.append(dict(label=label,tp=int(ok.sum()),fp=int(len(p)-ok.sum()),cars=len(p)));panels.append((f'{label} TP {ok.sum()} FP {len(p)-ok.sum()}',np.asarray(im)))
  for col,(label,im) in enumerate(panels):
   canvas.paste(Image.fromarray(im),(col*400,row*280+40));d=ImageDraw.Draw(canvas);d.text((col*400+3,row*280+3),label,fill='white',font=font);d.text((col*400+3,row*280+21),name,fill='white',font=font)
  case_stats.append(dict(name=name,ground_truth_cars=len(g),results=counts))
 canvas.save(report/'实际上板_增强与识别对照.png');write(report/'实际示例标注核对.json',case_stats)
 shutil.copy2(evidence/'road_revisit/lcd_readback.png',report/'当前板上帧缓冲读回.png')
 ci=result['car_ap50_difference_interval99'];dark=[p for p in board['processing_seconds'] if p>12]
 text=f'''# 平衡汽车识别版：电脑独立测试与真实上板验收

用户优先级为“两者平衡：尽量多检出，同时控制误检”。ABI28已通过独立304图的便携C确认和真实开发板读回。SD卡、Flash未改，ABI27仍保留。

## 新的240张暗光图，2117个汽车标注

| 指标 | 当前模型4视图 | 7视图＋修框候选 |
|---|---:|---:|
| 汽车AP50 | {a['ap50']*100:.2f}% | {b['ap50']*100:.2f}% |
| 精确率 | {a['precision']*100:.2f}% | {b['precision']*100:.2f}% |
| 召回率 | {a['recall']*100:.2f}% | {b['recall']*100:.2f}% |
| F1 | {result['f1']['low']['baseline']*100:.2f}% | {result['f1']['low']['candidate']*100:.2f}% |
| 正确检出TP | {a['tp']} | {b['tp']} |
| 误检FP | {a['fp']} | {b['fp']} |
| 漏检FN | {a['fn']} | {b['fn']} |

AP50增加{(b['ap50']-a['ap50'])*100:.2f}个百分点，2000次配对图片bootstrap的99%区间为[{ci[0]*100:.2f}, {ci[1]*100:.2f}]个百分点。检出增加44个、漏检减少44个，误检也增加63个，精确率下降约0.14个百分点。通过本次新设定的平衡条件，并不代表误检已经解决。

64张较亮对照图沿用4视图路径，输出逐字节不变。暗光由未修改原图平均亮度≤48定义，不是实测照度。所有记录过的训练/评测/筛选前缀组和哈希均已排除；不同前缀仍可能地理相关。

先前“AP至少提升1个百分点、额外误检减少25%”等实验的失败仍保留。本次依据用户新确认的平衡目标，先冻结开发选择和验收条件，再测试新的304张图片，没有按新测试答案换参数。开发数据为已使用的320＋160张，不能再称为盲测。

## 模块贡献的边界

主要增益来自三张额外道路细节裁剪。未修框的7视图对照AP50为{c['ap50']*100:.2f}%，与修框候选{b['ap50']*100:.2f}%接近且略高；目前**没有证明修框网络单独提高了AP**。修框候选误检少3个、正确检出少1个，差别很小，不能夸大其收益。

图像增强沿用ABI27，当前只用于显示。检测输入仍是原图。**不能把本轮检测AP增益归因为图像增强。** 实际图片中仍能看到夜间噪点、色块和源图模糊，增强画质的后续实验单独保存，不自动替换已验证版本。

## FPGA与ARM分工

PL沿用同一FP32卷积加速硬件：每次主网络51次调用，暗光7视图357次，较亮4视图204次。ARM完成流程调度、图像增强、裁剪/预处理、其余网络计算与后处理、17549参数小型框修正网络、显示叠加。主YOLO结构及权重保持之前已接受的汽车专项模型，实际新训练的是小型修框网络。

## 实际开发板验收

- 6组实际读回：两张真实暗光道路图、灰图、黑图、一次真实摄像头采集、再次回放同一道路图。
- 共36组主网络输出与独立x86 C参考比较；96次实际ARM小网络调用核对通过。图像输入、冻结源、检测后处理、增强和帧缓冲校验通过；小网络输出和最终后处理本次读回均与参考逐位一致。
- 同一固定图在摄像头测试后再次计算，原图、增强、基线框、候选框、小网络输出均逐字节相同。
- 暗光计算实测{min(dark):.2f}–{max(dark):.2f}秒，较亮控制/摄像头约9.66–11.09秒；不含JTAG传输。单帧系统，不宣称实时。
- 304图的整体指标在电脑实际C程序上测量；板上验收是样例实现一致性，不能写成已在板上逐张跑完304图。实物面板本轮尚无用户目视反馈，所附为真实帧缓冲读回。

## 效果图阅读

“实际上板_增强与识别对照.png”前两列是同一帧原图与增强；后两列使用相同增强背景展示实际板上框。绿框为按原标注IoU0.5匹配的正确框，粉红框为误检。样例在冻结评测后选择，包括增益和新增误检案例，不替代全部240图的统计。

程序目录：{ROOT.as_posix()}。恢复与操作入口见该目录使用说明.md。当前显示原图/增强页，框是同一候选结果；05_detector_comparison.cmd可切换4视图/自适应细节页。
'''
 (report/'验收与效果说明.md').write_text(text,encoding='utf-8')
 write(STUDY/'confirmation/protocol_clarification.json',dict(legacy_helper_text='fresh_protocol.json checkpoint_selection contains inherited development640 wording.',actual_development_images=480,actual_source_protocol_sha256=sha(STUDY/'protocol.json'),actual_selection_sha256=sha(STUDY/'selected.json'),affects_data_or_model_selection=False,original_protocol_preserved=True))
 for src,name in [(ROOT/'board_verified.json','实际上板验收.json'),(STUDY/'confirmation/fresh_result.json','独立图片验收.json')]:shutil.copy2(src,report/name)
 latest=dict(status=board['status'],root=str(ROOT),report=str(report/'验收与效果说明.md'),elf_sha256=board['elf_sha256'],physical_board_verified=True,sd_written=False)
 write(WORK/'当前平衡识别运行版_20261031.json',latest)
 with (report/'独立暗光指标.csv').open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.writer(f);w.writerow(['指标','4视图','7视图修框','7视图未修框对照'])
  for k in ['ap50','precision','recall','tp','fp','fn']:w.writerow([k,a[k],b[k],c[k]])
 members={}
 for p in ROOT.rglob('*'):
  if p.is_file() and not any(v in p.relative_to(ROOT).parts for v in ['obj','native','producer_native','__pycache__','simulated_reader_tests']):members['board/'+p.relative_to(ROOT).as_posix()]=p
 for p in report.rglob('*'):
  if p.is_file():members['report/'+p.relative_to(report).as_posix()]=p
 for name in ['protocol.json','selected.json','c_complete.json','export/model.pt','export/weights.f32','export/complete.json','confirmation/fresh/manifest.json','confirmation/fresh_result.json','confirmation/inference_policy.json','confirmation/baseline_predictions.json','confirmation/candidate_predictions.json','confirmation/unrefined_control_predictions.json','confirmation/protocol_clarification.json']:
  members['study/'+name]=STUDY/name
 for p in (STUDY/'c_proof/source').iterdir():
  if p.is_file():members['portable_c/'+p.name]=p
 digests={name:sha(p) for name,p in members.items()};archive=BASE/'road_car_balanced_ABI28_board_verified_20261031.zip';assert not archive.exists()
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for name,p in members.items():z.write(p,name)
  z.writestr('manifest.json',json.dumps(dict(sha256=digests,board_verified=True,SD_and_Flash_untouched=True),ensure_ascii=False,indent=2))
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  for name,digest in digests.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
 receipt=dict(status='ABI28_ACTUAL_BOARD_ARCHIVE_VERIFIED',archive=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,members=len(members)+1,crc_and_every_member_sha256_verified=True,frozen_python_modules=len(frozen),sd_written=False)
 write(ROOT/'archive_verified.json',receipt);write(report/'归档校验.json',receipt)
 print('BALANCED_BOARD_ARCHIVED',receipt,flush=True)

if __name__=='__main__':main()
