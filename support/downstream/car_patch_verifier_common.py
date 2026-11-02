from pathlib import Path
import hashlib,json
import numpy as np
BASE=Path('E:/FPGA_Enhance_Work')
ROOT=BASE/'road_car_verifier_20261030_r1'
ZOOM=BASE/'road_car_zoom_20261030_r1'
INITIAL=BASE/'road_viewadapt_20261030_r1/export/model.pt'
SEED=2026103061
EPOCHS=60
CHECKPOINTS=[15,30,60]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def patch(sensor,box):
 # Original800 RGB, fixed1.25 context, nearest-centre32x32. No generated pixels.
 b=np.asarray(box,np.float32);cx=np.float32(b[0]+b[2]);cy=np.float32(b[1]+b[3])
 w=np.float32(max(4.,float((b[2]-b[0])*np.float32(2.5))))
 h=np.float32(max(4.,float((b[3]-b[1])*np.float32(2.5))))
 xx=np.floor(cx+(np.arange(32,dtype=np.float32)+np.float32(.5)-16)*w/32).astype(np.int32)
 yy=np.floor(cy+(np.arange(32,dtype=np.float32)+np.float32(.5)-16)*h/32).astype(np.int32)
 a=sensor[np.clip(yy,0,479)[:,None],np.clip(xx,0,799)[None,:]].copy()
 z=a.astype(np.uint32);mean=float(((54*z[:,:,0]+183*z[:,:,1]+19*z[:,:,2])/256).mean())
 # Local exposure normalization is fixed, not tuned on test data.
 gain=min(3.,max(1.,80./(mean+4.)))
 a=np.floor(np.clip(a.astype(np.float32)*np.float32(gain),0,255)+.5).astype(np.uint8)
 meta=np.array([b[4],(b[0]+b[2])/800,(b[1]+b[3])/480,(b[2]-b[0])/400,(b[3]-b[1])/240,mean/255],np.float32)
 return a,meta

def make_model():
 import torch
 from torch import nn
 class Model(nn.Module):
  def __init__(self):
   super().__init__();self.conv=nn.Sequential(nn.Conv2d(3,8,3,2,1),nn.ReLU(),nn.Conv2d(8,16,3,2,1),nn.ReLU(),nn.Conv2d(16,24,3,2,1),nn.ReLU())
   self.fc1=nn.Linear(24*4*4+6,32);self.fc2=nn.Linear(32,1)
  def forward(self,x,meta):
   z=self.conv(x).flatten(1);return self.fc2(torch.relu(self.fc1(torch.cat([z,meta],1)))).flatten()
 return Model()

def iou_max(box,gt):
 if not len(gt):return 0.
 p=np.asarray(box,np.float32);g=np.asarray(gt,np.float32).reshape(-1,4)
 inter=np.maximum(0,np.minimum(p[2:4],g[:,2:4])-np.maximum(p[:2],g[:,:2])).prod(1)
 return float(np.max(inter/(np.maximum(0,p[2:4]-p[:2]).prod()+np.maximum(0,g[:,2:4]-g[:,:2]).prod(1)-inter+1e-9)))
