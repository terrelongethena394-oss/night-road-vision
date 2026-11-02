"""Archive actual brightness/display verification separately from recognition claims."""
import hashlib,json,shutil,zipfile
import numpy as np
from pathlib import Path
from shadowlift_lab import BASE,ROOT as LAB,OLD as PREVIOUS,read,write,sha,unpack,mean_y,Baseline
ROOT=BASE/'road_car_bright_20261030_r1';APP=ROOT/'firmware'

def main():
 proof=read(ROOT/'board_verified.json');assert proof['status']=='ABI27_CAR_BRIGHT_DISPLAY_BOARD_VERIFIED' and proof['old_ABI26_all_road_8_decodes_and_boxes_byte_exact']
 assert all(sha(APP/n)==h for n,h in read(APP/'runtime_checksums.json').items());evidence=Path(proof['evidence']);packets=proof['photo_results']+proof['camera_results']+proof['road_revisits'];folders=[evidence/f'photo_{i}' for i in range(4)]+[evidence/'camera_1',evidence/'road_revisit_1',evidence/'road_revisit_2'];base=Baseline();quality=[]
 for folder in folders:
  raw=unpack(np.fromfile(folder/'raw.u32','<u4')).reshape(240,400,3);actual=unpack(np.fromfile(folder/'enhanced.u32','<u4')).reshape(240,400,3);old=base.run(raw);sat=int(((actual.max(2)==255)&(old.max(2)<255)).sum());assert sat==0
  bright=old.max(2)>=245;assert np.array_equal(actual[bright],old[bright]);assert mean_y(actual)>=mean_y(old)-.01
  if mean_y(old)>=62:assert actual.tobytes()==old.tobytes()
  quality.append(dict(packet=folder.name,raw_mean_y=mean_y(raw),old_mean_y=mean_y(old),new_mean_y=mean_y(actual),newly_saturated255=sat,near_white_old_pixels_unchanged=True))
 last=Path(proof['last_packet']);oldlast=Path(read(PREVIOUS/'board_verified.json')['last_packet']);old=np.fromfile(oldlast/'enhanced.u32','<u4');new=np.fromfile(last/'enhanced.u32','<u4');assert (last/'raw.u32').read_bytes()==(oldlast/'raw.u32').read_bytes()
 comparisons=[v for p in packets for v in p['neural_comparisons']];summary=dict(status='ABI27_BRIGHTER_DISPLAY_BOARD_VERIFIED',packets=len(packets),neural_comparisons=len(comparisons),all_road_neural_outputs_and_boxes_equal_actual_ABI26=True,display_pages_C_frame_exact=[0,1],seconds_range=[min(p['total_seconds'] for p in packets),max(p['total_seconds'] for p in packets)],enhancement_C_max_abs=max(p['enhancement_max_abs'] for p in packets),quality=quality,last_frame=str(last/'lcd_readback.png'),previous_mean=mean_y(unpack(old).reshape(240,400,3)),new_mean=mean_y(unpack(new).reshape(240,400,3)),same_weights=True,same_PL_bit=True,SD_and_Flash_untouched=True,physical_check='Actual framebuffer inspected; user had confirmed previous ABI26 physical display normal',image_quality_limits='Known-scene qualitative development, no paired normal-exposure ground truth; no PSNR/SSIM quality improvement or recognition gain claimed.')
 write(ROOT/'board_summary.json',summary)
 (ROOT/'使用说明.md').write_text('''# 已通过上板核对的提亮增强版（ABI27）

默认左RAW IMAGE原图、右ENHANCED IMAGE增强图。两侧相同汽车框均来自原图检测，这一页单独展示画质变化，不代表增强提高了识别。

- 02_models.cmd：切换两模型对照，左稳定模型、右微调模型；两侧背景都是新版增强图。
- 03_enhancement.cmd：返回原图/增强图。切页不重新跑模型。
- 01_capture_camera.cmd：拍摄一个新的摄像头快照，计算约17秒后更新。
- 04_fixed_road.cmd：重新运行固定道路图。
- 05_start_camera.cmd：断电后通过JTAG重新加载并拍摄一帧。
- 00_restore_ABI26.cmd：恢复上一个已验证的汽车对照版。

快捷控制需要JTAG连接，所有控制只改运行内存；SD/Flash没有修改。断电后需重新加载。原ABI26及更早稳定工程保留。

增强增加暗部曝光、色度噪声抑制和色域保护，没有新增亮度空间模糊；已有原图光晕、压缩噪声和模糊仍可能被看见。增强不是新训练的神经网络，检测网络与权重均保持原样。

这是单帧演示，不是实时检测；没有标注的摄像头画面不作为准确率证据。此前四类综合验收失败的记录保留。
''',encoding='utf-8')
 here=Path(__file__).resolve().parent;workspace=here.parents[1];report=workspace/'提亮增强版上板验收_20261030.md'
 text=['# 提亮增强版：上板验收（2026-10-30）','',
 '针对“增强后仍太暗”，在已验证ABI26的Retinex/轻度去噪后增加自适应暗部曝光和亮度保持的色度清理。比较了偏强版本后选取目标平均亮度62的中等方案；避免为追求更亮而过度扩大原有噪声和光晕。无新增空间亮度平滑，不生成原图不存在的细节。','',
 f"当前同一张道路图原增强平均亮度为{summary['previous_mean']:.2f}，新版为{summary['new_mean']:.2f}（0–255）。这只是该场景的曝光统计，不是通用画质评分。",'',
 '## 实际验收','',
 f"电脑端37组场景/边界的C与NumPy比对通过。板上{summary['packets']}个数据包、{summary['neural_comparisons']}组网络输出核对通过；增强像素与C参考的最大差值为{summary['enhancement_C_max_abs']}。这里的C参考SSIM或像素一致性只用于实现核对，不是与正常曝光真值的图像质量评价。",'',
 '真实道路图的两模型全部8组解码结果、原图和汽车框，均与实际ABI26逐字节一致；识别输入、两套权重、PL位流和卷积实现不变。亮度改进只用于显示，不能据此声称检测准确率提高。',
 '原图/增强图页与两模型对照页都核对了C渲染结果，切页没有重新运行检测或改变图像/检测框；切页后重新推理也通过。','',
 '每个实际数据包均相对冻结旧增强算法检查：没有增加255饱和像素，旧图接近白色的像素保持不变；旧增强均值已达到62的图片完全旁路新增处理。',
 f"本轮板端计算时间{summary['seconds_range'][0]:.2f}–{summary['seconds_range'][1]:.2f}秒/双模型快照，JTAG上传回读和电脑校验另计。不是实时检测。",'',
 '## 各场景曝光','', '| 数据包 | 原图均值 | 旧增强均值 | 新增强均值 | 新增255饱和像素 |','| --- | ---: | ---: | ---: | ---: |']
 for r in quality:text.append(f"| {r['packet']} | {r['raw_mean_y']:.2f} | {r['old_mean_y']:.2f} | {r['new_mean_y']:.2f} | {r['newly_saturated255']} |")
 text+=['','## 显示和限制','',
 '当前默认左原图、右增强图，同样的新版汽车框叠加在两侧。需要对比模型时运行02_models.cmd，此时左右背景都使用新版增强图。03_enhancement.cmd回到画质对照。','',
 '已在电脑检查实际LCD帧，路面、路肩和暗处更可见，仍有原图噪声、光晕与模糊。画质方案是在已知示例上开发，没有配对正常曝光真值，不声称PSNR或主观质量的独立统计提升。摄像头场景也未做标注准确率评测。','',
 '原ABI26和早期稳定版保留；本次SD/Flash没有修改。完整证据：`'+str(evidence)+'`。','最终屏幕：`'+summary['last_frame']+'`。','']
 report.write_text('\n'.join(text),encoding='utf-8');write(workspace/'当前提亮增强版_20261030.json',dict(status='ABI27_BOARD_VERIFIED',root=str(ROOT),report=str(report),last_frame=summary['last_frame'],original_ABI26_preserved=True,SD_and_Flash_untouched=True))
 for pattern in ['*car_bright*.py','*shadowlift*.py','road_shadowlift.*','road_retinex_shadow.c']:
  for p in here.glob(pattern):
   if p.is_file():shutil.copy2(p,ROOT/'source'/p.name)
 for n in ['selected.json','c_complete.json','protocol.json','development.json','chroma_development.json','final_comparison.png']:
  target=ROOT/'quality_evidence'/n;target.parent.mkdir(exist_ok=True);shutil.copy2(LAB/n,target)
 archive=BASE/'road_car_bright_ABI27_board_verified_20261030.zip';assert not archive.exists();keep=[]
 for folder in ['firmware','tools','fixtures','source','quality_evidence',evidence.name]:keep +=[p for p in (ROOT/folder).rglob('*') if p.is_file() and 'obj' not in p.parts and '__pycache__' not in p.parts and p.suffix not in ['.map','.su']]
 keep +=[p for p in ROOT.iterdir() if p.is_file() and p.suffix in ['.json','.cmd','.md']];keep=sorted(set(keep));checks={p.relative_to(ROOT).as_posix():sha(p) for p in keep}
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in keep:z.write(p,p.relative_to(ROOT).as_posix())
  z.writestr('package_checksums.json',json.dumps(checks,indent=2));z.write(report,'提亮增强版上板验收_20261030.md')
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  for name,h in checks.items():assert hashlib.sha256(z.read(name)).hexdigest()==h
 receipt=dict(status='ABI27_BOARD_VERIFIED_PACKAGE_CRC_AND_SHA_PASS',archive=str(archive),sha256=sha(archive),files=len(checks),sd_written=False);write(ROOT/'verified_archive.json',receipt);print('CAR_BRIGHT_FINALIZED',summary,receipt,flush=True)
if __name__=='__main__':main()
