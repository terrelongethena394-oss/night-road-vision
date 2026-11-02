"""Exact C zoom pixels and fusion on every reused development image."""
from pathlib import Path
import ctypes as ct,os,shutil,subprocess
import numpy as np
from study_car_zoom_20261030 import ROOT,XS,zoom,map_zoom,fuse_zoom
from road_enhanceadapt_common import BASE,AUDIT,read,write,sha
from road_accuracy_common import sensor400
from road_classwise_native import Box
from shadowlift_lab import unpack

class ZoomC:
 def __init__(self):
  self.lib=ct.CDLL(str(ROOT/'c_proof/zoom.dll'));self.bp=ct.POINTER(Box);self.up=ct.POINTER(ct.c_uint32)
  self.fuse=self.lib.road_car_zoom_fuse;self.fuse.argtypes=[self.bp,ct.c_int,self.bp,ct.POINTER(ct.c_int),ct.c_float,self.bp,ct.c_int];self.fuse.restype=ct.c_int
  self.pixels=self.lib.road_zoom_pixels;self.pixels.argtypes=[ct.POINTER(ct.c_ubyte),ct.c_int,ct.c_int,self.up];self.pixels.restype=ct.c_int
 def image(self,sensor,x,y):
  source=np.ascontiguousarray(sensor[:,:,::-1]);before=source.tobytes();out=np.full(96002,0x12345678,np.uint32)
  ptr=ct.cast(ct.c_void_p(out.ctypes.data+4),self.up)
  assert self.pixels(source.ctypes.data_as(ct.POINTER(ct.c_ubyte)),x,y,ptr)==0
  assert out[0]==out[-1]==0x12345678 and source.tobytes()==before
  return unpack(out[1:-1]).reshape(240,400,3)
 def run(self,raw,local,w):
  a=(Box*300)();b=(Box*900)();out=(Box*302)();out[0].order=out[301].order=0x12345678
  for i,p in enumerate(raw):a[i]=Box(*map(float,p[:5]),int(p[5]),i)
  for t,pp in enumerate(local):
   for i,p in enumerate(pp):b[t*300+i]=Box(*map(float,p[:5]),int(p[5]),i)
  aa=bytes(a);bb=bytes(b);ptr=ct.cast(ct.byref(out,ct.sizeof(Box)),self.bp)
  n=self.fuse(a,len(raw),b,(ct.c_int*3)(*[len(p) for p in local]),w,ptr,300)
  assert 0<=n<=300 and out[0].order==out[301].order==0x12345678 and bytes(a)==aa and bytes(b)==bb
  return np.array([[out[i+1].x1,out[i+1].y1,out[i+1].x2,out[i+1].y2,out[i+1].score,out[i+1].cls] for i in range(n)],np.float32).reshape(-1,6)

