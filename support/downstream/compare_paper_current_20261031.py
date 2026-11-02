"""Known-photo reference check; not author RTL or a new accuracy evaluation."""
from pathlib import Path
import hashlib, json, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from road_retinex_project import paper_reference

BASE=Path('E:/FPGA_Enhance_Work')
OUT=BASE/'road_paper_recheck_20261031_r1'

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v): p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def unpack(p):
    x=np.fromfile(p,'<u4').reshape(240,400)
    return np.stack([(x>>s)&255 for s in (0,8,16)],2).astype(np.uint8)
def mean(a):
    v=a.astype(np.float64)
    return float(((54*v[:,:,0]+183*v[:,:,1]+19*v[:,:,2])/256).mean())

def main():
    assert not OUT.exists()
    OUT.mkdir();(OUT/'source').mkdir()
    receipt=BASE/'road_car_balanced_20261030_r1/board_candidate/board_verified.json'
    evidence=Path(json.loads(receipt.read_text(encoding='utf-8'))['evidence'])
    items=[('NIGHT ROAD A',evidence/'photo_0/raw.u32',evidence/'photo_0/enhanced.u32'),
           ('NIGHT ROAD B',evidence/'photo_1/raw.u32',evidence/'photo_1/enhanced.u32'),
           ('DARK TRAFFIC',BASE/'road_shadowlift_20261030_r1/dark_traffic/raw.u32',BASE/'road_shadowlift_20261030_r1/dark_traffic/final.u32')]
    write(OUT/'protocol.json',dict(status='KNOWN_SCENE_REFERENCE_COMPARISON',
       paper_doi='10.1109/TCSII.2024.3361561',
       reference='Independent floating implementation of equations2-12,11x11,sigma4,exp(-abs(d)/32),mirror reflect101. No authors RTL, piecewise weight approximation or fixed-point equivalence claimed.',
       reference_tone='sqrt(F*(2-F));sameRGBgain;no additional denoising, highlight fades, exposure targets, gain caps or alpha blending.',
       sources=[dict(name=n,raw=str(r),current=str(c),raw_sha256=sha(r),current_sha256=sha(c)) for n,r,c in items],
       scope='Previously inspected development images, not blind or paired reference-exposure samples. Means describe brightness only, not quality/accuracy. No detector changes or accuracy claim.',
       hardware_access=False,sd_written=False))
    for p in [Path(__file__),Path(__file__).with_name('road_retinex_project.py')]:shutil.copy2(p,OUT/'source'/p.name)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',16)
    canvas=Image.new('RGB',(1200,840),(18,18,18));draw=ImageDraw.Draw(canvas);rows=[]
    for i,(name,r,c) in enumerate(items):
        raw=unpack(r);current=unpack(c);paper,stat=paper_reference(raw)
        folder=OUT/f'scene_{i}';folder.mkdir()
        for col,(tag,im) in enumerate([('RAW',raw),('PAPER FLOAT REFERENCE',paper),('CURRENT BOARD DISPLAY',current)]):
            Image.fromarray(im).save(folder/f'{col}.png')
            canvas.paste(Image.fromarray(im),(col*400,i*280+40))
            draw.text((col*400+5,i*280+2),f'{name} / {tag}',font=font,fill='white')
            draw.text((col*400+5,i*280+21),f'Mean Y {mean(im):.2f} (brightness only)',font=font,fill='white')
        rows.append(dict(name=name,mean_raw=mean(raw),mean_paper=mean(paper),mean_current=mean(current),paper=stat))
    canvas.save(OUT/'comparison.png')
    # Numerical formula check for a flat RGB image: F=max(R,G,B)/255.
    checks=[]
    for value in [0,1,4,16,64,128,255]:
        a=np.full((240,400,3),value,np.uint8);z,_=paper_reference(a)
        expected=0 if value==0 else int(np.floor(255*np.sqrt((value/255)*(2-value/255))+.5))
        assert np.all(z==expected),(value,expected,np.unique(z))
        checks.append(dict(input=value,expected=expected,output=int(z[0,0,0])))
    write(OUT/'results.json',dict(rows=rows,flat_formula_checks=checks,source_sha256=sha(OUT/'source/road_retinex_project.py'),hardware_access=False,sd_written=False))
    print('PAPER_CURRENT_COMPARISON_READY',str(OUT/'comparison.png'))
    print(json.dumps(rows))

if __name__=='__main__':main()
