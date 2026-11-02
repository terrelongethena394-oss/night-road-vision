"""Train-only channel calibration and W8/A8 model with exact integer SiLU tables.
Internal Conv int32 sums and Q20 residual rescale; head logits/decode stay FP32.
"""
from pathlib import Path
import collections,hashlib,math,os,sys,time
import cv2,numpy as np
from road_integer_common import ROOT,FLOAT,LIGHT,MARGINS,read,write,sha
def away(x):return (np.sign(x)*np.floor(np.abs(x)+.5)).astype(np.int64)
def code_at(acc,ws,bias,scale):
    x=acc*float(ws)+float(bias)
    value=x/(1+math.exp(-x)) if x>=0 else x*math.exp(x)/(1+math.exp(x))
    q=value/float(scale)
    if q>=127:return 127
    if q<=-127:return -127
    return int(math.floor(q+.5)) if q>=0 else -int(math.floor(-q+.5))
def channel_table(bound,ws,bias,scale):
    lo,hi=-int(bound),int(bound);turn=math.floor((-1.2784645427610738-float(bias))/float(ws));split=max(lo-1,min(hi,turn))
    def monotone(a,b,reverse):
        if a>b:return 0,[]
        fn=lambda z:code_at(-z if reverse else z,ws,bias,scale)
        base=fn(a);maximum=fn(b);assert base<=maximum
        transitions=[]
        for target in range(base+1,maximum+1):
            left,right=a,b
            while left<right:
                mid=(left+right)//2
                if fn(mid)>=target:right=mid
                else:left=mid+1
            assert fn(left)>=target and (left==a or fn(left-1)<target)
            transitions.append(left)
        return base,transitions
    lb,lt=monotone(-split,hi,True) if split>=lo else (0,[])
    rb,rt=monotone(split+1,hi,False) if split<hi else (0,[])
    # Verify table behavior at all transitions, branch split and deterministic interior points.
    def lookup(a):
        if a<=split:return lb+int(np.searchsorted(lt,-a,side='right'))
        return rb+int(np.searchsorted(rt,a,side='right'))
    values={lo,hi,split,split+1,0}
    for v in lt:values.update([-v-1,-v,-v+1])
    for v in rt:values.update([v-1,v,v+1])
    values.update(int(lo+(hi-lo)*t/16) for t in range(17))
    for a in values:
        if lo<=a<=hi:assert lookup(a)==code_at(a,ws,bias,scale),(a,lookup(a),code_at(a,ws,bias,scale))
    return split,lb,lt,rb,rt,len([a for a in values if lo<=a<=hi])

class FloatGraph:
    def __init__(self,g,weights,device):
        import torch
        self.g=g;self.device=device;self.weights={}
        for t in g['tensors'][1:]:
            if t['kind']!=1:continue
            p=g['tensors'][t['inputs'][0]];k=t['k'];w=weights[t['woff']:t['woff']+k*k*p['c4']*t['c4']].reshape(k,k,p['c4'],t['c4'])
            self.weights[t['id']]=(torch.from_numpy(w[:,:,:p['c'],:t['c']].transpose(3,2,0,1).copy()).to(device),torch.from_numpy(weights[t['boff']:t['boff']+t['c']].copy()).to(device))
    def calibrate(self,x,maxima):
        import torch
        from torch.nn import functional as F
        vals={0:x}
        maxima[0]=torch.maximum(maxima[0],x.abs().amax((0,2,3)))
        for t in self.g['tensors'][1:]:
            args=[vals[i] for i in t['inputs']]
            if t['kind']==1:
                w,b=self.weights[t['id']];y=F.conv2d(args[0],w,b,stride=t['s'],padding=t['p'])
                if t['act']:y=F.silu(y)
            elif t['kind']==2:y=args[0]+args[1]
            elif t['kind']==3:y=torch.cat(args,1)
            elif t['kind']==4:y=F.max_pool2d(args[0],5,1,2)
            elif t['kind']==5:y=F.interpolate(args[0],scale_factor=2,mode='nearest')
            else:raise ValueError(t)
            maxima[t['id']]=torch.maximum(maxima[t['id']],y.abs().amax((0,2,3)));vals[t['id']]=y
            for i in t['inputs']:
                if self.g['tensors'][i]['last_use']==t['id']:vals.pop(i,None)
        return vals

