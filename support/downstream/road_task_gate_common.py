from pathlib import Path
import hashlib,json
import numpy as np
BASE=Path('E:/FPGA_Enhance_Work');ROOT=BASE/'road_task_gate_20261031_r1';SEED=2026103141
INITIAL=BASE/'road_viewadapt_20261030_r1/export/model.pt'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def make_model():
    import torch
    from torch import nn
    class Gate(nn.Module):
        def __init__(self):
            super().__init__();self.first=nn.Conv2d(7,8,1);self.depth=nn.Conv2d(8,8,3,padding=1,groups=8);self.head=nn.Conv2d(8,1,1)
            nn.init.zeros_(self.head.weight);nn.init.zeros_(self.head.bias)
        def forward(self,raw,bright,illum):
            x=torch.cat([raw,bright,illum],1);x=torch.relu(self.first(x));x=torch.relu(self.depth(x));mask=.1+.9*torch.sigmoid(self.head(x))
            return (raw+mask*(bright-raw)).clamp(0,1),mask
    return Gate()
def preprocess_exact(z):
    import torch
    import torch.nn.functional as F
    # Forward uses the exact integer400->320 path including both quantizers.
    # Backpropagation uses straight-through gradients,not a different resize.
    z255=z*255;pix=z255+(torch.floor(z255+.5)-z255).detach()
    yy=10*torch.arange(192,device=z.device)+1;xx=10*torch.arange(320,device=z.device)+1
    y=yy//8;x=xx//8;fy=(yy%8).to(z.dtype)[:,None];fx=(xx%8).to(z.dtype)[None,:]
    a=pix[:,:,y[:,None],x[None,:]]*((8-fy)*(8-fx))
    a+=pix[:,:,y[:,None],x[None,:]+1]*((8-fy)*fx)
    a+=pix[:,:,y[:,None]+1,x[None,:]]*(fy*(8-fx))
    a+=pix[:,:,y[:,None]+1,x[None,:]+1]*(fy*fx)
    q=a/64;q=q+(torch.floor((a+32)/64)-q).detach()
    return F.pad(q/255,(0,0,64,64),value=114/255)
