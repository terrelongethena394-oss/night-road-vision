"""Small sequence CNN for 96x32 BGR crops; ReLU6 permits bounded integer export."""
import torch
from torch import nn
class DSBlock(nn.Module):
    def __init__(self,cin,cout,stride):
        super().__init__();self.dw=nn.Conv2d(cin,cin,3,stride=stride,padding=1,groups=cin,bias=False);self.dw_bn=nn.BatchNorm2d(cin)
        self.pw=nn.Conv2d(cin,cout,1,bias=False);self.pw_bn=nn.BatchNorm2d(cout)
    def forward(self,x):
        x=torch.clamp(self.dw_bn(self.dw(x)),0,6)
        return torch.clamp(self.pw_bn(self.pw(x)),0,6)
class TinyPlate(nn.Module):
    def __init__(self,classes=68):
        super().__init__();self.stem=nn.Conv2d(1,16,3,stride=2,padding=1,bias=False);self.stem_bn=nn.BatchNorm2d(16)
        self.b1=DSBlock(16,32,(2,2));self.b2=DSBlock(32,64,(2,1));self.b3=DSBlock(64,96,(2,1))
        self.temporal=nn.Conv1d(192,128,3,padding=1,bias=False);self.temporal_bn=nn.BatchNorm1d(128);self.head=nn.Conv1d(128,classes,1)
    def forward(self,x):
        x=torch.clamp(self.stem_bn(self.stem(x)),0,6);x=self.b3(self.b2(self.b1(x)))
        x=x.flatten(1,2);x=torch.clamp(self.temporal_bn(self.temporal(x)),0,6)
        return self.head(x)
