"""Real board cases, letterbox-aware labels, with all failures retained."""
from pathlib import Path
import math,time
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from prepare_road_scene_acceptance import LAB,PACK
from photo_station_core import process_photo,STAGING,verify_return
from road_numpy_eval import correct
from car_roi_delivery_common import read,write,sha

def mapped_truth(row,meta):
    labels=np.array([[float(v) for v in line.split()] for line in Path(row['local_label']).read_text().splitlines() if line],np.float32).reshape(-1,5)
    a=labels[labels[:,0]==1];assert len(a)==row['class_counts'][1]
    nw,nh=meta['resized_size'];px,py=meta['padding_xy']
    g=np.zeros((len(a),5),np.float32);g[:,0]=1
    g[:,1]=(a[:,1]-a[:,3]/2)*nw/2+px/2;g[:,3]=(a[:,1]+a[:,3]/2)*nw/2+px/2
    g[:,2]=(a[:,2]-a[:,4]/2)*nh/2+py/2;g[:,4]=(a[:,2]+a[:,4]/2)*nh/2+py/2
    g[:,[1,3]]=np.clip(g[:,[1,3]],0,400);g[:,[2,4]]=np.clip(g[:,[2,4]],0,240)
    return g

def assess(row,result):
    out=Path(result['output']);packet=Path(result['packet_evidence']);p=np.fromfile(packet/'boxes.f32','<f4').reshape(-1,6)
    assert np.all(p[:,4]>=.25) and np.all(p[:,5]==1)
    g=mapped_truth(row,result['input']);ok,matched=correct(p,g,np.array([.5],np.float32));ok=ok[:,0];missed=[i for i in range(len(g)) if i not in matched[0]]
    tp=int(ok.sum());fp=len(p)-tp;fn=len(g)-tp
    raw=np.asarray(Image.open(out/'02_板上原图400.png').convert('RGB'));enh=np.asarray(Image.open(out/'03_板上增强400.png').convert('RGB'))
    px,py=result['input']['padding_xy'];nw,nh=result['input']['resized_size'];mask=np.zeros((240,400),bool)
    mask[math.ceil(py/2):math.floor((py+nh)/2),math.ceil(px/2):math.floor((px+nw)/2)]=True
    luma=lambda x:(x.astype(np.float32)*np.array([54,183,19],np.float32)).sum(2)/256
    y0,y1=luma(raw),luma(enh);shadow=mask&(y0<32)
    record=dict(case=row['case'],title=row['title'],image_name=row['name'],image_sha256=row['image_sha256'],label_sha256=row['label_sha256'],
        cars_annotated=len(g),boxes_returned=len(p),tp=tp,fp=fp,fn=fn,iou_threshold=.5,confidence_threshold=.25,
        precision=tp/len(p) if len(p) else None,recall=tp/len(g) if len(g) else None,
        raw_mean_luma=float(y0[mask].mean()),enhanced_mean_luma=float(y1[mask].mean()),
        raw_shadow_mean_luma=float(y0[shadow].mean()) if shadow.any() else None,enhanced_shadow_mean_luma=float(y1[shadow].mean()) if shadow.any() else None,
        board_seconds=result['board_processing_seconds'],wall_seconds=result['wall_seconds'],
        ground_truth_board400=g.tolist(),prediction_correct=ok.tolist(),missed_ground_truth_indices=missed,
        raw_input_detection=True,enhancement_input_accuracy_claimed=False,source_result=result,output=str(out))
    write(out/'场景核对.json',record)
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',18);small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',14)
    def annotate(a,left):
        im=Image.fromarray(a);d=ImageDraw.Draw(im)
        if left:
            for i,(_,x1,y1,x2,y2) in enumerate(g):
                d.rectangle((float(x1),float(y1),float(x2),float(y2)),outline=(255,210,60),width=1)
                d.text((float(x1),max(0,float(y1)-11)),f'G{i+1}',fill=(255,210,60))
        else:
            for i,b in enumerate(p):
                color=(65,245,180) if ok[i] else (255,110,150)
                d.rectangle(tuple(float(v) for v in b[:4]),outline=color,width=1)
                d.text((float(b[0]),max(0,float(b[1])-11)),('TP' if ok[i] else 'FP')+str(i+1),fill=color)
            for i in missed:
                _,x1,y1,x2,y2=g[i]
                d.rectangle((float(x1),float(y1),float(x2),float(y2)),outline=(255,210,60),width=1)
                d.text((float(x1),max(0,float(y1)-11)),f'FN{i+1}',fill=(255,210,60))
        return im.resize((480,288),Image.Resampling.BILINEAR)
    canvas=Image.new('RGB',(1000,425),(12,18,28));d=ImageDraw.Draw(canvas)
    d.text((16,10),f"{row['case']:02d}  {row['title']}   标注{len(g)}辆 / 正确{tp} / 误检{fp} / 漏检{fn}",font=font,fill=(235,243,250))
    d.text((16,46),'原图 + 数据集汽车标注（黄）',font=small,fill=(255,210,60))
    d.text((516,46),'板上增强 + 检出核对（绿TP / 红FP / 黄FN）',font=small,fill=(200,220,235))
    canvas.paste(annotate(raw,True),(10,78));canvas.paste(annotate(enh,False),(510,78))
    d.text((16,378),f"板上{result['board_processing_seconds']:.1f}秒  |  原图检测，增强用于显示  |  核对图标注由电脑绘制",font=small,fill=(155,175,195))
    canvas.save(out/'08_标注与检出核对.png');return record

