"""Report all checkpoints and failed gates without selecting attractive examples only."""
import csv,shutil,zipfile
from PIL import Image,ImageDraw,ImageFont
import numpy as np
from road_enhanceadapt_common import *
from road_accuracy_common import sensor400
from road_numpy_eval import correct

def counts(row):
 p=np.asarray(row['detections'],np.float32).reshape(-1,6);p=p[p[:,4]>=.25]
 g=np.asarray(row['ground_truth'],np.float32).reshape(-1,5)
 tp=int(correct(p,g,np.array([.5],np.float32))[0].sum())
 return tp,len(p)-tp

def main():
 selection=read(ROOT/'selected.json');delivery=read(ROOT/'delivery_selection.json');history=read(ROOT/'history.json')
 assert len(history)==6 and read(ROOT/'training_complete.json')['status']=='SIX_EPOCHS_MIXED_RAW_ENHANCED_TRAINING_COMPLETE'
 assert not selection['fresh_inference'] and not delivery['fresh_inference']
 prepared=read(ROOT/'prepared.json');before=selection['records'][0]['initial_raw']
 lines=['# 增强适配训练实验','',
 '本轮已完成实际神经网络微调，板卡、SD卡和Flash未修改。',
 '',f"训练集为原有{prepared['images']}个独立源图，其中{prepared['enhanced_sources']}个暗光源图生成了增强版本；增强版本不算新的独立场景。共6轮，每轮包含2400个全图样本和2400个原图细节样本。暗光全图按固定50%概率采用增强图，其他样本保留原图。",
 '', 'YOLOv5n四类结构、锚框和尺寸保持不变。FP32训练，BN运行统计量冻结；实际权重发生更新。第2、4、6轮检查点均保留。',
 '', '**以下全部是已经使用过的320张暗光图上的开发集结果，不是新的独立测试。** 96张较亮图在候选路由中沿用当前模型，因此不能用这个旁路宣称新模型本身在亮图上不退步。',
 '', '| 检查点/输入 | 汽车AP50 | 精确率 | 召回率 | TP | FP | FN |', '|---|---:|---:|---:|---:|---:|---:|']
 values=[('训练前模型/原图',before)]
 for r in selection['records']:
  values.extend([(f"第{r['epoch']}轮/原图",r['same_model_raw']),(f"第{r['epoch']}轮/增强全图＋原图细节",r['enhanced'])])
 for label,m in values:lines.append(f"| {label} | {m['ap50']*100:.2f}% | {m['precision']*100:.2f}% | {m['recall']*100:.2f}% | {m['tp']} | {m['fp']} | {m['fn']} |")
 lines+=['',f"增强输入主要假设达标：**{selection['qualified']}**。详细门槛保存在selected.json；不以次要结果覆盖失败。",
         '',f"交付候选达标：**{delivery['qualified']}**；候选输入方式：`{delivery['input_mode']}`。原图回退规则在训练中、任何候选验证之前单独登记，记录在secondary_protocol.json。"]
 if delivery['qualified']:
  lines+=['',f"冻结候选为第{delivery['chosen']['epoch']}轮。这里只是开发集筛选通过，仍需新的未使用图片确认；不能据此宣称已在新场景中提升。"]
 else:
  lines+=['','本轮没有找到符合全部预定条件的交付候选。继续保留已验证的ABI27程序；未把不合格模型下载到板卡，也未消耗新的独立测试集。']
 if (ROOT/'confirmation/fresh_result.json').exists():
  fresh=read(ROOT/'confirmation/fresh_result.json')
  lines+=['',f"新确认集最终结论：`{fresh['status']}`。详见confirmation/fresh_result.json。"]
 lines+=['','下一轮若继续改变训练或增强方案，必须把本轮结果视为开发经验，并在新的确认数据上检验。不能反复试过同一批图片后仍称其为盲测。']
 text='\n'.join(lines)+'\n';(ROOT/'实验结论.md').write_text(text,encoding='utf-8')
 work=Path(__file__).resolve().parents[2];(work/'增强适配训练结果_20261030.md').write_text(text,encoding='utf-8')
 with (ROOT/'开发集指标.csv').open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.writer(f);w.writerow(['输入','AP50_percent','precision_percent','recall_percent','TP','FP','FN'])
  for label,m in values:w.writerow([label,*[m[k]*100 for k in ['ap50','precision','recall']],*[m[k] for k in ['tp','fp','fn']]])
 # A diagnostic sheet uses a prespecified checkpoint if none qualifies;
 # choosing examples by results is disclosed and not used as accuracy evidence.
 epoch=delivery['chosen']['epoch'] if delivery['qualified'] else 6
 samples=read(ROOT/'development'/f'epoch{epoch}/predictions.json');diff=[]
 for r in samples:
  raw=counts(r['raw']);enh=counts(r['enh']);diff.append(dict(name=r['name'],dtp=enh[0]-raw[0],dfp=enh[1]-raw[1],raw=raw,enh=enh))
 chosen=[]
 for row in [max(diff,key=lambda z:(z['dtp'],-z['dfp'])),min(diff,key=lambda z:(z['dtp'],-z['dfp'])),max(diff,key=lambda z:z['dfp'])]:
  if row['name'] not in [r['name'] for r in chosen]:chosen.append(row)
 canvas=Image.new('RGB',(800,len(chosen)*280),(15,15,15));font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',13)
 smap={r['name']:r for r in samples};data=BASE/'road_brightness_route_20261030_r1/fresh'
 for y,r in enumerate(chosen):
  _,raw=sensor400(data/'images'/r['name']);enh=np.asarray(Image.open(AUDIT/'enhanced'/r['name']))
  for x,(key,im) in enumerate([('raw',raw),('enh',enh)]):
   frame=Image.fromarray(im);draw=ImageDraw.Draw(frame)
   for box in smap[r['name']][key]['detections']:
    if box[4]>=.25:draw.rectangle(tuple(box[:4]),outline=(0,255,80),width=1)
   canvas.paste(frame,(x*400,y*280+40));draw=ImageDraw.Draw(canvas);count=r[key]
   draw.text((x*400+3,y*280+2),f'EPOCH {epoch} {key.upper()} NN / TP {count[0]} FP {count[1]}',fill='white',font=font)
   draw.text((x*400+3,y*280+20),r['name'],fill='white',font=font)
 canvas.save(ROOT/'diagnostic_examples.png');write(ROOT/'diagnostic_selection.json',dict(epoch=epoch,examples=chosen,selected_by_outcome=True,not_accuracy_evidence=True))
 shutil.copy2(Path(__file__),ROOT/'source'/Path(__file__).name)
 print('ENHANCEADAPT_REPORT_READY',selection['qualified'],delivery['qualified'],flush=True)

if __name__=='__main__':main()
