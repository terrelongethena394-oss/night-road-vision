"""Inspect brighter variants with luminance-preserving chroma cleanup."""
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont
from shadowlift_lab import ROOT,read,write,unpack,words,lift,mean_y,smooth

def clean_chroma(rgb,raw,mix=.8,base=None):
 a=rgb.astype(np.float32);r,g,b=a.transpose(2,0,1);y=(r+2*g+b)*.25;co=(r-b)*.5;cg=(-r+2*g-b)*.25
 q=raw.astype(np.float32);guide=(54*q[:,:,0]+183*q[:,:,1]+19*q[:,:,2])/256
 pad=np.pad(np.stack([co,cg,guide],2),((2,2),(2,2),(0,0)),mode='reflect');nc=np.zeros_like(co);ng=np.zeros_like(cg);den=np.zeros_like(y)
 for dy in range(-2,3):
  for dx in range(-2,3):
   v=pad[dy+2:dy+242,dx+2:dx+402];w=np.exp(-((v[:,:,2]-guide)**2)/128)*np.exp(np.float32(-(dx*dx+dy*dy)/3.0));nc+=v[:,:,0]*w;ng+=v[:,:,1]*w;den+=w
 strength=np.float32(mix)*(1-smooth(30,120,guide))*(1-smooth(180,240,a.max(2)));co+=(nc/den-co)*strength;cg+=(ng/den-cg)*strength
 cap=np.maximum(base.astype(np.float32).max(2),np.minimum(254,10*raw.astype(np.float32).max(2))) if base is not None else np.where(a.max(2)>=255,np.float32(255),np.float32(254))
 deltas=[co-cg,cg,-co-cg];factor=np.ones_like(y)
 for d in deltas:
  factor=np.minimum(factor,np.divide(cap-y,d,out=np.ones_like(d),where=d>0));factor=np.minimum(factor,np.divide(y,-d,out=np.ones_like(d),where=d<0))
 factor=np.clip(factor,0,1);result=np.stack([y+d*factor for d in deltas],2)
 return np.floor(np.clip(result,0,255)+.5).astype(np.uint8)

def final_display(raw,base):
 lit,stats=lift(raw,base,62.)
 return (clean_chroma(lit,raw,.85,base) if stats['strength']>0 else base.copy()),stats

def main():
 names=['current_road','dark_traffic','city_control'];canvas=Image.new('RGB',(1600,840),(15,15,15));font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',15);report={}
 for row,name in enumerate(names):
  folder=ROOT/name;raw=unpack(np.fromfile(folder/'raw.u32','<u4')).reshape(240,400,3);base=unpack(np.fromfile(folder/'base.u32','<u4')).reshape(240,400,3);variants=[('CURRENT',base)]
  for target in [55,62,70]:
   lit,stats=lift(raw,base,float(target));out=clean_chroma(lit,raw,.85);tag='CLEAN'+str(target);Image.fromarray(out).save(folder/(tag+'.png'));words(out).tofile(folder/(tag+'.u32'));variants.append((tag,out));stats['mean_after_chroma']=mean_y(out);stats['new_saturated_pixels_after_chroma']=int(((out.max(2)==255)&(base.max(2)<255)).sum());report[name+'_'+tag]=stats
  for col,(label,im) in enumerate(variants):
   canvas.paste(Image.fromarray(im),(col*400,row*280+40));d=ImageDraw.Draw(canvas);d.text((col*400+6,row*280+3),name+' '+label,fill='white',font=font);d.text((col*400+6,row*280+21),f'MEAN Y {mean_y(im):.1f}',fill='white',font=font)
 canvas.save(ROOT/'chroma_comparison.png');write(ROOT/'chroma_development.json',report);print('SHADOWLIFT_CHROMA_COMPARISON_READY',flush=True)

if __name__=='__main__':main()
