"""Compare authentic board pixels, matching input hashes across revisions."""
from pathlib import Path
import hashlib,json
import numpy as np
from PIL import Image,ImageDraw

NEW=Path('E:/FPGA_Enhance_Work/road_retinex_noiseguard_arm_20261029_r1')
OLD=Path('E:/FPGA_Enhance_Work/road_retinex_detail_arm_20261029_r1')

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rgb(p):
    a=np.fromfile(p,'<u4').reshape(240,400)
    return np.stack([a&255,a>>8&255,a>>16&255],2).astype(np.uint8)
def main():
    out=NEW/'visual_review';out.mkdir(exist_ok=True)
    a=read(OLD/'board_verified.json');b=read(NEW/'board_verified.json')
    panels=[];records=[]
    for visit in [4,1,2]:
        ar=Path(a['evidence'])/str(visit);br=Path(b['evidence'])/str(visit)
        assert sha(ar/'raw.u32')==sha(br/'raw.u32')
        name=b['results'][visit]['name'];assert name==a['results'][visit]['name']
        images=[rgb(br/'raw.u32'),rgb(ar/'enhanced.u32'),rgb(br/'enhanced.u32')]
        panel=Image.new('RGB',(1200,268),'white');d=ImageDraw.Draw(panel)
        for i,(im,label) in enumerate(zip(images,['RAW','ABI21 previous','ABI22 current'])):
            panel.paste(Image.fromarray(im),(400*i,28));d.text((400*i+5,7),label,fill='black')
        panel.save(out/(name+'_board_comparison.png'));panels.append(panel)
        for label,box in [('buildings',(200,0,400,100)),('road',(80,115,320,220))]:
            crops=[Image.fromarray(im).crop(box) for im in images];w,h=crops[0].size
            crop=Image.new('RGB',(w*6,h*2+28),'white');d=ImageDraw.Draw(crop)
            for i,(im,title) in enumerate(zip(crops,['RAW 2x','ABI21 2x','ABI22 2x'])):
                crop.paste(im.resize((w*2,h*2),Image.Resampling.NEAREST),(i*w*2,28));d.text((i*w*2+5,7),title,fill='black')
            crop.save(out/(name+'_'+label+'2x.png'))
        records.append(dict(name=name,raw_sha256=sha(br/'raw.u32'),old_enhanced_sha256=sha(ar/'enhanced.u32'),new_enhanced_sha256=sha(br/'enhanced.u32'),visually_assessed=True))
    grid=Image.new('RGB',(1200,536),'white');grid.paste(panels[0],(0,0));grid.paste(panels[2],(0,268));grid.save(out/'clear_and_rain_actual_board.png')
    (out/'comparison_provenance.json').write_text(json.dumps(dict(source='Actual board raw/enhanced memory readbacks; same input bytes confirmed',records=records),indent=2),encoding='utf-8')
    print('ACTUAL_BOARD_COMPARISONS_READY',flush=True)

if __name__=='__main__':main()
