from pathlib import Path
import hashlib,json
import numpy as np
BASE=Path('E:/FPGA_Enhance_Work')
ROOT=BASE/'road_car_boxrefine_20261030_r1'
PREV=BASE/'road_car_verifier_20261030_r1'
ZOOM=BASE/'road_car_zoom_20261030_r1'
SEED=2026103071
EPOCHS=80
CHECKPOINTS=[20,40,80]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def patch(sensor,box):
 b=np.asarray(box,np.float32);cx=np.float32(b[0]+b[2]);cy=np.float32(b[1]+b[3])
 w=np.float32(max(4.,float((b[2]-b[0])*np.float32(3.))));h=np.float32(max(4.,float((b[3]-b[1])*np.float32(3.))))
 xx=np.floor(cx+(np.arange(32,dtype=np.float32)+.5-16)*w/32).astype(np.int32)
 yy=np.floor(cy+(np.arange(32,dtype=np.float32)+.5-16)*h/32).astype(np.int32)
 a=sensor[np.clip(yy,0,479)[:,None],np.clip(xx,0,799)[None,:]].copy();z=a.astype(np.uint32)
 mean=float(((54*z[:,:,0]+183*z[:,:,1]+19*z[:,:,2])/256).mean());gain=np.float32(min(3.,max(1.,80./(mean+4.))))
 a=np.floor(np.clip(a.astype(np.float32)*gain,0,255)+.5).astype(np.uint8)
 meta=np.array([0,(b[0]+b[2])/800,(b[1]+b[3])/480,(b[2]-b[0])/400,(b[3]-b[1])/240,mean/255],np.float32)
 return a,meta

def make_model():
 import torch
 from torch import nn
 class Model(nn.Module):
  def __init__(self):
   super().__init__();self.conv=nn.Sequential(nn.Conv2d(3,8,3,2,1),nn.ReLU(),nn.Conv2d(8,16,3,2,1),nn.ReLU(),nn.Conv2d(16,24,3,2,1),nn.ReLU())
   self.fc1=nn.Linear(390,32);self.fc2=nn.Linear(32,5)
  def forward(self,x,m):return self.fc2(torch.relu(self.fc1(torch.cat([self.conv(x).flatten(1),m],1))))
 return Model()

def adjust(box,delta,strength,cap):
 b=np.asarray(box,np.float32).copy();d=np.clip(np.asarray(delta,np.float32),-np.float32(cap),np.float32(cap))*np.float32(strength)
 w,h=b[2:4]-b[:2];cx=(b[0]+b[2])*np.float32(.5)+d[0]*w;cy=(b[1]+b[3])*np.float32(.5)+d[1]*h
 nw=w*np.exp(d[2]);nh=h*np.exp(d[3]);b[0]=np.clip(cx-nw*.5,0,400);b[2]=np.clip(cx+nw*.5,0,400)
 b[1]=np.clip(cy-nh*.5,0,240);b[3]=np.clip(cy+nh*.5,0,240)
 return b
