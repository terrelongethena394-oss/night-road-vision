"""Evidence package: preserve failed gates and positive but below-target result."""
from pathlib import Path
import csv,hashlib,json,shutil,zipfile
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from study_car_zoom_20261030 import ROOT
from road_enhanceadapt_common import BASE,read,write,sha
from road_accuracy_common import sensor400
from road_numpy_eval import correct,evaluate
from audit_bright_detector_20261030 import Enhancer

def counted(row):
 p=np.asarray(row['detections'],np.float32).reshape(-1,6);p=p[p[:,4]>=.25]
 g=np.asarray(row['ground_truth'],np.float32).reshape(-1,5)
 ok=correct(p,g,np.array([.5],np.float32))[0][:,0]
 return p,ok,int(ok.sum()),int(len(p)-ok.sum())

def main():
 work=Path(__file__).resolve().parents[2];out=work/'优化结果与独立测试_20261030';out.mkdir(exist_ok=True)
 final=read(ROOT/'confirmation/fresh_result.json');assert not final['accepted']
 assert final['low_gates']==dict(ap=False,precision=True,recall=True,ap_gain_ci99_positive=True)
 assert final['no_test_driven_reselection'] and final['actual_c_forwards']==1376
 selected=read(ROOT/'selected.json');a=final['scores']['low']['baseline'];b=final['scores']['low']['candidate']
 assert 0<b['ap50']-a['ap50']<.01 and final['car_ap50_difference_interval99'][0]>0
 manifest=read(ROOT/'confirmation/fresh/manifest.json');lookup={r['name']:r for r in manifest}
 old={r['name']:r for r in read(ROOT/'confirmation/baseline_predictions.json')}
 new={r['name']:r for r in read(ROOT/'confirmation/candidate_predictions.json')}
 for mode,rows in [('baseline',old),('candidate',new)]:
  m=evaluate([row for name,row in rows.items() if lookup[name]['cohort']=='low'])['classes']['car']
  assert m==final['scores']['low'][mode]
 differences=[]
 for name in old:
  if lookup[name]['cohort']!='low':continue
  aa=counted(old[name]);bb=counted(new[name]);differences.append(dict(name=name,old_tp=aa[2],old_fp=aa[3],new_tp=bb[2],new_fp=bb[3],delta_tp=bb[2]-aa[2],delta_fp=bb[3]-aa[3]))
 examples=[]
 for row in [max(differences,key=lambda r:(r['delta_tp'],-r['delta_fp'])),
             max([r for r in differences if r['delta_fp']<=0],key=lambda r:r['delta_tp']),
             min(differences,key=lambda r:(r['delta_tp'],-r['delta_fp'])),
             max(differences,key=lambda r:r['delta_fp'])]:
  if row['name'] not in [r['name'] for r in examples]:examples.append(row)
 font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',13);canvas=Image.new('RGB',(800,len(examples)*280),(15,15,15));engine=Enhancer()
 for y,row in enumerate(examples):
  name=row['name'];_,raw=sensor400(ROOT/'confirmation/fresh/images'/name)
  for x,(label,r) in enumerate([('RAW 4-VIEW',old[name]),('RAW 7-VIEW ZOOM',new[name])]):
   im=Image.fromarray(raw);d=ImageDraw.Draw(im);p,ok,tp,fp=counted(r)
   for box,hit in zip(p,ok):d.rectangle(tuple(box[:4]),outline=(30,255,70) if hit else (255,70,100),width=1)
   canvas.paste(im,(x*400,y*280+40));d=ImageDraw.Draw(canvas)
   d.text((x*400+4,y*280+2),f'{label} / TP {tp} FP {fp}',font=font,fill='white')
   d.text((x*400+4,y*280+20),name,font=font,fill='white')
  scene=out/Path(name).stem;scene.mkdir(exist_ok=True);Image.fromarray(raw).save(scene/'raw.png')
  Image.fromarray(engine.run(raw)).save(scene/'current_display_enhancement.png')
  write(scene/'label_and_detections.json',dict(source=lookup[name],baseline=old[name],candidate=new[name],comparison=row,
   enhancement='Unchanged ABI27 display only. Both detections use raw pixels; no enhancement-attribution claim.'))
 canvas.save(out/'独立测试_增益与退步案例.png');write(out/'案例选择.json',dict(selection='Selected by outcome AFTER frozen evaluation, include best gain, no-extra-FP gain, regression and most extra FP. Not a representative random sample or accuracy estimate.',examples=examples))
 text=f'''# 本轮优化结果：保留稳定版，细节补偿有小幅提升

本轮完成了实际训练和三条优化路线的电脑验证，开发板、SD卡和Flash均未修改。

## 已做的工作

1. **实际神经网络微调**：原有2400个训练源图，其中1060个暗光源图生成增强版本；原图/增强混合训练6轮，保存第2/4/6轮。权重实际更新，但未通过预定开发集门槛。增强输入最好AP50为46.18%，当前原图基线为46.46%。因此未采用这些新权重。
2. **增强辅助确认**：固定神经网络，让增强全图确认原图候选框，同时加入原图自身确认的对照。18组参数×两种辅助视图均未通过；降低误检时会漏掉过多车辆。该失败结果已保留。
3. **小目标细节补偿**：沿用当前已接受的神经网络权重，保留4个原图视图，再增加3个280×168道路裁剪。竖直位置y=152只根据原2400训练图的小车标注选择，横坐标固定0/260/520。增加视图让小车以更大的像素尺寸进入网络；增强显示保持当前ABI27算法。

## 开发集与新确认集分别报告

| 数据集 | 当前4视图AP50 | 7视图候选AP50 | 说明 |
|---|---:|---:|---|
| 已使用的320张暗光开发图 | 46.46% | 48.03% | 用于选择附加视图权重0.65，不能当作新盲测 |
| 新的160张暗光确认图 | {a['ap50']*100:.2f}% | {b['ap50']*100:.2f}% | 参数冻结后测试，未根据结果重新选择 |

不能把两批数据的不同基线交叉相减来计算增益。

新暗光确认集共有1550个汽车标注：

| 指标 | 当前4视图 | 7视图候选 |
|---|---:|---:|
| 精确率 | {a['precision']*100:.2f}% | {b['precision']*100:.2f}% |
| 召回率 | {a['recall']*100:.2f}% | {b['recall']*100:.2f}% |
| 正确检出TP | {a['tp']} | {b['tp']} |
| 误检FP | {a['fp']} | {b['fp']} |
| 漏检FN | {a['fn']} | {b['fn']} |

汽车AP50增加{(b['ap50']-a['ap50'])*100:.2f}个百分点；2000次配对图片bootstrap的99%区间为[{final['car_ap50_difference_interval99'][0]*100:.2f}, {final['car_ap50_difference_interval99'][1]*100:.2f}]个百分点。

这支持该确认样本上的小幅AP改善，代价是误检增加45个、精确率下降约0.36个百分点。虽然漏检减少27个，**仍未达到预先固定的AP至少提升1个百分点门槛，最终验收状态保留为拒绝正式替换**。没有回头降低门槛，也没有拿新测试结果重新挑参数。

另外64张较亮确认图沿用当前4视图原图路径，候选与基线输出逐字节一致。这证明旁路未改输出，不代表7视图方案本身已验证适合所有较亮场景。

## 验证与边界

- 新确认集的原始标注来自固定版本的数据源，按未修改原图平均亮度≤48选暗光组；不等于实测照度。已排除所有记录过的训练、评测、筛选图片前缀组与精确文件哈希。前缀分组也不保证不同前缀的地理场景独立。
- 实际便携C推理运行1376次；全部新旧融合结果与NumPy参考逐字节一致。另对开发集320图的960路裁剪像素和融合结果验证C/NumPy逐字节一致，并检查输入不变和缓冲区边界。
- 这是电脑端实际C程序验证，**尚未编译或下载新的上板固件**。网络图不变，但新视图生成、调度和后处理仍需要板上验证。
- 暗光计算从4次前向增至7次，卷积加速调用预计由204增至357；这是结构计数，不是板上实测耗时。继续采用单帧展示，不宣称实时。
- 本轮新确认集的提升来自原图细节补偿，**不能写成图像增强带来的识别提升**。当前增强仍用于显示，雨夜源图的噪点、光晕和模糊仍存在。

## 当前交付决定

继续保留已验证的ABI27。细节补偿作为有小幅收益的实验方案保存，适合后续做临时上板A/B，以测实际延迟和实现一致性；它尚未获准作为达标版本正式替换。

结果图用绿色标出正确框、粉红色标出误检框，匹配IoU=0.5，置信阈值0.25。图片按结果选择，包含退步和新增误检例；总体结论来自全部160张暗光图。
'''
 (out/'本轮结论.md').write_text(text,encoding='utf-8');(work/'本轮优化与独立测试结论_20261030.md').write_text(text,encoding='utf-8')
 with (out/'独立暗光指标.csv').open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.writer(f);w.writerow(['指标','当前4视图','7视图候选'])
  for name,key in [('AP50','ap50'),('精确率','precision'),('召回率','recall')]:w.writerow([name,a[key],b[key]])
  for name,key in [('TP','tp'),('FP','fp'),('FN','fn')]:w.writerow([name,a[key],b[key]])
 # Copy original machine receipts; keep their rejected status intact.
 for label,root,names in [
  ('01_混合训练',BASE/'road_enhanceadapt_20261030_r1',['protocol.json','secondary_protocol.json','prepared.json','training_config.json','gradient_smoke.json','history.json','training_complete.json','selected.json','delivery_selection.json','实验结论.md']),
  ('02_增强确认',BASE/'road_car_consensus_20261030_r1',['protocol.json','selected.json','c_numpy_proof.json']),
  ('03_细节补偿',ROOT,['protocol.json','selected.json','c_complete.json','confirmation/fresh_result.json','confirmation/inference_policy.json','confirmation/fresh_protocol.json','confirmation/fresh/complete.json'])]:
  for name in names:
   dest=out/label/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/name,dest)
 # Evidence archive with full zoom predictions/manifests, not duplicated datasets.
 bundle=BASE/'road_optimization_evidence_20261030_r3.zip';assert not bundle.exists()
 members={str(p.relative_to(out)).replace('\\','/'):p for p in out.rglob('*') if p.is_file()}
 for name in ['confirmation/baseline_predictions.json','confirmation/candidate_predictions.json','confirmation/fresh/manifest.json','holdout_exclusions.json','chosen_predictions.json','zoom_predictions.json']:
  members['machine_zoom/'+name]=ROOT/name
 for folder in [BASE/'road_enhanceadapt_20261030_r1',BASE/'road_car_consensus_20261030_r1',ROOT]:
  for p in (folder/'source').glob('*'):
   if p.is_file():members['source/'+folder.name+'/'+p.name]=p
 for p in (ROOT/'c_proof/source').iterdir():
  if p.is_file():members['portable_c/'+p.name]=p
 digests={name:sha(p) for name,p in members.items()}
 manifest_text=json.dumps(dict(sha256=digests,board_access=False,sd_written=False,
  scope='Evidence/code archive; requires existing model and datasets by recorded hashes. Not an SD boot package or board-verified release.'),ensure_ascii=False,indent=2)
 with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for name,p in members.items():z.write(p,name)
  z.writestr('manifest.json',manifest_text)
 with zipfile.ZipFile(bundle) as z:
  assert z.testzip() is None
  for name,digest in digests.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
 receipt=dict(status='OPTIMIZATION_EVIDENCE_ARCHIVED_STABLE_ABI27_RETAINED',archive=str(bundle),sha256=sha(bundle),bytes=bundle.stat().st_size,
              entries=len(members)+1,all_member_hashes_verified=True,board_access=False,sd_written=False)
 write(out/'归档校验.json',receipt);write(ROOT/'evidence_archive_verified.json',receipt)
 print('OPTIMIZATION_EVIDENCE_COMPLETE',receipt,flush=True)

if __name__=='__main__':main()
