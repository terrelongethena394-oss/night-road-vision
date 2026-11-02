"""Known-scene display exposure study; no learned details or recognition changes."""
from pathlib import Path
import ctypes as ct,json,hashlib,shutil
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont
BASE=Path('E:/FPGA_Enhance_Work');ROOT=BASE/'road_shadowlift_20261030_r1';OLD=BASE/'road_car_pair_20261030_r1'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def words(a):
 z=a.astype(np.uint32);return (z[:,:,0]|z[:,:,1]<<8|z[:,:,2]<<16).astype('<u4')
def unpack(a):return np.stack([a&255,a>>8&255,a>>16&255],-1).astype(np.uint8)
def mean_y(a):
 z=a.astype(np.float64);return float(((54*z[:,:,0]+183*z[:,:,1]+19*z[:,:,2])/256).mean())
def smooth(a,b,x):
 t=np.clip((x-a)/(b-a),0,1);return t*t*(3-2*t)

def lift(raw,base,target=70.):
 a=base.astype(np.float32);r=raw.astype(np.float32);v=a.max(2);rv=r.max(2);ry=(54*r[:,:,0]+183*r[:,:,1]+19*r[:,:,2])/256
 y=(54*a[:,:,0]+183*a[:,:,1]+19*a[:,:,2])/256;value=v/255
 weight=(1-smooth(.25,.90,value))*np.sqrt(1-value)*(ry/(ry+4))
 limit=np.maximum(1,np.minimum(np.divide(254,v,out=np.ones_like(v),where=v>0),np.divide(10*rv,v,out=np.ones_like(v),where=v>0)))
 lo=np.float32(0);hi=np.float32(5)
 for _ in range(16):
  mid=np.float32((lo+hi)*.5);g=np.minimum(1+mid*weight,limit)
  if float((y*g).mean(dtype=np.float64))<target:lo=mid
  else:hi=mid
 strength=np.float32((lo+hi)*.5) if mean_y(base)<target else np.float32(0)
 gain=np.minimum(1+strength*weight,limit);out=np.floor(np.clip(a*gain[:,:,None],0,255)+.5).astype(np.uint8)
 return out,dict(target=target,strength=float(strength),mean_raw=mean_y(raw),mean_base=mean_y(base),mean_out=mean_y(out),post_gain_max=float(gain.max()),new_saturated_pixels=int(((out.max(2)==255)&(base.max(2)<255)).sum()),unchanged_near_white_fraction=float((out[base.max(2)>=245]==base[base.max(2)>=245]).mean()) if np.any(base.max(2)>=245) else None)

class Baseline:
 def __init__(self):
  p=read(BASE/'road_retinex_noiseguard_arm_20261029_r1/c_complete.json');self.lib=ct.CDLL(str(Path(p['attempt'])/'retinex.dll'))
  class Stats(ct.Structure):_fields_=[(n,ct.c_float) for n in ['mean_in','mean_out','noise_proxy','alpha','max_gain']]
  self.Stats=Stats;self.up=ct.POINTER(ct.c_uint32);self.fp=ct.POINTER(ct.c_float);self.lib.road_retinex_c.argtypes=[self.up,self.up,ct.c_uint,self.fp,ct.POINTER(Stats),ct.c_void_p,ct.c_void_p]
 def run(self,rgb):
  a=words(rgb).reshape(-1);b=np.empty_like(a);w=np.empty(17*96000+65536,np.float32);stats=self.Stats();assert self.lib.road_retinex_c(a.ctypes.data_as(self.up),b.ctypes.data_as(self.up),96000,w.ctypes.data_as(self.fp),ct.byref(stats),None,None)==0;return unpack(b).reshape(240,400,3)

def main():
 assert not ROOT.exists();ROOT.mkdir();(ROOT/'source').mkdir();shutil.copy2(Path(__file__),ROOT/'source'/Path(__file__).name)
 receipt=read(OLD/'board_verified.json');write(OLD/'physical_panel_check.json',dict(status='USER_CONFIRMED_IMAGES_TEXT_AND_BOXES_NORMAL',answer='左右图像、文字和框均正常',new_feedback='增强图还是太暗，暗处看不清',board_evidence=receipt['evidence']))
 write(ROOT/'protocol.json',dict(status='KNOWN_SCENE_IMAGE_QUALITY_DEVELOPMENT',user_feedback='Still too dark, cannot see shadows',baseline='ABI26 guard_light Retinex, unchanged NLM',candidate='Shadow-only hue-preserving postgain,16-step scalar exposure search,targets70/88, poststrength<=5, overall raw maximum channel gain<=10, no new channel saturation, no spatial blur added.',detector_input='Raw unchanged, models/PL bit unchanged; no claim of recognition improvement from this display-only change.',no_blind_image_quality_or_PSNR_claim=True,hardware_access=False,sd_written=False))
 sources=[('current_road',OLD/'fixtures/road/source800.bgr'),('dark_traffic',BASE/'road_accuracy_20261030_r1/firmware/runtime/cases/babf991d-b4102dd2/sensor800.png'),('city_control',BASE/'road_accuracy_20261030_r1/firmware/runtime/cases/b484aa24-d70cf6e5/sensor800.png')]
 engine=Baseline();font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',15);canvas=Image.new('RGB',(1600,len(sources)*280),(15,15,15));report={}
 for at,(name,p) in enumerate(sources):
  sensor=np.frombuffer(p.read_bytes(),np.uint8).reshape(480,800,3)[:,:,::-1].copy() if p.suffix=='.bgr' else np.asarray(Image.open(p).convert('RGB'))
  raw=((sensor.astype(np.uint16).reshape(240,2,400,2,3).sum(axis=(1,3))+2)//4).astype(np.uint8);old=engine.run(raw);bal,mb=lift(raw,old,70.);strong,ms=lift(raw,old,88.);folder=ROOT/name;folder.mkdir();words(raw).tofile(folder/'raw.u32');words(old).tofile(folder/'base.u32');words(bal).tofile(folder/'balanced.u32');words(strong).tofile(folder/'strong.u32');report[name]=dict(source=str(p),source_sha256=sha(p),balanced=mb,strong=ms)
  for col,(label,im) in enumerate([('RAW',raw),('CURRENT',old),('SHADOW70',bal),('SHADOW88',strong)]):
   Image.fromarray(im).save(folder/(label+'.png'));canvas.paste(Image.fromarray(im),(col*400,at*280+40));d=ImageDraw.Draw(canvas);d.text((col*400+6,at*280+3),name+' '+label,fill='white',font=font);d.text((col*400+6,at*280+21),f'MEAN Y {mean_y(im):.1f}',fill='white',font=font)
 canvas.save(ROOT/'exposure_comparison.png');write(ROOT/'development.json',report);print('SHADOWLIFT_DEVELOPMENT',report,flush=True)

if __name__=='__main__':main()
