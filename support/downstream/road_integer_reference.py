"""Independent CUDA integer-code reference, never uses the deployed C kernel."""
import sys,os
from pathlib import Path
import cv2,numpy as np
from road_integer_common import ROOT,FLOAT,LIGHT,read,write,sha
os.environ['YOLOv5_AUTOINSTALL']='false'
sys.path.insert(0,str(LIGHT/'yolov5'));os.chdir(LIGHT/'yolov5')
import torch
import torch.nn.functional as F
from utils.general import non_max_suppression,scale_boxes
torch.set_num_threads(4)
torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False

class IntegerReference:
    def __init__(self,folder):
        self.folder=Path(folder);self.g=read(FLOAT/'graph.json');self.qg=read(self.folder/'quant_graph.json')
        assert sha(self.folder/'qmodel.bin')==self.qg['model_sha256']
        self.arr=np.load(self.folder/'quant_arrays.npz');self.layers={};blob=(self.folder/'qmodel.bin').read_bytes()
        th=np.frombuffer(blob,dtype='<i4',offset=self.qg['threshold_base'],count=(self.qg['float_base']-self.qg['threshold_base'])//4)
        self.device='cuda:0'
        for t in self.g['tensors'][1:]:
            i=t['id'];n=self.qg['nodes'][i];layer={}
            if t['kind']==1:
                p=self.g['tensors'][t['inputs'][0]];w=self.arr[f'weight_{i}'][:,:,:p['c'],:t['c']].transpose(3,2,0,1).copy()
                dtype=torch.float32 if int(self.arr[f'bound_{i}'].max())<2**24 else torch.float64
                layer['w']=torch.from_numpy(w).to(self.device,dtype=dtype)
                layer['ws']=torch.from_numpy(self.arr[f'ws_{i}'][:t['c']].copy()).to(self.device)[None,:,None,None]
                layer['bias']=torch.from_numpy(self.arr[f'bias_{i}'][:t['c']].copy()).to(self.device)[None,:,None,None]
                if not n['head']:
                    ch=self.qg['channels'][n['ch_base']:n['ch_base']+t['c']]
                    layer['split']=torch.tensor([c['split'] for c in ch],device=self.device)[:,None]
                    for side in ['l','r']:
                        width=max(1,max(c[side+'n'] for c in ch));tab=np.full((t['c'],width),2**31-1,np.int32)
                        for j,c in enumerate(ch):tab[j,:c[side+'n']]=th[c[side+'o']:c[side+'o']+c[side+'n']]
                        layer[side+'t']=torch.from_numpy(tab).to(self.device)
                        layer[side+'b']=torch.tensor([c[side+'b'] for c in ch],device=self.device)[:,None]
            elif t['kind']==2:
                for k in ['ra','rb']:layer[k]=torch.from_numpy(self.arr[f'{k}_{i}'][:t['c']].copy()).to(self.device)[None,:,None,None]
            self.layers[i]=layer
    @torch.inference_mode()
    def forward(self,images,trace=None):
        # images uint8 NCHW, first tensor is intentionally unsigned RGB.
        values={0:images.to(self.device,dtype=torch.int32)}
        if trace:trace(0,values[0])
        for t in self.g['tensors'][1:]:
            i=t['id'];args=[values[j] for j in t['inputs']];layer=self.layers[i]
            if t['kind']==1:
                acc=F.conv2d(args[0].to(layer['w'].dtype),layer['w'],stride=t['s'],padding=t['p']).to(torch.int32)
                if self.qg['nodes'][i]['head']:
                    y=acc.float()*layer['ws'];y=y+layer['bias']
                else:
                    flat=acc.permute(1,0,2,3).contiguous().view(t['c'],-1)
                    left=layer['lb']+torch.searchsorted(layer['lt'],(-flat).contiguous(),right=True)
                    right=layer['rb']+torch.searchsorted(layer['rt'],flat.contiguous(),right=True)
                    y=torch.where(flat<=layer['split'],left,right).view(t['c'],acc.shape[0],t['h'],t['w']).permute(1,0,2,3).contiguous().to(torch.int32)
            elif t['kind']==2:
                v=args[0]*layer['ra']+args[1]*layer['rb']
                y=torch.where(v>=0,(v+2**19)>>20,-((-v+2**19)>>20)).clamp(-127,127)
            elif t['kind']==3:y=torch.cat(args,1)
            elif t['kind']==4:y=F.max_pool2d(args[0].float(),5,1,2).to(torch.int32)
            elif t['kind']==5:y=F.interpolate(args[0].float(),scale_factor=2,mode='nearest').to(torch.int32)
            else:raise ValueError(t)
            values[i]=y
            if trace:trace(i,y)
            for j in t['inputs']:
                if self.g['tensors'][j]['last_use']==i:values.pop(j,None)
        heads=[values[i] for i in self.g['heads']];decoded=[]
        for level,h in enumerate(heads):
            b,c,ny,nx=h.shape;v=h.view(b,3,9,ny,nx).permute(0,1,3,4,2).contiguous().sigmoid()
            yy,xx=torch.meshgrid(torch.arange(ny,device=h.device),torch.arange(nx,device=h.device),indexing='ij')
            grid=torch.stack((xx,yy),2)[None,None].float()-.5
            anchor=torch.tensor(self.g['anchors_pixels'][level],device=h.device).view(1,3,1,1,2)
            v[...,:2]=(v[...,:2]*2+grid)*self.g['strides'][level]
            v[...,2:4]=(v[...,2:4]*2)**2*anchor
            decoded.append(v.view(b,-1,9))
        return torch.cat(decoded,1)

def evaluate(folder,rows,loader,out,tag):
    from road_adapt_eval_core import evaluate_serial_predictions
    model=IntegerReference(folder);predictions={}
    with torch.inference_mode():
        for at in range(0,len(rows),4):
            rs=rows[at:at+4];ims=np.stack([loader(r).transpose(2,0,1) for r in rs]);pred=non_max_suppression(model.forward(torch.from_numpy(ims.copy())),.001,.6,max_det=300)
            for row,p in zip(rs,pred):
                if len(p):scale_boxes((320,320),p[:,:4],(240,400),ratio_pad=((.8,.8),(0.,64.)))
                predictions[row['name']]=p.cpu().float().tolist()
            if (at+4)%64==0:print('INTEGER_VALIDATION_PROGRESS',tag,at+4,flush=True)
    del model;torch.cuda.empty_cache()
    return evaluate_serial_predictions(rows,predictions,out,tag)

if __name__=='__main__':
    from road_light_evaluate import validation_rows,validation_loader
    for tag in ['m100','m110','m125']:
        out=ROOT/'validation_r1'/tag;out.mkdir(parents=True,exist_ok=False)
        metrics=evaluate(ROOT/tag,validation_rows(),validation_loader,out,tag)
        write(out/'complete.json',dict(status='INTEGER_REFERENCE_OLD_VALIDATION_COMPLETE',metrics=metrics,no_new_test=True,no_hardware=True))
        print('INTEGER_VALIDATION_COMPLETE',tag,metrics['all']['mAP50'],metrics['by_time']['night']['mAP50'],flush=True)
