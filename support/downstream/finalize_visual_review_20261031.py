"""Record actual visual review, rejected candidates, and the retained board version."""
from pathlib import Path
import json,shutil,zipfile
from car_box_refine_common import BASE,read,write,sha
HERE=Path(__file__).parent;WORK=HERE.parents[1]

def main():
 study=BASE/'road_display_noiseguard_20261031_r1';out=WORK/'平衡识别版验收_20261031/画质检查';out.mkdir(exist_ok=True)
 selected=BASE/'road_car_balanced_20261030_r1/board_candidate';receipt=read(selected/'board_verified.json')
 assert receipt['status']=='ABI28_BALANCED_CAR_ACTUAL_BOARD_VERIFIED'
 for name in ['comparison.png','guided_comparison.png','detailguard_comparison.png','detailguard_crop.png']:
  shutil.copy2(study/name,out/name)
 decision=dict(status='RETAIN_ACTUAL_BOARD_VERIFIED_ABI28_NO_DISPLAY_CANDIDATE_PROMOTED',date='2026-10-31',
  inspected_actual_readbacks=[str(Path(receipt['evidence'])/'photo_0/lcd_readback.png'),str(Path(receipt['evidence'])/'photo_1/lcd_readback.png')],
  recognition_review='Actual GT-matched hardware outputs:gain sceneTP3->6 FP4->4;difficult sceneTP2->3 FP1->5. Full240-image results,not these selected examples,define overall accuracy.',
  display_observations='Current output visibly improves road visibility;noise,color blocks and input blur remain. Source-selected examples do not establish global perceptual quality.',
  variants=[dict(name='SNR post-exposure',decision='NOT_PROMOTED',reason='Almost no change:the two board examples already bypass added exposure at prior baseline mean>=62;Haar median estimate0.'),
            dict(name='Guided direct illumination',decision='REJECTED',reason='Visually amplified dark sky color blocks;road visibility did not justify new artifacts.'),
            dict(name='Conservative chroma/black guard with source-edge lift',decision='RESEARCH_ONLY',reason='Small chroma change and limited edge acutance,with loss of some dark brightness;not a clear overall improvement over current output.')],
  no_paired_normal_exposure_reference=True,no_PSNR_or_SSIM_quality_gain_claim=True,
  display_experiments_do_not_change_detector_inputs=True,board_firmware_unchanged_during_visual_experiments=True,sd_written=False)
 write(study/'decision.json',decision);write(out/'检查决策.json',decision)
 text='''# 我实际检查了哪些图片

已经查看ABI28开发板实际帧缓冲读回的两张暗光道路图，并用原始标注核对实际框。当前画面能明显提亮路面和暗处，但仍有颗粒、色块和源图模糊。

成功例：正确检出3→6，误检4→4。困难例：正确检出2→3，误检1→5。它们按结果选择，只用于说明成功与失败，不能取代完整240图的统计。

## 电脑上追加的三类画质实验

1. SNR附加曝光控制：在当前两张上板图片上几乎不改变结果，没有可见收益。
2. 直接导向亮度估计：虽保留原始亮度细节，但天空色块更明显，已淘汰。
3. 色度清理、暗噪声保护和真实边缘轻增强：只有小幅变化，同时部分暗部略变暗，尚不能认为整体更好，保留为研究分支。

因此当前开发板继续运行已验证的ABI28，未把这些画质候选下载到板上。原图/增强图是相同检测结果叠加，图像增强不改变检测输入；检测提升主要来自多尺度细节补偿，修框模块的独立收益尚未证实。

`guided_comparison.png`中第三、四列是已淘汰的电脑候选。`detailguard_comparison.png`中第三、四列尚未上板。`detailguard_crop.png`是2倍最近邻像素检查图，不是恢复出的高分辨率细节。所有图片均为确定性算法输出，没有使用生成式图像补画道路或车辆。

目前没有对应的正常曝光真值，不能据这些照片给出PSNR/SSIM画质提升结论。后续减少误检应更多针对原有主检测器的困难背景和小目标框定位，单纯继续提亮或增加框数不能解决。
'''
 (out/'图片检查说明.md').write_text(text,encoding='utf-8')
 report=WORK/'平衡识别版验收_20261031/验收与效果说明.md'
 with report.open('a',encoding='utf-8') as f:f.write('\n\n补充：已完成实际图像目视检查及三类电脑画质候选对比，均未作为整体更优的显示方案部署，继续保留ABI28。详见画质检查/图片检查说明.md。\n')
 archive=BASE/'road_display_visual_review_20261031.zip';assert not archive.exists()
 members={}
 for p in study.rglob('*'):
  if p.is_file():members['experiments/'+p.relative_to(study).as_posix()]=p
 for p in out.iterdir():
  if p.is_file():members['review/'+p.name]=p
 for name in ['study_display_noiseguard_20261031.py','study_guided_display_20261031.py','study_display_detailguard_20261031.py','finalize_visual_review_20261031.py']:
  members['source/'+name]=HERE/name
 hashes={name:sha(p) for name,p in members.items()}
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for name,p in members.items():z.write(p,name)
  z.writestr('manifest.json',json.dumps(dict(sha256=hashes,board_version_retained=28,no_display_candidate_deployed=True,sd_written=False),ensure_ascii=False,indent=2))
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  for name,digest in hashes.items():assert __import__('hashlib').sha256(z.read(name)).hexdigest()==digest
 write(out/'实验归档校验.json',dict(archive=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,all_hashes_verified=True))
 print('VISUAL_REVIEW_COMPLETE_RETAIN_ABI28',str(out),sha(archive),flush=True)

if __name__=='__main__':main()
