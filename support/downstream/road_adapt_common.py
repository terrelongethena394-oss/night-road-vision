"""Shared, fixed arithmetic for road enhancement/domain-adaptation experiment."""
from pathlib import Path
import hashlib,json
import cv2,numpy as np
BASE=Path('E:/FPGA_Enhance_Work/road_detection_20261026')
ROOT=Path('E:/FPGA_Enhance_Work/road_joint_adapt_20261026')
REF=Path('E:/FPGA_Enhance_Work/multinex_fixed_w18_20261025/cpp_reference/multinex_reference.exe')
REF_SHA='2eb7289db70c9f5f305cc2b0c84187653b312c03409247db82ecc005aded622d'
SEED=2026102627
NAMES=['person','car','truck','bus']
POLICIES=[dict(name='raw',kind='raw'),dict(name='full_net',kind='net'),dict(name='legacy_protected',kind='legacy'),
          *[dict(name=f'bounded_s{s}_c{c}_t{t}',kind='bounded',strength=s,cap=c,threshold=t)
            for s,c,t in [(64,32,128),(128,32,128),(192,32,128),(256,32,128),(128,64,128),(128,32,64),(128,32,192)]]]
TRAIN_MILD=next(p for p in POLICIES if p['name']=='bounded_s128_c32_t128')
FUSION_POLICIES=[dict(name=f'dual_t{int(t*100):03d}_w{int(w*100):03d}',kind='supplement',min_conf=t,weight=w,gate_mean=48)
                 for t in [.5,.65,.8] for w in [.5,.75]]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def luma(rgb):
    a=rgb.astype(np.int32)
    return (a[:,:,0]*54+a[:,:,1]*183+a[:,:,2]*19+128)>>8
def apply_policy(raw,net,p):
    if p['kind']=='raw':return raw.copy()
    if p['kind']=='net':return net.copy()
    y=luma(raw)
    if p['kind']=='legacy':
        mean=int((y.sum()+y.size//2)//y.size);a=256 if mean<=32 else (0 if mean>=48 else ((48-mean)*256+8)//16)
        return ((raw.astype(np.uint32)*(256-a)+net.astype(np.uint32)*a+128)>>8).astype(np.uint8)
    assert p['kind']=='bounded'
    delta=np.clip(luma(net)-y,0,p['cap']);mask=np.maximum(0,p['threshold']-y);den=256*p['threshold']
    add=(delta*p['strength']*mask+den//2)//den
    return np.minimum(raw.astype(np.int32)+add[:,:,None],255).astype(np.uint8)
def canonical(rgb):
    a=cv2.resize(rgb,(400,240),interpolation=cv2.INTER_LINEAR).copy();a[:,:,0]&=248;a[:,:,1]&=252;a[:,:,2]&=248
    return a
def frame_path(split,kind,name):return ROOT/'frames'/split/kind/(Path(name).stem+'.png')
