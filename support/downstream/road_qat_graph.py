"""Full-width fused YOLO graph with fixed trained-data W8/A8 STE quantizers.
Training surrogate only. Deployment uses the independently exported exact integer model.
GPL-3.0, same graph/anchors as the verified detector.
"""
from pathlib import Path
import copy,json,numpy as np,torch
from torch import nn
from torch.nn import functional as F
NN=Path('E:/FPGA_Enhance_Work/road_arm_prototype_20261026')
QUANT=Path('E:/FPGA_Enhance_Work/road_integer_20261027/m125')
def round_ste(x):
    rounded=x.sign()*torch.floor(x.abs()+.5)
    return x+(rounded-x).detach()
class QConv(nn.Module):
    def __init__(self,t,p,weights,arrays):
        super().__init__();self.t=t;self.head=not bool(t['act']);i=t['id'];k=t['k']
        w=weights[t['woff']:t['woff']+k*k*p['c4']*t['c4']].reshape(k,k,p['c4'],t['c4'])[:,:,:p['c'],:t['c']].transpose(3,2,0,1).copy()
        self.weight=nn.Parameter(torch.from_numpy(w));self.bias=nn.Parameter(torch.from_numpy(weights[t['boff']:t['boff']+t['c']].copy()))
        self.register_buffer('input_scale',torch.from_numpy(arrays[f'scale_{p["id"]}'][:p['c']].copy()).view(1,-1,1,1))
        self.register_buffer('output_scale',torch.from_numpy(arrays[f'scale_{i}'][:t['c']].copy()).view(1,-1,1,1))
        self.register_buffer('weight_scale',torch.from_numpy(arrays[f'ws_{i}'][:t['c']].copy()).view(-1,1,1,1))
        self.first=p['id']==0
    def weight_codes(self):
        # Match the existing exporter rounding of effective weights in float64.
        eff=self.weight.double()*self.input_scale.double()/self.weight_scale.double()
        return round_ste(eff).clamp(-127,127).float()
    def forward(self,x):
        qa=round_ste(x/self.input_scale).clamp(0 if self.first else -127,255 if self.first else 127)
        acc=F.conv2d(qa,self.weight_codes(),stride=self.t['s'],padding=self.t['p'])
        y=acc*self.weight_scale.view(1,-1,1,1)+self.bias.view(1,-1,1,1)
        if self.head:return y
        return round_ste(F.silu(y)/self.output_scale).clamp(-127,127)*self.output_scale
class QATGraph(nn.Module):
    def __init__(self,teacher,hyp):
        super().__init__();self.g=json.loads((NN/'graph.json').read_text());arrays=np.load(QUANT/'quant_arrays.npz');weights=np.fromfile(NN/'weights.f32','<f4')
        self.convs=nn.ModuleDict();self.hyp=hyp
        head=copy.deepcopy(teacher.model[-1]).cpu();head.m=nn.ModuleList();self.model=nn.ModuleList([head]);self.stride=teacher.stride.cpu()
        for t in self.g['tensors']:
            i=t['id'];self.register_buffer(f'scale_{i}',torch.from_numpy(arrays[f'scale_{i}'][:t['c']].copy()).view(1,-1,1,1))
            if i and t['kind']==1:self.convs[str(i)]=QConv(t,self.g['tensors'][t['inputs'][0]],weights,arrays)
            if i and t['kind']==2:
                for name in ['ra','rb']:self.register_buffer(f'{name}_{i}',torch.from_numpy(arrays[f'{name}_{i}'][:t['c']].copy()).view(1,-1,1,1))
        for t in self.g['tensors'][1:]:
            if t['kind']==1:
                expected=arrays[f'weight_{t["id"]}'][:,:,:self.g['tensors'][t['inputs'][0]]['c'],:t['c']].transpose(3,2,0,1)
                assert np.array_equal(self.convs[str(t['id'])].weight_codes().detach().numpy(),expected),'Initial weight code drift'
    def forward(self,x,trace=None):
        vals={0:round_ste(x*255).clamp(0,255)/255}
        if trace:trace(0,round_ste(vals[0]*255))
        for t in self.g['tensors'][1:]:
            i=t['id'];args=[vals[j] for j in t['inputs']]
            if t['kind']==1:y=self.convs[str(i)](args[0])
            elif t['kind']==2:
                a,b=t['inputs'];qa=round_ste(args[0]/getattr(self,f'scale_{a}'));qb=round_ste(args[1]/getattr(self,f'scale_{b}'))
                v=qa.double()*getattr(self,f'ra_{i}').double()+qb.double()*getattr(self,f'rb_{i}').double()
                q=round_ste(v/1048576).clamp(-127,127).float();y=q*getattr(self,f'scale_{i}')
            elif t['kind']==3:y=torch.cat(args,1)
            elif t['kind']==4:y=F.max_pool2d(args[0],5,1,2)
            elif t['kind']==5:y=F.interpolate(args[0],scale_factor=2,mode='nearest')
            else:raise ValueError(t)
            vals[i]=y
            if trace:trace(i,y if i in self.g['heads'] else round_ste(y/getattr(self,f'scale_{i}')))
            for j in t['inputs']:
                if self.g['tensors'][j]['last_use']==i:vals.pop(j,None)
        return [vals[i].view(x.shape[0],3,9,vals[i].shape[2],vals[i].shape[3]).permute(0,1,3,4,2).contiguous() for i in self.g['heads']]
    def fused_weights(self):
        weights=np.fromfile(NN/'weights.f32','<f4').copy()
        for t in self.g['tensors'][1:]:
            if t['kind']!=1:continue
            p=self.g['tensors'][t['inputs'][0]];k=t['k'];conv=self.convs[str(t['id'])]
            w=np.zeros((k,k,p['c4'],t['c4']),np.float32);w[:,:,:p['c'],:t['c']]=conv.weight.detach().cpu().numpy().transpose(2,3,1,0)
            weights[t['woff']:t['woff']+w.size]=w.ravel();weights[t['boff']:t['boff']+t['c']]=conv.bias.detach().cpu().numpy()
        return weights
