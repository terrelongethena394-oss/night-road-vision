from pathlib import Path
import hashlib,json
import numpy as np
BASE=Path('E:/FPGA_Enhance_Work')
ROOT=BASE/'road_retinex_student_20261031_r2'
SEED=2026103119
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def make_model():
    import torch
    import torch.nn.functional as F
    from torch import nn
    class Student(nn.Module):
        def __init__(self):
            super().__init__();self.first=nn.Conv2d(7,12,1);self.depth=nn.Conv2d(12,12,3,padding=1,groups=12);self.point=nn.Conv2d(12,12,1);self.head=nn.Conv2d(12,3,1)
            nn.init.zeros_(self.head.weight);nn.init.zeros_(self.head.bias)
        def forward(self,a,f):
            u=((a.amax(1,keepdim=True)-.65)/.33).clamp(0,1);gate=1-u*u*(3-2*u)
            gain=torch.where(f>1e-8,(f*(2-f)).clamp_min(0).sqrt()/f.clamp_min(1e-8),torch.ones_like(f))
            base=a*(1+(gain-1)*gate)
            x=torch.cat([a,base,f],1);x=F.relu(self.first(x));x=F.relu(self.depth(x));x=F.relu(self.point(x))
            return (base+self.head(x)*gate).clamp(0,1)
    return Student()
def infer(net,a,torch):
    from road_retinex_project import illumination
    total=int((a.astype(np.uint64)*np.array([54,183,19],np.uint64)).sum())
    if total==0 or total>48*256*96000:return a.copy()
    x=torch.from_numpy(np.ascontiguousarray(a.transpose(2,0,1))).float().cuda()[None]/255
    f=torch.from_numpy(illumination(a)).cuda()[None,None]
    with torch.inference_mode():z=net(x,f)[0].permute(1,2,0).cpu().numpy()
    return np.floor(z*255+.5).astype(np.uint8)
