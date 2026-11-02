from pathlib import Path
import hashlib,json
import numpy as np
BASE=Path('E:/FPGA_Enhance_Work')
ROOT=BASE/'road_tiny_restore_20261031_r1'
DETECTOR=BASE/'road_viewadapt_20261030_r1/export/model.pt'
SEED=2026103107
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def make_model():
    import torch
    from torch import nn
    class TinyRestore(nn.Module):
        def __init__(self):
            super().__init__()
            self.first=nn.Conv2d(7,12,1)
            self.depth=nn.Conv2d(12,12,3,padding=1,groups=12)
            self.point=nn.Conv2d(12,12,1)
            self.head=nn.Conv2d(12,3,1)
            nn.init.zeros_(self.head.weight);nn.init.zeros_(self.head.bias)
        def forward(self,raw,illum):
            import torch.nn.functional as F
            local=F.avg_pool2d(F.pad(raw,(1,1,1,1),mode='reflect'),3,stride=1)
            x=torch.cat([raw,local,illum],1)
            x=F.relu(self.first(x));x=F.relu(self.depth(x));x=F.relu(self.point(x));res=self.head(x)
            y=(54*local[:,0:1]+183*local[:,1:2]+19*local[:,2:3])/256
            v=raw.amax(1,keepdim=True);u=((v-.65)/.33).clamp(0,1)
            gate=y/(y+.02)*(1-u*u*(3-2*u))
            route=((54*raw[:,0:1]+183*raw[:,1:2]+19*raw[:,2:3])/256).mean((2,3),keepdim=True)<=48/255
            return (raw+res*gate*route).clamp(0,1)
    return TinyRestore()
