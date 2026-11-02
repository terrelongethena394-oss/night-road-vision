"""Same-input visual comparisons; freeze candidates before looking at outputs."""
from pathlib import Path
import json, hashlib, shutil
import numpy as np
from PIL import Image, ImageDraw
from road_retinex_noiseguard import enhance, PRESETS
from study_road_local_enhance import metric

ROOT = Path('E:/FPGA_Enhance_Work/road_retinex_noiseguard_20261029_r2')
OLD = Path('E:/FPGA_Enhance_Work/road_retinex_detail_20261029_r1')
REF = Path('E:/FPGA_Enhance_Work/road_project_retinex_20261029_r3')
NAMES = ['a2a8d23a-90b0b3df', 'a32543af-7cf90f4a', 'c81ff2c0-420a8956', 'b8acc534-d5b64200', 'baa88157-4026332f']

def write(p, v):
    p.write_text(json.dumps(v, ensure_ascii=False, indent=2), encoding='utf-8')

def sheet(images, labels, path, crop=None):
    items = [Image.fromarray(z).crop(crop) if crop else Image.fromarray(z) for z in images]
    if crop: items = [im.resize((im.width*2, im.height*2), Image.Resampling.NEAREST) for im in items]
    w, h = items[0].size
    out = Image.new('RGB', (w*len(items), h+28), 'white')
    d = ImageDraw.Draw(out)
    for i, (im, name) in enumerate(zip(items, labels)):
        out.paste(im, (i*w, 28)); d.text((i*w+5, 6), name, fill='black')
    out.save(path)

def main():
    assert not ROOT.exists(); ROOT.mkdir()
    src = Path(__file__).with_name('road_retinex_noiseguard.py')
    write(ROOT/'protocol.json', dict(status='FROZEN_BEFORE_OUTPUTS', presets=PRESETS, default='guard_light', known_development_images=NAMES, previous_revision='r1 smoothstep protection retained in its experiment folder. Rational protection avoids steep near-black contrast; h10 allows modest luminance denoising.', selection='Visual assessment of same-input detail/noise tradeoff. Paired20 descriptive regression only; no blind-test or detector-improvement claim.', source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(), hardware_access=False, sd_written=False))
    shutil.copy2(src, ROOT/src.name)
    rows=[]
    for name in NAMES:
        folder=ROOT/name; folder.mkdir()
        raw=np.array(Image.open(OLD/name/'raw.png').convert('RGB'))
        old=np.array(Image.open(OLD/name/'detail_balanced.png').convert('RGB'))
        Image.fromarray(raw).save(folder/'raw.png')
        images=[raw,old]; labels=['RAW','ABI21']
        for preset in PRESETS:
            z,s=enhance(raw,preset); Image.fromarray(z).save(folder/(preset+'.png'))
            rows.append(dict(name=name,preset=preset,**s)); images.append(z);labels.append(preset)
        sheet(images,labels,folder/'comparison.png')
        sheet(images,labels,folder/'buildings2x.png',(200,0,400,100))
        sheet(images,labels,folder/'road2x.png',(80,115,320,220))
        print('NOISEGUARD_CASE',name,flush=True)
    scores=[]
    for folder in sorted((REF/'paired_regression').iterdir()):
        if not folder.is_dir(): continue
        raw=np.array(Image.open(folder/'raw.png').convert('RGB')); gt=np.array(Image.open(folder/'normal_reference.png').convert('RGB'))
        z,_=enhance(raw,'guard_light'); scores.append(dict(name=folder.name,**metric(z,gt)))
    write(ROOT/'paired20_regression.json',dict(images=len(scores),psnr=float(np.mean([r['psnr'] for r in scores])),ssim=float(np.mean([r['ssim'] for r in scores])),rows=scores,not_new_blind_test=True))
    write(ROOT/'complete.json',dict(status='OFFLINE_CANDIDATES_READY_FOR_VISUAL_REVIEW',rows=rows,hardware_access=False,sd_written=False))
    print('NOISEGUARD_OFFLINE_COMPLETE',flush=True)

if __name__=='__main__': main()
