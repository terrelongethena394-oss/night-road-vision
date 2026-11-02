"""Exposure-constrained prototypes from actual baseline board pixels.

These previews are explicitly computer prototypes, never board readbacks.
"""
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from car_roi_delivery_common import BASE,read,write,sha

ROOT=BASE/'natural_exposure_guard_20261101_r1'
CASES=BASE/'road_scene_acceptance_20261031_r1'
PROFILES={'natural55':dict(gamma=.55,gain=5.5,black=12,highlight_low=130,highlight_high=245),
          'natural60':dict(gamma=.60,gain=4.5,black=12,highlight_low=130,highlight_high=245)}

def table(profile):
    y=np.arange(256,dtype=np.float64);smooth=lambda x:np.clip(x,0,1)**2*(3-2*np.clip(x,0,1))
    desired=255*np.power(y/255,profile['gamma'])
    desired=y+(desired-y)*smooth(y/profile['black'])*(1-smooth((y-profile['highlight_low'])/(profile['highlight_high']-profile['highlight_low'])))
    desired=np.clip(np.minimum(desired,y*profile['gain']),y,255)
    return np.floor(desired*256+.5).astype(np.uint16)

def apply(raw,enh,lut):
    a=raw.astype(np.uint64);b=enh.astype(np.uint64);weights=np.array([54,183,19],np.uint64)
    y0=(a*weights).sum(2);y1=(b*weights).sum(2);target=np.maximum(y0,lut[((y0+128)>>8).astype(np.int32)].astype(np.uint64))
    active=y1>target;result=enh.copy()
    den=y1[active]-y0[active];w0=y1[active]-target[active];w1=target[active]-y0[active]
    result[active]=((a[active]*w0[:,None]+b[active]*w1[:,None]+(den//2)[:,None])//den[:,None]).astype(np.uint8)
    assert np.all((result.astype(np.uint64)*weights).sum(2)<=target+128)
    assert np.all(result>=np.minimum(raw,enh)) and np.all(result<=np.maximum(raw,enh))
    return result

def main():
    assert not ROOT.exists();ROOT.mkdir();(ROOT/'computer_prototypes').mkdir()
    records=[];font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14)
    for name,profile in PROFILES.items():
        lut=table(profile);lut.tofile(ROOT/f'{name}.u16');canvas=Image.new('RGB',(1200,1120),(12,18,28));d=ImageDraw.Draw(canvas)
        for i,case in enumerate(read(CASES/'complete.json')['cases']):
            out=Path(case['output']);raw=np.array(Image.open(out/'02_板上原图400.png').convert('RGB'));old=np.array(Image.open(out/'03_板上增强400.png').convert('RGB'))
            new=apply(raw,old,lut);Image.fromarray(new).save(ROOT/'computer_prototypes'/f'{name}_case{case["case"]:02d}.png')
            for col,(label,img) in enumerate([('RAW BOARD INPUT',raw),('CURRENT BOARD ENHANCEMENT',old),('COMPUTER PROTOTYPE '+name,new)]):
                canvas.paste(Image.fromarray(img),(col*400,i*280+40));d.text((col*400+5,i*280+5),f"CASE {case['case']}  {label}",font=font,fill='white')
            y=lambda a:float((a.astype(np.float32)*np.array([54,183,19],np.float32)).sum(2).mean()/256)
            records.append(dict(profile=name,case=case['case'],raw_y=y(raw),old_y=y(old),new_y=y(new),baseline_packet=case['source_result']['packet_evidence'],prototype_only=True))
        canvas.save(ROOT/f'{name}_computer_comparison.png')
    rng=np.random.default_rng(2026110101);raw=rng.integers(0,256,(240,400,3),dtype=np.uint8);old=rng.integers(0,256,(240,400,3),dtype=np.uint8)
    for profile in PROFILES.values():
        lut=table(profile);apply(raw,old,lut)
        assert np.array_equal(apply(raw,raw,lut),raw)
        assert not apply(np.zeros_like(raw),old,lut).any()
    write(ROOT/'prototype_verified.json',dict(status='COMPUTER_PROTOTYPES_ONLY_AWAIT_VISUAL_SELECTION',profiles=PROFILES,rows=records,
        rules='Fixed integer luminance LUT and convex raw/enhanced RGB mixture, no spatial blur; protect black floor/highlights; no detector changes.',
        synthetic_random_convex_bounds_pass=True,black_pass=True,identity_pass=True,hardware_access=False,sd_written=False))
    print('NATURAL_GUARD_PROTOTYPES_READY',records,flush=True)

if __name__=='__main__':main()
