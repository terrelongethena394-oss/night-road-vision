"""Lower frozen YOLOv5n into a concrete FP32 NHWC C graph, with liveness allocation.
YOLOv5 architecture semantics adapted under GPL-3.0; preserve upstream license.
"""
import os,sys,copy,collections
from pathlib import Path
import cv2,numpy as np
from road_arm_common import ROOT,DIAG,BASE,WEIGHT,WEIGHT_SHA,NAMES,read,write,sha,preprocess400
os.chdir(BASE/'yolov5');sys.path.insert(0,str(BASE/'yolov5'))
import torch
from torch import nn
from torch.nn import functional as F
from models.common import Conv,Bottleneck,C3,SPPF,Concat
from models.yolo import Detect
torch.set_num_threads(4)

class Lower:
    def __init__(self):
        self.tensors=[dict(id=0,name='input320',h=320,w=320,c=3,c4=4,inputs=[])];self.ops=[];self.weights=[];self.cursor=0
    def node(self,kind,inputs,h,w,c,name,**kw):
        i=len(self.tensors);d=dict(id=i,name=name,h=h,w=w,c=c,c4=(c+3)//4*4,inputs=inputs,kind=kind,**kw)
        self.tensors.append(d);self.ops.append(d);return i
    def blob(self,a):
        v=np.asarray(a,dtype='<f4').ravel();offset=self.cursor;self.weights.append(v);self.cursor+=len(v)
        pad=(-self.cursor)%16
        if pad:self.weights.append(np.zeros(pad,np.float32));self.cursor+=pad
        return offset
    def conv(self,m,x,name,act=False):
        assert m.groups==1 and m.dilation==(1,1) and m.kernel_size[0]==m.kernel_size[1] and m.stride[0]==m.stride[1]
        t=self.tensors[x];k=m.kernel_size[0];s=m.stride[0];p=m.padding[0];oc=m.out_channels;ic=m.in_channels
        assert ic==t['c'];oc4=(oc+3)//4*4
        w=np.zeros((k,k,t['c4'],oc4),np.float32);w[:,:,:ic,:oc]=m.weight.detach().cpu().numpy().transpose(2,3,1,0)
        b=np.zeros(oc4,np.float32)
        if m.bias is not None:b[:oc]=m.bias.detach().cpu().numpy()
        wi=self.blob(w);bi=self.blob(b)
        return self.node(1,[x],(t['h']+2*p-k)//s+1,(t['w']+2*p-k)//s+1,oc,name,k=k,s=s,p=p,act=int(act),woff=wi,boff=bi)
    def cat(self,x,name):
        ts=[self.tensors[i] for i in x];assert len(x)<=4 and len({(t['h'],t['w']) for t in ts})==1
        return self.node(3,x,ts[0]['h'],ts[0]['w'],sum(t['c'] for t in ts),name)
    def module(self,m,x,name):
        if isinstance(m,Conv):
            assert isinstance(m.act,(nn.SiLU,nn.Identity)) and not hasattr(m,'bn')
            return self.conv(m.conv,x,name,isinstance(m.act,nn.SiLU))
        if isinstance(m,Bottleneck):
            y=self.module(m.cv2,self.module(m.cv1,x,name+'.cv1'),name+'.cv2')
            if m.add:
                t=self.tensors[x];return self.node(2,[x,y],t['h'],t['w'],t['c'],name+'.add')
            return y
        if isinstance(m,C3):
            y=self.module(m.cv1,x,name+'.cv1')
            for j,b in enumerate(m.m):y=self.module(b,y,name+f'.m.{j}')
            z=self.module(m.cv2,x,name+'.cv2')
            return self.module(m.cv3,self.cat([y,z],name+'.cat'),name+'.cv3')
        if isinstance(m,SPPF):
            y=self.module(m.cv1,x,name+'.cv1');t=self.tensors[y];items=[y]
            for j in range(3):items.append(self.node(4,[items[-1]],t['h'],t['w'],t['c'],name+f'.pool{j}',k=5,s=1,p=2))
            return self.module(m.cv2,self.cat(items,name+'.cat'),name+'.cv2')
        if isinstance(m,nn.Upsample):
            assert m.mode=='nearest' and m.scale_factor==2;t=self.tensors[x]
            return self.node(5,[x],t['h']*2,t['w']*2,t['c'],name)
        if isinstance(m,Concat):return self.cat(x,name)
        raise TypeError((name,type(m)))
    def allocate(self,heads):
        n=len(self.tensors);last=[i for i in range(n)]
        for t in self.ops:
            for i in t['inputs']:last[i]=max(last[i],t['id'])
        for i in heads:last[i]=n
        free=[];active={};end=0
        for t in self.tensors:
            i=t['id'];size=((t['h']*t['w']*t['c4']+15)//16)*16
            fits=[(count,j) for j,(offset,count) in enumerate(free) if count>=size]
            if fits:
                _,j=min(fits);offset,count=free.pop(j)
                if count>size:free.append((offset+size,count-size))
            else:offset=end;end+=size
            # Inputs are still live during output allocation and execution.
            for other,(a,b) in active.items():assert offset+size<=a or offset>=a+b,(i,other)
            t.update(offset=offset,elements=t['h']*t['w']*t['c4'],allocated_elements=size,last_use=last[i]);active[i]=(offset,size)
            for q in list(active):
                if last[q]==i:free.append(active.pop(q))
            free.sort();merged=[]
            for a,b in free:
                if merged and merged[-1][0]+merged[-1][1]==a:merged[-1]=(merged[-1][0],merged[-1][1]+b)
                else:merged.append((a,b))
            free=merged
        return end

def execute(graph,weights,x):
    # Independent lowering proof using PyTorch primitive operators, CPU float32.
    vals={0:x}
    for t in graph.ops:
        args=[vals[i] for i in t['inputs']]
        if t['kind']==1:
            src=args[0];ic=src.shape[1];oc=t['c'];ic4=(ic+3)//4*4;oc4=t['c4'];k=t['k'];w=weights[t['woff']:t['woff']+k*k*ic4*oc4].reshape(k,k,ic4,oc4)
            w=torch.from_numpy(w[:,:,:ic,:oc].transpose(3,2,0,1).copy());b=torch.from_numpy(weights[t['boff']:t['boff']+oc].copy())
            y=F.conv2d(src,w,b,stride=t['s'],padding=t['p'])
            if t['act']:y=F.silu(y)
        elif t['kind']==2:y=args[0]+args[1]
        elif t['kind']==3:y=torch.cat(args,1)
        elif t['kind']==4:y=F.max_pool2d(args[0],5,1,2)
        elif t['kind']==5:y=F.interpolate(args[0],scale_factor=2,mode='nearest')
        else:raise ValueError(t)
        assert list(y.shape)==[1,t['c'],t['h'],t['w']];vals[t['id']]=y
    return vals

def main():
    ROOT.mkdir(exist_ok=False);assert sha(WEIGHT)==WEIGHT_SHA
    protocol=read(DIAG/'protocol.json');names=protocol['examples']
    fixtures=[dict(name=Path(n).stem,source=n,kind='validation',timeofday=next(r['timeofday'] for r in protocol['rows'] if r['name']==n)) for n in names]
    fixtures += [dict(name='control_black',kind='synthetic'),dict(name='control_random',kind='synthetic')]
    write(ROOT/'protocol.json',dict(status='FROZEN_BEFORE_C_EXPORT_AND_FIXTURE_INFERENCE',model_sha256=WEIGHT_SHA,weights=str(WEIGHT),fixtures=fixtures,input_size=320,
          arithmetic='FP32 real arithmetic, with SSE2 host / NEON Cortex-A9 four-output-channel accumulation. Not INT8.',
          preprocessing='Explicit integer bilinear at scale4/5 with eighth-pixel coordinates, nearest half-up output, padding114 top/bottom64. OpenCV INTER_LINEAR compared but not assumed identical.',
          scope='Fixed-image standalone probe and host validation; no camera integration or board timing claim.',board_written=False,sd_written=False))
    original=torch.load(WEIGHT,map_location='cpu',weights_only=False)['model'].float().eval();model=copy.deepcopy(original).fuse().eval()
    g=Lower();top=[];x=0;heads=[]
    for m in model.model:
        if m.f!=-1:x=top[m.f] if isinstance(m.f,int) else [x if j==-1 else top[j] for j in m.f]
        if isinstance(m,Detect):
            assert m.nc==4 and m.na==3 and m.nl==3
            heads=[g.conv(conv,i,f'model.{m.i}.head{j}') for j,(conv,i) in enumerate(zip(m.m,x))]
            strides=m.stride.detach().cpu().numpy();anchors=(m.anchors*m.stride[:,None,None]).detach().cpu().numpy()
            break
        x=g.module(m,x,f'model.{m.i}');top.append(x)
    assert len(heads)==3
    arena=g.allocate(heads);weights=np.concatenate(g.weights).astype('<f4');weights.tofile(ROOT/'weights.f32')
    graph=dict(status='LOWERED_NHWC4_FP32_GRAPH_WITH_LIVENESS',tensors=g.tensors,heads=heads,arena_floats=arena,weights_floats=len(weights),
               strides=strides.tolist(),anchors_pixels=anchors.tolist(),class_names=NAMES,weights_sha256=sha(ROOT/'weights.f32'))
    write(ROOT/'graph.json',graph)
    header='#ifndef ROAD_GRAPH_H\n#define ROAD_GRAPH_H\n#include <stdint.h>\n'
    header+='typedef struct{int h,w,c,c4;uint32_t off;} RoadTensor;\n'
    header+='typedef struct{int kind,n,in[4],k,s,p,act;uint32_t wo,bo;} RoadOp;\n'
    header+=f'#define ROAD_TENSORS {len(g.tensors)}\n#define ROAD_ARENA_FLOATS {arena}U\n#define ROAD_WEIGHT_FLOATS {len(weights)}U\n#define ROAD_CANDIDATES 6300\n'
    header+='static const RoadTensor ROAD_T[]={' + ','.join('{'+','.join(str(t[k]) for k in ['h','w','c','c4','offset'])+'}' for t in g.tensors)+'};\n'
    ops=[]
    for t in g.ops:
        ins=t['inputs']+[-1]*(4-len(t['inputs']))
        ops.append('{'+f'{t["kind"]},{len(t["inputs"])},'+'{'+','.join(map(str,ins))+'},'+','.join(str(t.get(k,0)) for k in ['k','s','p','act','woff','boff'])+'}')
    header+='static const RoadOp ROAD_OPS[]={'+','.join(ops)+'};\n'
    header+='static const int ROAD_HEADS[3]={'+','.join(map(str,heads))+'};\n'
    header+='static const float ROAD_STRIDES[3]={'+','.join(str(float(v))+'f' for v in strides)+'};\n'
    header+='static const float ROAD_ANCHORS[3][3][2]={'+','.join('{'+','.join('{'+','.join(str(float(v))+'f' for v in pair)+'}' for pair in level)+'}' for level in anchors)+'};\n#endif\n'
    (ROOT/'road_graph.h').write_text(header,encoding='ascii')
    cases=ROOT/'cases';cases.mkdir();proofs=[];rng=np.random.default_rng(2026102641)
    with torch.inference_mode():
        for fixture in fixtures:
            folder=cases/fixture['name'];folder.mkdir()
            if fixture['kind']=='validation':a=cv2.imread(str(DIAG/'camera_order/frames'/(fixture['name']+'.sim565.png')))[:,:,::-1].copy()
            elif fixture['name']=='control_black':a=np.zeros((240,400,3),np.uint8)
            else:a=rng.integers(0,256,(240,400,3),dtype=np.uint8)
            words=a[:,:,0].astype(np.uint32)|(a[:,:,1].astype(np.uint32)<<8)|(a[:,:,2].astype(np.uint32)<<16);words.astype('<u4').tofile(folder/'input400.u32')
            image=preprocess400(a);image.tofile(folder/'input320.rgb');tensor=torch.from_numpy(image.transpose(2,0,1).copy())[None].float()/255
            before=original(tensor)[0];after,raw=model(tensor);assert torch.allclose(before,after,rtol=1e-4,atol=1e-4)
            vals=execute(g,weights,tensor)
            for j,i in enumerate(heads):
                h,w=g.tensors[i]['h'],g.tensors[i]['w'];lower=vals[i].reshape(1,3,9,h,w).permute(0,1,3,4,2)
                assert torch.equal(lower,raw[j]),(fixture['name'],j,float((lower-raw[j]).abs().max()))
            trace=folder/'golden';trace.mkdir()
            for t in g.tensors:
                image=vals[t['id']][0].permute(1,2,0).cpu().numpy();packed=np.zeros((t['h'],t['w'],t['c4']),dtype='<f4');packed[:,:,:t['c']]=image;packed.tofile(trace/f'{t["id"]:03d}.f32')
            after.cpu().numpy().astype('<f4').tofile(folder/'decoded.f32')
            from utils.general import non_max_suppression,scale_boxes
            boxes=non_max_suppression(after.clone(),.25,.6,max_det=300)[0];boxes.numpy().astype('<f4').tofile(folder/'boxes320.f32')
            mapped=boxes.clone();scale_boxes((320,320),mapped[:,:4],(240,400),ratio_pad=((.8,.8),(0.,64.)))
            mapped.numpy().astype('<f4').tofile(folder/'boxes400.f32')
            legacy=cv2.copyMakeBorder(cv2.resize(a,(320,192),interpolation=cv2.INTER_LINEAR),64,64,0,0,cv2.BORDER_CONSTANT,value=(114,114,114))
            delta=np.abs(preprocess400(a).astype(np.int16)-legacy.astype(np.int16))
            proofs.append(dict(**fixture,input_sha256=sha(folder/'input400.u32'),preprocessing_vs_opencv_max_abs=int(delta.max()),preprocessing_vs_opencv_different_bytes=int((delta!=0).sum()),
                               fuse_decoded_max_abs=float((before-after).abs().max()),lowered_heads_exact=True,boxes=len(boxes)))
            print('ROAD_ARM_EXPORT_FIXTURE',fixture['name'],len(boxes),flush=True)
    shutil_license=BASE/'yolov5/LICENSE';(ROOT/'YOLOv5_LICENSE').write_bytes(shutil_license.read_bytes())
    write(ROOT/'export_complete.json',dict(status='C_GRAPH_EXPORTED_AND_LOWERED_TORCH_HEADS_EXACT',graph_sha256=sha(ROOT/'graph.json'),weights_sha256=sha(ROOT/'weights.f32'),
          arena_bytes=arena*4,weight_bytes=len(weights)*4,fixtures=proofs,board_deployed=False,sd_written=False))
    print('ROAD_ARM_GRAPH_EXPORT_COMPLETE',len(g.tensors),arena*4,len(weights)*4,flush=True)
if __name__=='__main__':main()
