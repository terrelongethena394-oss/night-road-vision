"""Known-scene conservative display cleanup; neither boxes nor NN inputs used."""
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont
from car_box_refine_common import BASE,read,write
from shadowlift_lab import unpack,mean_y,smooth
ROOT=BASE/'road_display_noiseguard_20261031_r1'

def detailguard(raw,current,sharp=.2):
 r=raw.astype(np.float32);a=current.astype(np.float32);ry=(54*r[:,:,0]+183*r[:,:,1]+19*r[:,:,2])/256
 if mean_y(raw)>48:return current.copy()
 mu=cv2.blur(ry,(5,5),borderType=cv2.BORDER_REFLECT_101);v=a.max(2)
 protect=1-.3*(1-smooth(1,12,mu))*(1-smooth(40,100,v))
 protected=np.floor(np.clip(r+(a-r)*protect[:,:,None],0,255)+.5).astype(np.uint8)
 z=protected.astype(np.float32);co=(z[:,:,0]-z[:,:,2])*.5;cg=(-z[:,:,0]+2*z[:,:,1]-z[:,:,2])*.25;y=(z[:,:,0]+2*z[:,:,1]+z[:,:,2])*.25
 # Quarter-gray guide and fixed spatial weights permit a small C lookup table.
 guide=np.floor(ry*4+.5).astype(np.int32);p=np.pad(np.stack([co,cg,guide],2),((2,2),(2,2),(0,0)),mode='reflect')
 nc=np.zeros_like(co);ng=np.zeros_like(cg);den=np.zeros_like(y)
 for dy in range(-2,3):
  for dx in range(-2,3):
   q=p[dy+2:dy+242,dx+2:dx+402];diff=q[:,:,2]-guide
   w=np.exp(-(diff*diff)/2048).astype(np.float32)*np.float32(np.exp(-(dx*dx+dy*dy)/3))
   nc+=q[:,:,0]*w;ng+=q[:,:,1]*w;den+=w
 mix=.85*(1-smooth(30,120,ry))*(1-smooth(180,240,z.max(2)));co+=(nc/den-co)*mix;cg+=(ng/den-cg)*mix
 delta=np.stack([co-cg,cg,-co-cg],2);cap=np.maximum(z.max(2),np.minimum(254,10*r.max(2)));factor=np.ones_like(y)
 for i in range(3):
  d=delta[:,:,i];factor=np.minimum(factor,np.divide(cap-y,d,out=np.ones_like(d),where=d>0));factor=np.minimum(factor,np.divide(y,-d,out=np.ones_like(d),where=d<0))
 z=y[:,:,None]+delta*np.clip(factor,0,1)[:,:,None]
 if sharp:
  blur=cv2.sepFilter2D(ry,-1,np.array([.25,.5,.25],np.float32),np.array([.25,.5,.25],np.float32),borderType=cv2.BORDER_REFLECT_101)
  grad=np.abs(cv2.Sobel(ry,-1,1,0,ksize=3,borderType=cv2.BORDER_REFLECT_101))+np.abs(cv2.Sobel(ry,-1,0,1,ksize=3,borderType=cv2.BORDER_REFLECT_101))
  gain=np.minimum(8,(54*a[:,:,0]+183*a[:,:,1]+19*a[:,:,2])/256/(ry+1))
  d=np.clip(np.float32(sharp)*gain*(ry-blur),-3,3)*smooth(16,80,grad)*(1-smooth(180,245,v));z+=d[:,:,None]
 out=np.floor(np.clip(z,0,254)+.5).astype(np.uint8);out[v>=245]=current[v>=245]
 return out

def main():
 assert not (ROOT/'detailguard_protocol.json').exists()
 write(ROOT/'detailguard_protocol.json',dict(status='KNOWN_SCENE_CONSERVATIVE_DISPLAY_STUDY',
  previous_guided_variant='Raw-edge preservation amplified dark sky color blocks;do not deploy it.',
  method='Keep current validated tone map. Dark low-signal exposure protection<=30%;unconditional quarter-gray-guided chroma cleanup;optional true-source-edge lift<=3gray withstrength.2. No new luminance spatial denoising. Meanraw>48 andcurrentnearwhite>=245 unchanged.',
  known_scene_only=True,no_blind_quality_claim=True,detector_unchanged=True,hardware_access=False,sd_written=False))
 board=BASE/'road_car_balanced_20261030_r1/board_candidate';p=Path(read(board/'board_verified.json')['evidence'])
 sources=[('board_gain',p/'photo_0/raw.u32',p/'photo_0/enhanced.u32'),('board_false',p/'photo_1/raw.u32',p/'photo_1/enhanced.u32'),('dark_traffic',BASE/'road_shadowlift_20261030_r1/dark_traffic/raw.u32',BASE/'road_shadowlift_20261030_r1/dark_traffic/final.u32')]
 canvas=Image.new('RGB',(1600,840),(15,15,15));font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14);stats={}
 for row,(name,r,c) in enumerate(sources):
  raw=unpack(np.fromfile(r,'<u4')).reshape(240,400,3);current=unpack(np.fromfile(c,'<u4')).reshape(240,400,3);soft=detailguard(raw,current,0);sharp=detailguard(raw,current,.2);folder=ROOT/(name+'_guard');folder.mkdir()
  for col,(tag,im) in enumerate([('RAW',raw),('CURRENT',current),('CHROMA + BLACK GUARD',soft),('GUARD + TRUE EDGE',sharp)]):
   Image.fromarray(im).save(folder/(str(col)+'.png'));canvas.paste(Image.fromarray(im),(col*400,row*280+40));d=ImageDraw.Draw(canvas);d.text((col*400+3,row*280+3),name+' '+tag,font=font,fill='white');d.text((col*400+3,row*280+21),f'MEAN {mean_y(im):.1f}',font=font,fill='white')
  stats[name]=dict(current_mean=mean_y(current),guard_mean=mean_y(soft),edge_mean=mean_y(sharp),new_saturated255=int(((sharp.max(2)==255)&(current.max(2)<255)).sum()))
 canvas.save(ROOT/'detailguard_comparison.png');write(ROOT/'detailguard_observations.json',stats)
 # Pixel QA crop,2x nearest display only;no claim of recovered resolution.
 tiles=Image.new('RGB',(1200,360),(15,15,15))
 for col,(tag,file) in enumerate([('CURRENT','1.png'),('GUARD','2.png'),('GUARD+EDGE','3.png')]):
  im=Image.open(ROOT/'board_gain_guard'/file);crop=im.crop((80,20,280,180)).resize((400,320),Image.Resampling.NEAREST);tiles.paste(crop,(400*col,40));ImageDraw.Draw(tiles).text((400*col+5,4),tag+' 2X PIXEL QA',font=font,fill='white')
 tiles.save(ROOT/'detailguard_crop.png');print('DETAILGUARD_PREVIEW_READY',stats,flush=True)

if __name__=='__main__':main()
