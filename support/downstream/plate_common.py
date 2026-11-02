"""Chinese full-plate sequence recognition experiment, separate from digit branch."""
from pathlib import Path
import hashlib,json,sys,importlib.util
import numpy as np
import torch
import torch.nn.functional as F
ROOT=Path('E:/FPGA_Enhance_Work/license_plate_20261026')
BASE=ROOT.parent
SEED=2026102617
SOURCE=ROOT/'lprnet_source'
CHARS=list('京沪津渝冀晋蒙辽吉黑苏浙皖闽赣鲁豫鄂湘粤桂琼川贵云藏陕甘青宁新0123456789ABCDEFGHJKLMNPQRSTUVWXYZIO-')
PROVINCES=list('皖沪津渝冀晋蒙辽吉黑苏浙京闽赣鲁豫鄂湘粤桂琼川贵云藏陕甘青宁新')
ALPHABETS=list('ABCDEFGHJKLMNPQRSTUVWXYZ')
ADS=ALPHABETS+list('0123456789')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def decode_key(key):
    import re
    m=re.search(r'-(\d+_\d+(?:_\d+){5,6})-\d+-\d+',key)
    assert m,'No CCPD annotation in key'
    ids=list(map(int,m[1].split('_')))
    assert len(ids)==7 and ids[0]<31 and ids[1]<24 and all(i<34 for i in ids[2:]),'Only standard seven-character blue plates in this phase'
    return PROVINCES[ids[0]]+ALPHABETS[ids[1]]+''.join(ADS[i] for i in ids[2:])
def split_plate(label):
    k=int(hashlib.sha256((str(SEED)+'|'+label).encode()).hexdigest()[:8],16)%100
    return 'train' if k<70 else ('validation' if k<85 else 'test')
def build_model(pretrained=True):
    spec=importlib.util.spec_from_file_location('reviewed_lprnet',SOURCE/'model/LPRNet.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    model=module.build_lprnet(lpr_max_len=8,phase=False,class_num=len(CHARS),dropout_rate=0)
    if pretrained:model.load_state_dict(torch.load(SOURCE/'weights/Final_LPRNet_model.pth',weights_only=True,map_location='cpu'))
    return model
def forward_per_image(model,x):
    # Upstream averages feature energy across the batch; this version matches
    # its batch1 operation but makes independent-image batching possible.
    keep=[]
    for i,layer in enumerate(model.backbone):
        x=layer(x)
        if i in [2,6,13,22]:keep.append(x)
    context=[]
    for i,z in enumerate(keep):
        if i in [0,1]:z=F.avg_pool2d(z,5,5)
        elif i==2:z=F.avg_pool2d(z,(4,10),(4,2))
        z=z/(z*z).mean((1,2,3),keepdim=True).clamp_min(1e-12);context.append(z)
    return model.container(torch.cat(context,1)).mean(2)
def decode(logits):
    rows=logits.argmax(1).cpu().numpy() if isinstance(logits,torch.Tensor) else np.asarray(logits).argmax(1)
    result=[]
    for row in rows:
        previous=-1;out=[]
        for k in row:
            k=int(k)
            if k!=previous and k!=len(CHARS)-1:out.append(CHARS[k])
            previous=k
        result.append(''.join(out))
    return result
def edit_distance(a,b):
    prev=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        cur=[i]
        for j,y in enumerate(b,1):cur.append(min(cur[-1]+1,prev[j]+1,prev[j-1]+(x!=y)))
        prev=cur
    return prev[-1]
