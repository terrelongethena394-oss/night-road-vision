from pathlib import Path
import hashlib,json
import numpy as np
ROOT=Path('E:/FPGA_Enhance_Work/road_enhance_20261027')
NN=Path('E:/FPGA_Enhance_Work/road_arm_prototype_20261026')
OLD=Path('E:/FPGA_Enhance_Work/road_hybrid_20261027_r1')
CAPS=[16,24,32]
GAMMA_LIFT=np.maximum(0,np.floor(255*(np.arange(256)/255.)**.65+.5).astype(np.int32)-np.arange(256))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,indent=2,ensure_ascii=False),encoding='utf-8')
def enhance(rgb,mode=1,cap=24):
    a=rgb.astype(np.uint32);y=(54*a[:,:,0]+183*a[:,:,1]+19*a[:,:,2]+128)>>8;n=y.size;mean=int((int(y.sum())+n//2)//n)
    alpha=256 if mean<=40 else (0 if mean>=80 else ((80-mean)*256+20)//40)
    if mode==0:alpha=0
    if mode==2:alpha=256
    i=np.arange(256,dtype=np.uint32);d=np.minimum(np.minimum(GAMMA_LIFT.astype(np.uint32),cap),i);d=(d*np.maximum(0,192-i.astype(np.int32)).astype(np.uint32)+96)//192;d=(d*alpha+128)>>8
    gain=np.full(256,4096,np.uint32);gain[1:]=((i[1:]+d[1:])*4096+i[1:]//2)//i[1:]
    out=np.minimum(255,(a*gain[a.max(2)][:,:,None]+2048)>>12).astype(np.uint8);oy=out.astype(np.uint32)
    meanout=int((int(((54*oy[:,:,0]+183*oy[:,:,1]+19*oy[:,:,2]+128)>>8).sum())+n//2)//n)
    stats=dict(mean_in=mean,mean_out=meanout,alpha=alpha,cap=cap,changed=int(np.any(out!=rgb,axis=2).sum()),max_delta=int((out.astype(np.int32)-rgb).max()))
    return out,stats
