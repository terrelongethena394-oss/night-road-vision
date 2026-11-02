"""Post-freeze diagnostic only: fixed real photos with synthetic exposure."""
from pathlib import Path
import importlib.util,json,time
import numpy as np
from PIL import Image
from scipy.io import loadmat
import torch
from train_real_digit_cnn import OUT,TEST,IntegerCNN

UPGRADE=Path('E:/FPGA_Enhance_Work/model_upgrade_20261023')

def pool(rgb):
    v=rgb.astype(np.int64);g=(77*v[:,:,0]+150*v[:,:,1]+29*v[:,:,2]+128)>>8
    return ((g.reshape(28,8,28,8).sum((1,3))+32)>>6).astype(np.uint8)

def main():
    assert not (OUT/'synthetic_light_diagnostic.json').exists(),'Keep fixed diagnostic outcomes'
    q=IntegerCNN(torch.load(OUT/'real_digit_cnn.pth',map_location='cpu',weights_only=True))
    spec=importlib.util.spec_from_file_location('fixed8',UPGRADE/'hls8/fixed8.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    state=torch.load(UPGRADE/'student8/best_student8.pth',map_location='cpu',weights_only=True)
    enhance=mod.FixedNanoDCE({k:v.numpy() for k,v in state.items()})
    d=loadmat(TEST);x=d['X'].transpose(3,0,1,2);y=d['y'].reshape(-1)%10
    ids=np.concatenate([np.flatnonzero(y==k)[:10] for k in range(10)])
    rows=[];start=time.monotonic()
    for i,index in enumerate(ids):
        original=np.array(Image.fromarray(x[index]).resize((224,224),Image.Resampling.LANCZOS))
        original[:,:,0]&=248;original[:,:,1]&=252;original[:,:,2]&=248
        for alpha in (1.,.125):
            raw=np.floor(original.astype(np.float64)*alpha+.5).astype(np.uint8)
            # Three-pixel surround reproduces the small network's full context.
            # Context is the same constant 16 as fixed-image tile, also dimmed.
            surround=np.full((230,230,3),int(16*alpha+.5),np.uint8);surround[3:227,3:227]=raw
            nn=enhance.infer(surround)[0][3:227,3:227]
            gamma=np.floor(np.sqrt(raw.astype(np.float64)/255)*255+.5).astype(np.uint8)
            row=dict(svhn_test_index=int(index),truth=int(y[index]),alpha=alpha)
            for name,image in [('RAW',raw),('GAMMA',gamma),('NN8',nn)]:
                p,_=q.infer(pool(image));row[name]=int(p[0])
            rows.append(row)
        if (i+1)%10==0:print('FROZEN_LIGHT_DIAGNOSTIC',i+1,100,round(time.monotonic()-start,1),flush=True)
    summary=[]
    for alpha in (1.,.125):
        group=[r for r in rows if r['alpha']==alpha]
        summary.append(dict(alpha=alpha,n=len(group),correct={key:sum(r[key]==r['truth'] for r in group) for key in ('RAW','GAMMA','NN8')}))
    report=dict(status='PC_INTEGER_REFERENCE_ONLY',selection='First 10 official SVHN test indices per digit, fixed before diagnostic inference',
        model_frozen_before_diagnostic=True,summary=summary,results=rows,
        limitations='Synthetic RGB brightness is not measured illumination/lux or real low-light capture. Images have supplied digit ROIs. This diagnostic was not used to select/retrain either network. No FPGA output readback.')
    (OUT/'synthetic_light_diagnostic.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('FROZEN_LIGHT_DIAGNOSTIC_COMPLETE',json.dumps(summary),flush=True)

if __name__=='__main__':main()
