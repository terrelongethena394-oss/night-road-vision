"""Known-scene, display-only noise-aware exposure study; no detector changes."""
from pathlib import Path
import numpy as np,cv2
from PIL import Image,ImageDraw,ImageFont
from shadowlift_lab import Baseline,mean_y,words,unpack,smooth
from shadowlift_refine import clean_chroma
from car_box_refine_common import BASE,read,write,sha
ROOT=BASE/'road_display_noiseguard_20261031_r1'

def noise_lift(raw,base,cap=8.,denoise=.15):
 r=raw.astype(np.float32);a=base.astype(np.float32);ry=(54*r[:,:,0]+183*r[:,:,1]+19*r[:,:,2])/256
 haar=(ry[::2,::2]-ry[::2,1::2]-ry[1::2,::2]+ry[1::2,1::2])*.5
 sigma=float(np.median(np.abs(haar))/np.float32(.67448975))
 mu=cv2.blur(ry,(5,5),borderType=cv2.BORDER_REFLECT_101);var=np.maximum(0,cv2.blur(ry*ry,(5,5),borderType=cv2.BORDER_REFLECT_101)-mu*mu)
 if mean_y(base)>=62:return base.copy(),dict(sigma=sigma,strength=0,mean=mean_y(base),bypass=True)
 confidence=mu/(mu+np.float32(2*sigma)+np.float32(1e-6));v=a.max(2);rv=r.max(2)
 weight=(1-smooth(.25,.9,v/255))*np.sqrt(1-v/255)*(ry/(ry+4))*confidence
 rawcap=np.float32(4.5)+np.float32(cap-4.5)*confidence
 limit=np.maximum(1,np.minimum(np.divide(254,v,out=np.ones_like(v),where=v>0),np.divide(rawcap*rv,v,out=np.ones_like(v),where=v>0)))
 y=(54*a[:,:,0]+183*a[:,:,1]+19*a[:,:,2])/256;lo=np.float32(0);hi=np.float32(5)
 for _ in range(16):
  mid=np.float32((lo+hi)*.5);gain=np.minimum(1+mid*weight,limit)
  if float((y*gain).mean(dtype=np.float64))<62:lo=mid
  else:hi=mid
 gain=np.minimum(1+np.float32((lo+hi)*.5)*weight,limit);lit=np.floor(np.clip(a*gain[:,:,None],0,255)+.5).astype(np.uint8)
 if denoise and sigma>.5:
  z=lit.astype(np.float32);yy=(54*z[:,:,0]+183*z[:,:,1]+19*z[:,:,2])/256
  alpha=np.float32(denoise)*(sigma*sigma/(var+sigma*sigma+1e-6))*(1-smooth(25,70,mu))*(1-smooth(160,230,z.max(2)))
  delta=(cv2.blur(yy,(3,3),borderType=cv2.BORDER_REFLECT_101)-yy)*alpha
  lit=np.floor(np.clip(z+delta[:,:,None],0,254)+.5).astype(np.uint8)
  # Preserve every pixel whose prior enhancement already has near-white values.
  lit[a.max(2)>=245]=np.floor(a[a.max(2)>=245]+.5).astype(np.uint8)
 result=clean_chroma(lit,raw,.85,base)
 return result,dict(sigma=sigma,strength=float((lo+hi)*.5),mean=mean_y(result),bypass=False)

def main():
 assert not ROOT.exists();ROOT.mkdir();(ROOT/'source').mkdir();__import__('shutil').copy2(__file__,ROOT/'source'/Path(__file__).name)
 write(ROOT/'protocol.json',dict(status='KNOWN_SCENE_DISPLAY_DEVELOPMENT_ONLY',
  reason='Inspect actual hardware readback:sky/road noise is visible and road-side false detections remain. Image appearance and detector accuracy are separate.',
  candidate='Keep prior Retinex baseline;noise estimate from2x2 Haar median,5x5 source SNR controls added exposure. Targets62,rawcaps8/10;optional<=15%luma smoothing only noisy low-texture dark regions. Chroma cleanup unchanged.',
  evaluation='Visual comparison on known board scenes plus prior rainy/city images;not blind and no normal-exposure ground truth. Do not claim PSNR/SSIM quality improvement.',
  detector_input='All YOLO and refiner inputs/weights unchanged;display only. No board access or SD changes.',hardware_access=False,sd_written=False))
 board=BASE/'road_car_balanced_20261030_r1/board_candidate';receipt=read(board/'board_verified.json');evidence=Path(receipt['evidence'])
 sources=[('board_gain',evidence/'photo_0/raw.u32',evidence/'photo_0/enhanced.u32'),('board_false',evidence/'photo_1/raw.u32',evidence/'photo_1/enhanced.u32'),
          ('rain',BASE/'road_shadowlift_20261030_r1/dark_traffic/raw.u32',BASE/'road_shadowlift_20261030_r1/dark_traffic/final.u32')]
 font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14);canvas=Image.new('RGB',(1600,840),(15,15,15));engine=Baseline();stats={}
 for row,(name,rawfile,currentfile) in enumerate(sources):
  raw=unpack(np.fromfile(rawfile,'<u4')).reshape(240,400,3);base=engine.run(raw);current=unpack(np.fromfile(currentfile,'<u4')).reshape(240,400,3)
  v8,s8=noise_lift(raw,base,8.,.15);v10,s10=noise_lift(raw,base,10.,0);stats[name]=dict(cap8=s8,cap10=s10,raw_mean=mean_y(raw),current_mean=mean_y(current))
  folder=ROOT/name;folder.mkdir()
  for col,(tag,im) in enumerate([('RAW',raw),('CURRENT',current),('SNR CAP8',v8),('SNR CAP10 NO LUMA FILTER',v10)]):
   Image.fromarray(im).save(folder/(str(col)+'.png'));canvas.paste(Image.fromarray(im),(col*400,row*280+40));d=ImageDraw.Draw(canvas)
   d.text((col*400+3,row*280+3),name+' '+tag,fill='white',font=font);d.text((col*400+3,row*280+21),f'MEAN {mean_y(im):.1f}',fill='white',font=font)
 canvas.save(ROOT/'comparison.png');write(ROOT/'observations.json',stats);print('DISPLAY_SNR_PREVIEW_READY',stats,flush=True)

if __name__=='__main__':main()
