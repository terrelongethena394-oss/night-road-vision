"""Ground-truth-backed positive AND negative examples; aggregate result remains failed."""
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from road_enhanced_detection_common import BASE,read,write
from road_numpy_eval import correct
import road_accuracy_common as ac
ROOT=BASE/'road_allview_enhance_20261031_r1'
def measure(r):
    p=np.asarray(r['detections'],np.float32).reshape(-1,6);p=p[(p[:,4]>=.25)&(p[:,5]==1)];g=np.asarray(r['ground_truth'],np.float32).reshape(-1,5);ok,matched=correct(p,g,np.array([.5],np.float32));tp=int(ok[:,0].sum());return dict(p=p,g=g,ok=ok[:,0],missed=set(range(len(g)))-matched[0],tp=tp,fp=len(p)-tp,fn=len(g)-tp)
def main():
    pred=read(ROOT/'predictions.json');rows=read(ROOT/'development_manifest.json');manifest={r['name']:r for r in rows};pairs=[]
    for a,b in zip(pred['raw'],pred['gamma080']):
        assert a['name']==b['name'];x=measure(a);y=measure(b);pairs.append((a['name'],x,y))
    positive=sorted([z for z in pairs if z[2]['tp']>z[1]['tp'] and z[2]['fp']<=z[1]['fp']],key=lambda z:(z[2]['tp']-z[1]['tp'],z[1]['fp']-z[2]['fp']),reverse=True)[:2]
    negative=sorted([z for z in pairs if z[2]['tp']<z[1]['tp']],key=lambda z:(z[1]['tp']-z[2]['tp'],z[2]['fp']-z[1]['fp']),reverse=True)[:2]
    chosen=[('增强有利的开发例',z) for z in positive]+[('增强不利的开发例',z) for z in negative];assert len(chosen)==4
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',17);small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',13);canvas=Image.new('RGB',(820,4*300+92),'#151922');d=ImageDraw.Draw(canvas)
    d.text((10,5),'按结果选择的正例与反例，不代表整体提升；全部为已使用开发图',font=font,fill='white');d.text((10,31),'绿：正确检出  橙：误检  紫：漏检标注；固定置信度0.25，IoU0.5',font=small,fill='#e0dfec');d.text((10,55),'左：原图检测                         右：轻度增强后检测（相同模型/7视图）',font=font,fill='white');receipt=[]
    for i,(kind,(name,raw,enh)) in enumerate(chosen):
        r=manifest[name];_,a=ac.sensor400(Path(r['data_root'])/'images'/name);images=[a,ac.gamma(a,'gamma080')];top=92+i*300;d.text((10,top),kind+' '+name,font=small,fill='#e0dfec')
        for j,(im,info) in enumerate(zip(images,[raw,enh])):
            p=Image.fromarray(im);pd=ImageDraw.Draw(p)
            for b,ok in zip(info['p'],info['ok']):pd.rectangle(tuple(map(float,b[:4])),outline='#4fe397' if ok else '#ff9c38',width=1)
            for k in info['missed']:pd.rectangle(tuple(map(float,info['g'][k,1:])),outline='#f26dff',width=1)
            canvas.paste(p,(10+j*410,top+22));d.text((10+j*410,top+265),f"TP={info['tp']}   FP={info['fp']}   FN={info['fn']}",font=font,fill='white')
        receipt.append(dict(name=name,selection=kind,raw={k:raw[k] for k in ['tp','fp','fn']},enhanced={k:enh[k] for k in ['tp','fp','fn']}))
    workspace=Path(__file__).resolve().parents[2];out=workspace/'增强识别优化验证_20261031';out.mkdir(exist_ok=True);canvas.save(out/'增强正例与反例.png');write(out/'图例选择记录.json',dict(scope='Explicit result-selected positive and negative development examples, not independent proof or overall improvement.',images=receipt));print(out/'增强正例与反例.png')
if __name__=='__main__':main()