def export_variant(tag,margin,g,weights,maxima):
    folder=ROOT/tag;folder.mkdir();scales={};qweights=[];cursor=0;thresholds=[];floats=[];ratios=[];channels=[];nodes=[];proof=[];arrays={}
    def bytes_add(a):
        nonlocal cursor
        offset=cursor;v=np.asarray(a,np.int8).ravel();qweights.append(v.tobytes());cursor+=len(v);pad=(-cursor)%64
        if pad:qweights.append(bytes(pad));cursor+=pad
        return offset
    for t in g['tensors']:
        i=t['id'];pad=t['c4']-t['c'];scale=np.maximum(maxima[str(i)].astype(np.float64)*margin/127,1e-8).astype(np.float32)
        if i==0:scale=np.full(t['c'],1/255,np.float32)
        elif t['kind'] in [4,5]:scale=scales[t['inputs'][0]][:t['c']].copy()
        elif t['kind']==3:scale=np.concatenate([scales[p][:g['tensors'][p]['c']] for p in t['inputs']])
        elif t['kind']==2:scale=np.maximum(scale,np.maximum(scales[t['inputs'][0]][:t['c']],scales[t['inputs'][1]][:t['c']]))
        scale=np.pad(scale,(0,pad),constant_values=1).astype(np.float32);scales[i]=scale;arrays[f'scale_{i}']=scale
        node=dict(id=i,head=i in g['heads'],woff=0,ws_off=0,bias_off=0,ch_base=0,ra_off=0,rb_off=0)
        if i and t['kind']==1:
            p=g['tensors'][t['inputs'][0]];k=t['k'];w=weights[t['woff']:t['woff']+k*k*p['c4']*t['c4']].reshape(k,k,p['c4'],t['c4']).astype(np.float64)
            eff=w*scales[p['id']][None,None,:,None].astype(np.float64);ws=np.maximum(np.abs(eff).max((0,1,2))/127,1e-12).astype(np.float32)
            q=np.clip(away(eff/ws[None,None,None,:]),-127,127).astype(np.int8);b=weights[t['boff']:t['boff']+t['c4']].copy()
            bounds=np.abs(q.astype(np.int64)).sum((0,1,2))*(255 if p['id']==0 else 127);assert int(bounds.max())<2**31
            node['woff']=bytes_add(q);node['ws_off']=len(floats);floats.extend(ws.tolist());node['bias_off']=len(floats);floats.extend(b.tolist());node['ch_base']=len(channels)
            arrays[f'weight_{i}']=q;arrays[f'ws_{i}']=ws;arrays[f'bias_{i}']=b;arrays[f'bound_{i}']=bounds
            comparisons=0
            if not node['head']:
                assert t['act']==1
                for c in range(t['c4']):
                    if c>=t['c']:result=(0,0,[],0,[],0)
                    else:result=channel_table(int(bounds[c]),ws[c],b[c],scale[c])
                    split,lb,lt,rb,rt,n=result;loff=len(thresholds);thresholds.extend(lt);roff=len(thresholds);thresholds.extend(rt)
                    channels.append(dict(split=split,lb=lb,ln=len(lt),lo=loff,rb=rb,rn=len(rt),ro=roff));comparisons+=n
            proof.append(dict(node=i,name=t['name'],max_abs_acc_bound=int(bounds.max()),reference_conv_fp32_exact=int(bounds.max())<2**24,activation_table_boundary_checks=comparisons))
        elif i and t['kind']==2:
            a,b=t['inputs'];ra=np.clip(away(scales[a].astype(np.float64)/scale*2**20),0,2**20).astype(np.int32);rb=np.clip(away(scales[b].astype(np.float64)/scale*2**20),0,2**20).astype(np.int32)
            node['ra_off']=len(ratios);ratios.extend(ra.tolist());node['rb_off']=len(ratios);ratios.extend(rb.tolist());arrays[f'ra_{i}']=ra;arrays[f'rb_{i}']=rb
        nodes.append(node)
    model=b''.join(qweights);threshold_base=len(model);model+=np.array(thresholds,dtype='<i4').tobytes();model+=bytes((-len(model))%64)
    float_base=len(model);model+=np.array(floats,dtype='<f4').tobytes();model+=bytes((-len(model))%64)
    ratio_base=len(model);model+=np.array(ratios,dtype='<i4').tobytes();model+=bytes((-len(model))%64)
    (folder/'qmodel.bin').write_bytes(model);np.savez(folder/'quant_arrays.npz',**arrays)
    write(folder/'quant_graph.json',dict(status='W8_A8_PER_CHANNEL_INTEGER_CONV_AND_SILU_TABLE_MODEL',source_graph_sha256=sha(FLOAT/'graph.json'),source_weights_sha256=sha(FLOAT/'weights.f32'),
        margin=margin,nodes=nodes,channels=channels,threshold_base=threshold_base,float_base=float_base,ratio_base=ratio_base,model_bytes=len(model),model_sha256=sha(folder/'qmodel.bin'),
        arithmetic='Input RGB uses unsigned8 codes and scale1/255. Internal features signed8 perchannel. Conv int32, SiLU quantizer integer threshold search from offline float64 semantics, residual Q20 signed int32. Final raw heads and decode float32.',proof=proof))
    header='#ifndef ROAD_Q8_TABLES_H\n#define ROAD_Q8_TABLES_H\n#include <stdint.h>\n'
    header+=f'#define ROAD_Q_BYTES {len(model)}U\n#define Q_THRESH_BASE {threshold_base}U\n#define Q_FLOAT_BASE {float_base}U\n#define Q_RATIO_BASE {ratio_base}U\n'
    header+='typedef struct{int head;uint32_t wo,ws,bo,ch,ra,rb;} QNode;\ntypedef struct{int32_t split,lb,ln,lo,rb,rn,ro;} QChannel;\n'
    header+='static const QNode Q_NODES[]={'+','.join('{'+','.join(str(int(n[k])) for k in ['head','woff','ws_off','bias_off','ch_base','ra_off','rb_off'])+'}' for n in nodes)+'};\n'
    header+='static const QChannel Q_CHANNELS[]={'+','.join('{'+','.join(str(int(c[k])) for k in ['split','lb','ln','lo','rb','rn','ro'])+'}' for c in channels)+'};\n#endif\n'
    (folder/'road_q8_tables.h').write_text(header,encoding='ascii')
    graph_header=(FLOAT/'road_graph.h').read_text();import re
    graph_header=re.sub(r'#define ROAD_WEIGHT_FLOATS \d+U',f'#define ROAD_WEIGHT_FLOATS {len(model)//4}U',graph_header)
    (folder/'road_graph.h').write_text(graph_header,encoding='ascii')
    print('INTEGER_MODEL_EXPORTED',tag,len(model),'thresholds',len(thresholds),flush=True)