def main():
 selected=read(ROOT/'selected.json');assert selected['qualified'];y=read(ROOT/'protocol.json')['geometry']['y'];out=ROOT/'c_proof';out.mkdir();src=out/'source';src.mkdir()
 here=Path(__file__).parent
 s=(here/'road_vehicle_multiview.c').read_text(encoding='utf-8')
 old='b.x1=b.x1*.5f+(float)t*100.f;b.x2=b.x2*.5f+(float)t*100.f;b.y1=b.y1*.5f+60.f;b.y2=b.y2*.5f+60.f;'
 new=f'b.x1=b.x1*.35f+(float)t*130.f;b.x2=b.x2*.35f+(float)t*130.f;b.y1=b.y1*.35f+{y*.5:.1f}f;b.y2=b.y2*.35f+{y*.5:.1f}f;'
 assert s.count(old)==1
 s=s.replace(old,new).replace('int road_vehicle_multiview(','int road_car_zoom_fuse(').replace('if(b.cls==0||b.score<.05f','if(b.cls!=1||b.score<.05f')
 (src/'road_car_zoom_fuse.c').write_text(s,encoding='utf-8')
 shutil.copy2(here/'road_vehicle_multiview.h',src/'road_vehicle_multiview.h')
 for n in ['road_fp32.h','road_graph.h']:shutil.copy2(BASE/'road_car_bright_20261030_r1/firmware/source'/n,src/n)
 pixel=r'''#include <stdint.h>
#include <stddef.h>
int road_zoom_pixels(const unsigned char *bgr,int x0,int y0,uint32_t *out){
 int x,y,c;
 if(!bgr||!out||x0<0||x0>520||y0<0||y0>312||(const void*)bgr==(void*)out)return 1;
 for(y=0;y<240;y++){
  int v=14*y-3,yy,fy,y1;if(v<0)v=0;if(v>3340)v=3340;yy=v/20;fy=v%20;y1=yy<167?yy+1:167;
  for(x=0;x<400;x++){
   int u=14*x-3,xx,fx,x1;uint32_t value=0;
   if(u<0)u=0;if(u>5580)u=5580;xx=u/20;fx=u%20;x1=xx<279?xx+1:279;
   for(c=0;c<3;c++){
    unsigned a=bgr[((y0+yy)*800+x0+xx)*3+2-c];
    unsigned b=bgr[((y0+yy)*800+x0+x1)*3+2-c];
    unsigned d=bgr[((y0+y1)*800+x0+xx)*3+2-c];
    unsigned e=bgr[((y0+y1)*800+x0+x1)*3+2-c];
    unsigned q=(a*(20-fx)*(20-fy)+b*fx*(20-fy)+d*(20-fx)*fy+e*fx*fy+200)/400;
    value|=q<<(8*c);
   }
   out[y*400+x]=value;
  }
 }
 return 0;
}
'''
 # Braced scalar statements keep the strict compiler diagnostics useful.
 pixel=pixel.replace('if(v<0)v=0;if(v>3340)v=3340;','if(v<0){v=0;}if(v>3340){v=3340;}').replace('if(u<0)u=0;if(u>5580)u=5580;','if(u<0){u=0;}if(u>5580){u=5580;}')
 (src/'road_zoom_pixels.c').write_text(pixel,encoding='ascii')
 gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH']
 cmd=[str(gcc),'-O2','-std=c99','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror','-shared','-static-libgcc','-Wl,--export-all-symbols',str(src/'road_car_zoom_fuse.c'),str(src/'road_zoom_pixels.c'),'-lm','-o',str(out/'zoom.dll')]
 p=subprocess.run(cmd,capture_output=True,text=True,env=env);(out/'build.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
 engine=ZoomC();manifest=read(BASE/'road_brightness_route_20261030_r1/fresh/manifest.json');low=[r for r in manifest if r['cohort']=='low']
 pred={r['name']:r for r in read(ROOT/'zoom_predictions.json')};raw={r['name']:r['raw_multiview'] for r in read(AUDIT/'predictions.json')};fused=[]
 for at,r in enumerate(low):
  sensor,_=sensor400(BASE/'road_brightness_route_20261030_r1/fresh/images'/r['name'])
  for x in XS:assert engine.image(sensor,x,y).tobytes()==zoom(sensor,x,y).tobytes()
  actual=engine.run(raw[r['name']]['detections'],pred[r['name']]['local'],selected['chosen']['weight'])
  reference=fuse_zoom(raw[r['name']]['detections'],pred[r['name']]['mapped'],selected['chosen']['weight'])
  assert actual.shape==reference.shape and actual.tobytes()==reference.tobytes(),r['name']
  fused.append(dict(name=r['name'],ground_truth=raw[r['name']]['ground_truth'],detections=actual.tolist()))
  if (at+1)%80==0:print('ZOOM_C_PIXELS_AND_FUSION_EXACT',at+1,len(low),flush=True)
 assert fused==read(ROOT/'chosen_predictions.json')
 rng=np.random.default_rng(2026103044)
 for sensor in [np.zeros((480,800,3),np.uint8),np.full((480,800,3),255,np.uint8),rng.integers(0,256,(480,800,3),np.uint8)]:
  for x in XS:assert engine.image(sensor,x,y).tobytes()==zoom(sensor,x,y).tobytes()
 assert len(engine.run([], [[],[],[]],selected['chosen']['weight']))==0
 write(ROOT/'c_complete.json',dict(status='ALL320_ZOOM_C_NUMPY_PIXELS_AND_FUSION_BYTE_EXACT',images=320,real_pixel_views=960,synthetic_pixel_views=9,
  fusion_cases=320,source_sha256={p.name:sha(p) for p in src.iterdir()},dll_sha256=sha(out/'zoom.dll'),compiler=cmd,
  source_and_output_guards=True,source_immutable=True,selection_sha256=sha(ROOT/'selected.json'),hardware_access=False,sd_written=False))
 shutil.copy2(__file__,ROOT/'source'/Path(__file__).name);print('ZOOM_C_PROOF_COMPLETE',flush=True)

if __name__=='__main__':main()