def report(records):
    records=sorted(records,key=lambda r:r['case']);lines=[(PACK/'说明.md').read_text(encoding='utf-8'),'','## 实板结果','',
        '| 编号 | 场景 | 标注 | 正确检出 | 误检 | 漏检 | 板上耗时 | 原图→增强平均亮度 |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for r in records:lines.append(f"| {r['case']:02d} | {r['title']} | {r['cars_annotated']} | {r['tp']} | {r['fp']} | {r['fn']} | {r['board_seconds']:.1f}秒 | {r['raw_mean_luma']:.1f}→{r['enhanced_mean_luma']:.1f} |")
    lines+=['','亮度均值只描述提亮幅度，不代表细节恢复或画质评分。增强结果来自板卡；核对图中的数据集标注、TP/FP/FN文字由电脑绘制。',
        '当前汽车检测输入为原图，图中的同一组检测框显示在增强图上。本组结果不构成增强后检测准确率提高的证据。','',
        '## 查看方法','','“测试照片”保存原始图片，“标注”保存对应汽车等类别的原始标注。',
        '每个“板上结果”子文件夹内，07是原图和板上增强的展示对照，08是含人工数据集标注的检出核对图，场景核对.json保留逐框结果和实际读回路径。','']
    (PACK/'实板验收结果.md').write_text('\n'.join(lines),encoding='utf-8')
    contact=Image.new('RGB',(1000,425*len(records)),(12,18,28))
    for i,r in enumerate(records):
        with Image.open(Path(r['output'])/'08_标注与检出核对.png') as im:contact.paste(im,(0,425*i))
    contact.save(PACK/'四场景核对总览.png')
    return records

def main():
    protocol=read(LAB/'protocol.json');assert protocol['status']=='CASES_FROZEN_BEFORE_BOARD_OUTPUTS'
    assert not (LAB/'complete.json').exists(),'Preserve completed acceptance records'
    write(LAB/'execution_policy.json',dict(order=[1,2,4,3],purpose='Leave the typical road case visible last; report all four, without outcome-based replacement.',
        model_changed=False,threshold_changed=False,sd_written=False))
    (PACK/'板上结果').mkdir(exist_ok=True);records=[]
    try:
        for number in [1,2,4,3]:
            row=next(r for r in protocol['cases'] if r['case']==number)
            assert sha(row['local_image'])==row['image_sha256'] and sha(row['local_label'])==row['label_sha256']
            print('ROAD_CASE_BEGIN',number,row['title'],row['name'],flush=True)
            receipt=LAB/f'case{number:02d}_verified.json'
            if receipt.exists():
                record=read(receipt);result=record['source_result'];packet=Path(result['packet_evidence'])
                assert record['image_sha256']==row['image_sha256'] and record['label_sha256']==row['label_sha256']
                verify_return(packet,packet.parent/'prepared',kind=5)
                print('ROAD_CASE_REUSED_VERIFIED_PACKET',number,flush=True)
            else:
                result=process_photo(row['display_image'],output_root=PACK/'板上结果',notify=lambda s:print('ROAD_PROGRESS',number,s,flush=True))
                record=assess(row,result);write(receipt,record)
            records.append(record)
            print('ROAD_CASE_RESULT',number,'GT',record['cars_annotated'],'TP',record['tp'],'FP',record['fp'],'FN',record['fn'],'SECONDS',round(record['board_seconds'],2),flush=True)
        write(STAGING/'gui_last_result.json',result)
        ordered=report(records);proof=dict(status='FOUR_FIXED_ROAD_CASES_ACTUAL_BOARD_VERIFIED',cases=ordered,
            protocol_sha256=sha(LAB/'protocol.json'),representative_accuracy_study=False,new_independent_data=False,
            model_changed=False,threshold_changed=False,sd_written=False,all_chosen_cases_reported=True)
        write(LAB/'complete.json',proof);write(PACK/'实板验收记录.json',proof)
        print('ROAD_SCENE_ACCEPTANCE_COMPLETE',PACK,flush=True)
    except Exception as e:
        write(LAB/'incomplete.json',dict(status='INCOMPLETE_NO_FOUR_CASE_PASS_CLAIM',error=str(e),completed_cases=[r['case'] for r in records],sd_written=False))
        raise

if __name__=='__main__':main()
