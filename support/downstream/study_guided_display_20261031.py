"""Display-only guided illumination, preserve raw luminance detail in dark branch."""
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont
from car_box_refine_common import BASE,read,write
from shadowlift_lab import mean_y,unpack,smooth,Baseline
from shadowlift_refine import clean_chroma
ROOT=BASE/'road_display_noiseguard_20261031_r1'

def guided_display(raw,cap=8.):
 a=raw.astype(np.float32);ry=(54*a[:,:,0]+183*a[:,:,1]+19*a[:,:,2])/256;v=a.max(2);i=v/255
 def box(z):return cv2.blur(z,(17,17),borderType=cv2.BORDER_REFLECT_101)
 mean=box(i);var=np.maximum(0,box(i*i)-mean*mean);aa=var/(var+.001);bb=mean-aa*mean
 illumination=np.maximum(i,box(aa)*i+box(bb));core=np.minimum(np.maximum(illumination,.02)**np.float32(-.55),np.float32(cap))
 mu=cv2.blur(ry,(5,5),borderType=cv2.BORDER_REFLECT_101)
 weight=(core-1)*smooth(1,8,mu)*(1-smooth(160,245,v))
 limit=np.maximum(1,np.minimum(np.float32(cap),np.divide(254,v,out=np.ones_like(v),where=v>0)))
 lo=np.float32(0);hi=np.float32(4)
 for _ in range(16):
  mid=np.float32((lo+hi)*.5);gain=np.minimum(1+mid*weight,limit)
  if float((ry*gain).mean(dtype=np.float64))<62:lo=mid
  else:hi=mid
 strength=np.float32((lo+hi)*.5) if mean_y(raw)<62 else np.float32(0)
 gain=np.minimum(1+strength*weight,limit);out=np.floor(np.clip(a*gain[:,:,None],0,255)+.5).astype(np.uint8)
 out=clean_chroma(out,raw,.85,raw);out[v>=245]=raw[v>=245]
 return out,dict(mean_raw=mean_y(raw),mean_out=mean_y(out),strength=float(strength),cap=cap,new_saturated_pixels=int(((out.max(2)==255)&(v<255)).sum()),no_spatial_luminance_filter=True)

def main():
 assert not (ROOT/'direct_protocol.json').exists()
 write(ROOT/'direct_protocol.json',dict(status='KNOWN_SCENE_GUIDED_ILLUMINATION_FROZEN_BEFORE_PREVIEWS',
  previous='First SNR post-gain changes made virtually no difference:the two board scenes bypass added exposure because prior baseline mean>=62;Haar median was0. Preserve these observations.',
  method='Dark branch from original RGB,17x17 guided max-channel illumination,source mean5 nearblack protection,fixed gamma.45,scalar exposure search target62,caps6/8. Chroma-only cleanup,nearwhite raw>=245 exact. No spatial luminance denoising in this branch.',
  purpose='Check whether preserving raw edges avoids prior patch-filter softness. Not paired-truth image-quality proof;no recognition gain claim.',
  no_detector_or_board_changes=True,hardware_access=False,sd_written=False))
 board=BASE/'road_car_balanced_20261030_r1/board_candidate';p=Path(read(board/'board_verified.json')['evidence'])
 cases=[('board_gain',p/'photo_0/raw.u32',p/'photo_0/enhanced.u32'),('board_false',p/'photo_1/raw.u32',p/'photo_1/enhanced.u32'),
        ('dark_traffic',BASE/'road_shadowlift_20261030_r1/dark_traffic/raw.u32',BASE/'road_shadowlift_20261030_r1/dark_traffic/final.u32')]
 canvas=Image.new('RGB',(1600,840),(15,15,15));font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14);stats={}
 for row,(name,r,c) in enumerate(cases):
  raw=unpack(np.fromfile(r,'<u4')).reshape(240,400,3);current=unpack(np.fromfile(c,'<u4')).reshape(240,400,3)
  a,sa=guided_display(raw,6.);b,sb=guided_display(raw,8.);stats[name]=dict(cap6=sa,cap8=sb)
  folder=ROOT/(name+'_direct');folder.mkdir()
  for col,(tag,im) in enumerate([('RAW',raw),('CURRENT',current),('GUIDED CAP6',a),('GUIDED CAP8',b)]):
   Image.fromarray(im).save(folder/(str(col)+'.png'));canvas.paste(Image.fromarray(im),(col*400,row*280+40));d=ImageDraw.Draw(canvas)
   d.text((col*400+3,row*280+3),name+' '+tag,font=font,fill='white');d.text((col*400+3,row*280+21),f'MEAN {mean_y(im):.1f}',font=font,fill='white')
 canvas.save(ROOT/'guided_comparison.png');write(ROOT/'guided_observations.json',stats);print('GUIDED_DISPLAY_PREVIEW_READY',stats,flush=True)

if __name__=='__main__':main()
