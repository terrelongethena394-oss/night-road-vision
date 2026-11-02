from pathlib import Path
from road_adapt_common import read,write,sha,NAMES,BASE
ROOT=Path('E:/FPGA_Enhance_Work/road_arm_prototype_20261026')
DIAG=Path('E:/FPGA_Enhance_Work/road_pipeline_diagnostic_20261026')
WEIGHT=BASE/'frozen/road4_best.pt'
WEIGHT_SHA='98f46429cd431d735e276d7735f50f61811a70cbb5feb2a0475fba562449a46f'

def preprocess400(a):
    import numpy as np
    assert a.shape==(240,400,3) and a.dtype==np.uint8
    yy=(10*np.arange(192)+1);xx=(10*np.arange(320)+1)
    y,fy=yy//8,yy%8;x,fx=xx//8,xx%8
    z=a.astype(np.int32)
    s=(z[y[:,None],x[None,:]]*((8-fy)[:,None]*(8-fx)[None,:])[:,:,None]+
       z[y[:,None],x[None,:]+1]*((8-fy)[:,None]*fx[None,:])[:,:,None]+
       z[y[:,None]+1,x[None,:]]*(fy[:,None]*(8-fx)[None,:])[:,:,None]+
       z[y[:,None]+1,x[None,:]+1]*(fy[:,None]*fx[None,:])[:,:,None])
    out=np.full((320,320,3),114,np.uint8);out[64:256]=((s+32)//64).astype(np.uint8)
    return out
