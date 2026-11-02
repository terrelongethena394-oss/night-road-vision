"""Fixed-hash development diagnostics; not a substitute for full-set metrics."""
from pathlib import Path
import hashlib
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from road_enhanced_detection_common import BASE,read,write
from prove_student_fusion_20261031 import Engine
import road_accuracy_common as ac
ROOT=BASE/'road_allview_enhance_20261031_r1'
def main():
    rows=sorted(read(ROOT/'development_manifest.json'),key=lambda r:hashlib.sha256(('visual20261031'+r['name']).encode()).hexdigest())[:4]
    names={r['name'] for r in rows};pred=read(ROOT/'predictions.json');boxes={m:{r['name']:r['detections'] for r in pred[m] if r['name'] in names} for m in ['raw','gamma080']};del pred
    e=Engine();font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',16);small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',13)
    canvas=Image.new('RGB',(1200,4*286+66),'#181b23');d=ImageDraw.Draw(canvas)
    for j,t in enumerate(['RAW + RAW detection','ABI29 display + RAW detection','Gamma 0.8 + enhanced detection']):d.text((j*400+10,10),t,font=font,fill='white')
    receipt=[]
    for i,r in enumerate(rows):
        _,raw=ac.sensor400(Path(r['data_root'])/'images'/r['name']);views=[raw,e.run(raw),ac.gamma(raw,'gamma080')];top=44+i*286
        d.text((10,top),r['name']+' [development, not independent]',font=small,fill='#d8dfeb')
        for j,a in enumerate(views):
            p=Image.fromarray(a);pd=ImageDraw.Draw(p);bb=np.asarray(boxes['gamma080' if j==2 else 'raw'][r['name']]).reshape(-1,6);bb=bb[(bb[:,5]==1)&(bb[:,4]>=.25)]
            for b in bb:pd.rectangle(tuple(float(v) for v in b[:4]),outline='#54ecae',width=1)
            canvas.paste(p,(j*400,top+22));d.text((j*400+8,top+263),'cars at fixed conf 0.25: '+str(len(bb)),font=small,fill='#c9d4e5')
        receipt.append(dict(name=r['name'],selection='First4 by SHA256 visual20261031+name; no visual/score selection.'))
    target=ROOT/'diagnostic_gallery.png';canvas.save(target);write(ROOT/'diagnostic_gallery_receipt.json',receipt);print(target)
if __name__=='__main__':main()
