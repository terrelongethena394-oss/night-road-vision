"""Small frozen 28x28 -> 32 ReLU -> 11 digit/background classifier.

Inputs are white foreground on black background, divided by 256. The integer
model uses signed Q12 weights, Q20 biases, and Q8 hidden activations.
"""
from pathlib import Path
import numpy as np
import torch
from torch import nn

ROOT=Path('E:/FPGA_Enhance_Work/digit_recognition_20261023')


class DigitMLP(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1=nn.Linear(784,32)
        self.fc2=nn.Linear(32,11)

    def forward(self,x):
        return self.fc2(torch.relu(self.fc1(x.reshape(-1,784))))


def round_away(x):
    return (np.sign(x)*np.floor(np.abs(x)+0.5)).astype(np.int64)


def rshift(x,n):
    return np.sign(x)*((np.abs(x)+(1<<(n-1)))>>n)


class IntegerDigit:
    def __init__(self,state):
        self.w1=round_away(state['fc1.weight'].numpy()*4096)
        self.b1=round_away(state['fc1.bias'].numpy()*1048576)
        self.w2=round_away(state['fc2.weight'].numpy()*4096)
        self.b2=round_away(state['fc2.bias'].numpy()*1048576)
        assert max(np.abs(self.w1).max(),np.abs(self.w2).max())<=32767

    def infer(self,x):
        x=np.asarray(x,dtype=np.int64).reshape(-1,784)
        h=np.clip(rshift(x@self.w1.T+self.b1,12),0,(1<<20)-1)
        logits=h@self.w2.T+self.b2
        return logits.argmax(1),logits

    def bounds(self):
        lo=np.minimum(self.w1,0).sum(1)*255+self.b1
        hi=np.maximum(self.w1,0).sum(1)*255+self.b1
        hhi=np.maximum(rshift(hi,12),0)
        assert hhi.max()<(1<<20)
        olo=np.minimum(self.w2,0)@hhi+self.b2
        ohi=np.maximum(self.w2,0)@hhi+self.b2
        assert max(np.abs(lo).max(),np.abs(hi).max(),np.abs(olo).max(),np.abs(ohi).max())<(1<<39)
        return dict(first_acc_min=int(lo.min()),first_acc_max=int(hi.max()),hidden_max_q8=int(hhi.max()),
                    output_acc_min=int(olo.min()),output_acc_max=int(ohi.max()),accumulator_bits=40)
