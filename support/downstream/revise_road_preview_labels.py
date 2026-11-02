"""Improve label legibility; retain every box and all measured predictions."""
from pathlib import Path
import hashlib,json,shutil,zipfile
from PIL import Image,ImageDraw,ImageFont
ROOT=Path('E:/FPGA_Enhance_Work/road_detection_20261026');OUT=ROOT/'release';HERE=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    names=['person','car','truck','bus'];colors=[(255,170,30),(0,230,255),(220,130,255),(60,255,110)];font=lambda n:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n)
    selected=read(ROOT/'test/evaluation_protocol.json')['display_examples']
    pred={v:{r['name']:r for r in read(ROOT/'test'/f'{v}_predictions.json')} for v in ['raw400','multinex400','protected400']}
    for index,name in enumerate(selected,1):
        canvas=Image.new('RGB',(1248,420),'#f4f6f8');d=ImageDraw.Draw(canvas)
        d.text((20,8),'电脑离线检测｜真实道路图｜同一训练后模型与阈值',font=font(25),fill='#172436')
        d.text((20,45),f'{name}    时段：{pred["raw400"][name]["timeofday"]}',font=font(18),fill='#44546a')
        for i,(view,title) in enumerate(zip(['raw400','multinex400','protected400'],['原图 RAW','固定 Multinex 增强','全局亮度保护输出'])):
            x=16+i*412;d.text((x,77),title,font=font(22),fill='#172436')
            image=Image.open(ROOT/'test/enhancement_inputs'/(Path(name).stem+'.'+view+'.png')).convert('RGB');draw=ImageDraw.Draw(image)
            for p in pred[view][name]['detections']:
                if p[4]<.25:continue
                x1,y1,x2,y2,confidence,k=p;k=int(k);color=colors[k];draw.rectangle((x1,y1,x2,y2),outline=color,width=2)
                if x2-x1>=55 and y2-y1>=18:
                    label=f'{names[k]} {confidence:.2f}';box=draw.textbbox((0,0),label,font=font(11));tx=min(max(0,x1),400-(box[2]-box[0]))
                    draw.text((tx,max(0,y1-13)),label,fill=color,font=font(11),stroke_width=1,stroke_fill=(0,0,0))
            canvas.paste(image,(x,112));d.text((x,355),f'匹配标注目标：{len(pred[view][name]["matched_gt"])}',font=font(18),fill='#44546a')
        d.text((20,390),'颜色：橙=行人，青=汽车，紫=卡车，绿=公交车；小目标仅画框，所有预测均计入评测。',font=font(18),fill='#44546a')
        canvas.save(OUT/'效果图'/f'{index:02d}_{Path(name).stem}.png')
    for name in ['finish_road_detector.py','revise_road_preview_labels.py']:
        shutil.copy2(HERE/name,OUT/'训练评测脚本'/name)
    files=sorted(p for p in OUT.rglob('*') if p.is_file() and p.name!='manifest.json')
    manifest=[dict(path=p.relative_to(OUT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in files]
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    archive=ROOT.parent/'road_detector_first_round_20261026_r1.zip';assert not archive.exists()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in files+[OUT/'manifest.json']:z.write(p,p.relative_to(OUT).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and all(hashlib.sha256(z.read(v['path'])).hexdigest()==v['sha256'] for v in manifest)
    (ROOT/'release.json').write_text(json.dumps(dict(archive=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,all_hashes_verified=True),indent=2),encoding='utf-8')
    print('ROAD_PREVIEW_LABELS_REVISED_ALL_BOXES_RETAINED',archive,sha(archive),flush=True)
if __name__=='__main__':main()
