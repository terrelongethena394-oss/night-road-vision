"""Fixed-photo detection study; pixel path mirrors current board RGB888."""
from pathlib import Path
import hashlib,json
import cv2,numpy as np
from road_arm_common import preprocess400
from road_numpy_eval import by_time,correct,evaluate

BASE=Path('E:/FPGA_Enhance_Work')
DATA=BASE/'road_detection_20261026'
ROOT=BASE/'road_accuracy_20261030_r1'
WEIGHTS=DATA/'frozen/road4_best.pt'
APP=BASE/'road_retinex_noiseguard_arm_20261029_r1/firmware'
SEED=2026103001
QUOTA={'night':480,'dawn/dusk':32,'daytime':160}
NAMES=['person','car','truck','bus']
GAMMAS={'raw':1.,'gamma080':.8,'gamma065':.65}
TILES=[(0,120),(200,120),(400,120)]

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sensor400(path):
    im=cv2.imread(str(path));assert im is not None
    sensor=cv2.resize(im[:,:,::-1],(800,480),interpolation=cv2.INTER_LINEAR)
    a=sensor.astype(np.uint16)
    full=((a[0::2,0::2]+a[0::2,1::2]+a[1::2,0::2]+a[1::2,1::2]+2)//4).astype(np.uint8)
    return sensor,full
def gamma(rgb,mode):
    if mode=='raw':return rgb.copy()
    a=rgb.astype(np.float32);v=a.max(2)/255
    target=v**GAMMAS[mode]
    gain=np.divide(target,v,out=np.ones_like(v),where=v>1e-8)
    gain=np.minimum(gain,3.)
    gain=1+(gain-1)*(1-np.clip((v-.65)/.33,0,1))
    return np.floor(np.clip(a*gain[:,:,None],0,255)+.5).astype(np.uint8)
def truth(path):
    a=np.array([[float(v) for v in line.split()] for line in Path(path).read_text().splitlines() if line],np.float32).reshape(-1,5)
    b=a.copy();b[:,1]=(a[:,1]-a[:,3]/2)*400;b[:,2]=(a[:,2]-a[:,4]/2)*240;b[:,3]=(a[:,1]+a[:,3]/2)*400;b[:,4]=(a[:,2]+a[:,4]/2)*240
    return b
def nms_numpy(a,threshold=.6,maxdet=300):
    a=np.asarray(a,np.float32).reshape(-1,6)
    if not len(a):return a
    order=np.argsort(-a[:,4],kind='stable');b=a[order];keep=[];dead=np.zeros(len(b),bool)
    # Same class offset as existing CPU/torch fusion. Float32 throughout.
    boxes=b[:,:4]+b[:,5:6]*np.float32(7680)
    areas=np.maximum(0,boxes[:,2:]-boxes[:,:2]).prod(1)
    for i in range(len(b)):
        if dead[i]:continue
        keep.append(i)
        if len(keep)>=maxdet:break
        inter=np.maximum(0,np.minimum(boxes[i,2:],boxes[i+1:,2:])-np.maximum(boxes[i,:2],boxes[i+1:,:2])).prod(1)
        iou=inter/(areas[i]+areas[i+1:]-inter+np.float32(1e-9))
        dead[i+1:]|=(b[i,5]==b[i+1:,5])&(iou>threshold)
    return b[keep]
def map_tile(pred,x,y):
    p=np.asarray(pred,np.float32).reshape(-1,6).copy()
    if not len(p):return p
    p=p[(p[:,0]>1)&(p[:,1]>1)&(p[:,2]<399)&(p[:,3]<239)]
    p[:,:4]*=.5;p[:,[0,2]]+=x*.5;p[:,[1,3]]+=y*.5
    return p
def fuse(full,tiles,weight):
    a=np.asarray(full,np.float32).reshape(-1,6);extra=[]
    for tile in tiles:
        for p in np.asarray(tile,np.float32).reshape(-1,6):
            if int(p[5])==0 or p[4]<.05:continue  # vehicle-only supplement
            others=a[(a[:,5]==p[5])&(a[:,4]>=.25)]
            if len(others):
                wh=np.maximum(0,p[2:4]-p[:2]);area=wh.prod()
                oa=np.maximum(0,others[:,2:4]-others[:,:2]).prod(1)
                inter=np.maximum(0,np.minimum(p[2:4],others[:,2:4])-np.maximum(p[:2],others[:,:2])).prod(1)
                if np.any((inter/(area+oa-inter+1e-9)>=.3)|(inter/(np.minimum(area,oa)+1e-9)>=.8)):continue
            q=p.copy();q[4]*=weight;extra.append(q)
    # Reserve all original person predictions, so vehicle supplements cannot
    # evict them through the shared maximum-box budget.
    person=a[a[:,5]==0]
    vehicles=np.concatenate([a[a[:,5]!=0],np.asarray(extra,np.float32).reshape(-1,6)])
    vehicles=nms_numpy(vehicles,maxdet=300-len(person)) if len(person)<300 else np.empty((0,6),np.float32)
    combined=np.concatenate([person,vehicles])
    return combined[np.argsort(-combined[:,4],kind='stable')]
def metrics(rows):
    z=dict(all=evaluate(rows),by_time={t:evaluate([r for r in rows if r['timeofday']==t]) for t in ['night','dawn/dusk','daytime'] if any(r['timeofday']==t for r in rows)})
    for part in [z['all'],*z['by_time'].values()]:
        vv=[part['classes'][k]['ap50'] for k in ['car','truck','bus'] if part['classes'][k]['objects']]
        part['vehicle_mAP50']=float(np.mean(vv)) if vv else None
    return z

class Detector:
    def __init__(self):
        import os,sys,torch
        os.environ['YOLOv5_AUTOINSTALL']='false';sys.path.insert(0,str(DATA/'yolov5'))
        from utils.general import non_max_suppression
        self.torch=torch;self.nms=non_max_suppression
        torch.set_num_threads(4);cv2.setNumThreads(1)
        torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
        torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
        self.model=torch.load(WEIGHTS,map_location='cpu',weights_only=False)['model'].float().fuse().eval().cuda()
    def run(self,images):
        t=self.torch
        x=t.from_numpy(np.ascontiguousarray(np.stack([preprocess400(a).transpose(2,0,1) for a in images]))).cuda().float()/255
        with t.inference_mode():pred=self.nms(self.model(x)[0],.001,.6,max_det=300)
        result=[]
        for p in pred:
            a=p.cpu().float().numpy();a[:,[0,2]]=np.clip(a[:,[0,2]]/.8,0,400);a[:,[1,3]]=np.clip((a[:,[1,3]]-64)/.8,0,240)
            result.append(a.tolist())
        return result
