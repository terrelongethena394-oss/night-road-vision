"""Frozen preprocessing/model contract for the recognition improvement experiment."""
from pathlib import Path
import hashlib,json
import numpy as np
import torch
from torch import nn
ROOT=Path('E:/FPGA_Enhance_Work/recognition_upgrade_20261026')
BASE=ROOT.parent
SEED=2026102609
OLD=BASE/'real_digit_training_20261025/cnn_candidate'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def normalize_np(x):
    a=np.asarray(x,np.uint8).reshape(-1,784)
    part=np.partition(a,(39,744),axis=1)
    lo=part[:,39].astype(np.int32);hi=part[:,744].astype(np.int32)
    span=np.maximum(hi-lo,32)[:,None];center=((lo+hi+1)//2)[:,None]
    d=a.astype(np.int32)-center;q=(np.abs(d)*192+span//2)//span
    return np.clip(128+np.where(d<0,-q,q),0,255).astype(np.uint8).reshape(-1,28,28)
def normalize_torch(x):
    a=x.reshape(-1,784).to(torch.int32)
    lo=a.kthvalue(40,dim=1).values;hi=a.kthvalue(745,dim=1).values
    span=(hi-lo).clamp_min(32)[:,None];center=((lo+hi+1)//2)[:,None]
    d=a-center;q=(d.abs()*192+span//2)//span
    return (128+torch.where(d<0,-q,q)).clamp(0,255).reshape(-1,28,28).float()/256
class UpgradeCNN(nn.Module):
    def __init__(self,hidden=64):
        super().__init__();self.conv1=nn.Conv2d(1,8,3,padding=1);self.conv2=nn.Conv2d(8,16,3,padding=1)
        self.fc1=nn.Linear(784,hidden);self.fc2=nn.Linear(hidden,11)
    def forward(self,x):
        x=x.reshape(-1,1,28,28)
        x=nn.functional.max_pool2d(torch.relu(self.conv1(x)),2)
        x=nn.functional.max_pool2d(torch.relu(self.conv2(x)),2)
        return self.fc2(torch.relu(self.fc1(x.flatten(1))))
def initialize_from_old():
    old=torch.load(OLD/'real_digit_cnn.pth',weights_only=True,map_location='cpu')
    assert sha(OLD/'real_digit_cnn.pth')=='07478560652fdd4c73e6347f8494cdceecd90cda3f62d8705cbb229babc32493'
    model=UpgradeCNN(64)
    with torch.no_grad():
        for key in ('conv1.weight','conv1.bias','conv2.weight','conv2.bias'):model.state_dict()[key].copy_(old[key])
        model.fc1.weight[:32].copy_(old['fc1.weight']);model.fc1.bias[:32].copy_(old['fc1.bias'])
        model.fc2.weight[:,:32].copy_(old['fc2.weight']);model.fc2.weight[:,32:].zero_();model.fc2.bias.copy_(old['fc2.bias'])
    return model