def main():
    ROOT.mkdir(exist_ok=False);start=time.monotonic();g=read(FLOAT/'graph.json');weights=np.fromfile(FLOAT/'weights.f32','<f4')
    assert sha(FLOAT/'weights.f32')==g['weights_sha256'];rows=[r for r in read(LIGHT/'dataset/manifest.json') if r['split']=='train']
    selected=[]
    for period,n in [('night',160),('dawn/dusk',54),('daytime',106)]:
        group=[r for r in rows if r['timeofday']==period];group.sort(key=lambda r:hashlib.sha256(('2026102711|'+r['name']).encode()).hexdigest());selected.extend(group[:n])
    assert len(selected)==320
    protocol=dict(status='FROZEN_BEFORE_INTEGER_CALIBRATION_OR_VALIDATION',calibration_images=[r['name'] for r in selected],calibration_split='train only',margins=MARGINS,
         float_model_sha256=sha(FLOAT/'weights.f32'),input='Exact camera-order320PNG from light dataset',selection='Old validation only, same no-regression gates as light candidates. Final integer and student candidates frozen before shared new holdout. No claim that integer kernels are faster until board timed.',
         no_new_test_used=True,no_hardware_access=True)
    write(ROOT/'protocol.json',protocol);write(LIGHT/'protocol_integer_addendum.json',dict(status='FROZEN_BEFORE_INTEGER_VALIDATION_AND_ALL_FRESH_TESTS',quant_protocol_sha256=sha(ROOT/'protocol.json'),
          reason='Alternative to architecture pruning when validation precision drops. Compare same frozen teacher with W8/A8 Conv and integer SiLU; keep final heads float32. Calibration uses train only. Candidate gates remain unchanged.'))
    import torch
    torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    model=FloatGraph(g,weights,'cuda:0');maxima={t['id']:torch.zeros(t['c'],device='cuda:0') for t in g['tensors']}
    with torch.inference_mode():
        for at in range(0,len(selected),8):
            rs=selected[at:at+8];images=[]
            for r in rs:
                path=LIGHT/'dataset/images/train'/(Path(r['name']).stem+'.png');assert sha(path)==r['input320_sha256'];images.append(cv2.imread(str(path))[:,:,::-1].transpose(2,0,1).copy())
            x=torch.from_numpy(np.stack(images)).cuda().float()/255;model.calibrate(x,maxima)
            if (at+8)%64==0:print('INTEGER_CALIBRATION_TRAIN_FRAMES',at+8,flush=True)
    a={str(i):v.cpu().numpy() for i,v in maxima.items()};np.savez(ROOT/'calibration_maxima.npz',**a)
    del model,maxima;torch.cuda.empty_cache()
    for tag,margin in MARGINS.items():export_variant(tag,margin,g,weights,a)
    write(ROOT/'prepare_complete.json',dict(status='INTEGER_CALIBRATION_AND_THREE_FROZEN_QUANTIZERS_READY',seconds=time.monotonic()-start,calibration_images=320,
          no_validation_used_for_ranges=True,no_test_used=True,no_hardware_write=True))
    print('INTEGER_CALIBRATION_EXPORT_COMPLETE',time.monotonic()-start,flush=True)
if __name__=='__main__':main()
