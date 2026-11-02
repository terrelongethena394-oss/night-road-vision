"""Fit a label-blind brightness gate on TRAIN validation images only.

Both routes use the same frozen recognizer; runtime sees brightness, no label.
The enhancement weights and recognition weights remain unchanged.
"""
from pathlib import Path
import hashlib,importlib.util,json,time
import numpy as np
from PIL import Image
from scipy.io import loadmat
import torch
from train_real_digit_cnn import OUT,IntegerCNN
from train_real_digit import ROOT
from prepare_real_cnn_images import pooled

UPGRADE=Path('E:/FPGA_Enhance_Work/model_upgrade_20261023')

def main():
    dest=OUT/'exposure_gate';dest.mkdir(exist_ok=True)
    assert not (dest/'gate_config.json').exists(),'Preserve fitted gate'
    mat=loadmat(ROOT/'data/train_32x32.mat');rgb=mat['X'].transpose(3,0,1,2);y=mat['y'].reshape(-1)%10
    split=np.load(ROOT/'split_indices.npz');vi=split['validation'];ti=split['train']
    ids=np.concatenate([vi[y[vi]==k][:50] for k in range(10)])
    assert not set(ids)&set(ti) and len(ids)==500
    q=IntegerCNN(torch.load(OUT/'real_digit_cnn.pth',weights_only=True,map_location='cpu'))
    spec=importlib.util.spec_from_file_location('fixed8',UPGRADE/'hls8/fixed8.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    state=torch.load(UPGRADE/'student8/best_student8.pth',weights_only=True,map_location='cpu')
    enhance=mod.FixedNanoDCE({k:v.numpy() for k,v in state.items()})
    rows=[];start=time.monotonic()
    for i,index in enumerate(ids):
        tile=np.array(Image.fromarray(rgb[index]).resize((224,224),Image.Resampling.LANCZOS))
        tile[:,:,0]&=248;tile[:,:,1]&=252;tile[:,:,2]&=248
        for alpha in (1.,.25):
            raw=np.floor(tile.astype(np.float64)*alpha+.5).astype(np.uint8)
            context=np.full((230,230,3),int(16*alpha+.5),np.uint8);context[3:227,3:227]=raw
            enh=enhance.infer(context)[0][3:227,3:227]
            v=raw.astype(np.int64);luma=(77*v[:,:,0]+150*v[:,:,1]+29*v[:,:,2]+128)>>8
            mean=int((luma.sum()+25088)//50176)
            rp,_=q.infer(pooled(raw));ep,_=q.infer(pooled(enh))
            rows.append(dict(train_file_index=int(index),truth=int(y[index]),alpha=alpha,mean=mean,raw=int(rp[0]),nn8=int(ep[0])))
        if (i+1)%50==0:print('GATE_VALIDATION_ONLY',i+1,500,round(time.monotonic()-start,1),flush=True)
    scores=[]
    for threshold in range(-1,256):
        correct=sum((r['nn8'] if r['mean']<=threshold else r['raw'])==r['truth'] for r in rows)
        scores.append(dict(threshold=threshold,correct=correct))
    # Lower threshold wins ties, preferring fewer unnecessary enhancements.
    best=max(scores,key=lambda r:(r['correct'],-r['threshold']))
    groups=[]
    for alpha in (1.,.25):
        group=[r for r in rows if r['alpha']==alpha]
        groups.append(dict(alpha=alpha,n=len(group),raw_correct=sum(r['raw']==r['truth'] for r in group),
            nn8_correct=sum(r['nn8']==r['truth'] for r in group),
            gated_correct=sum((r['nn8'] if r['mean']<=best['threshold'] else r['raw'])==r['truth'] for r in group)))
    config=dict(status='VALIDATION_CALIBRATED_NOT_CAMERA_VERIFIED',threshold=best['threshold'],
        rule='Use NN8 when rounded integer ROI luma mean <= threshold, otherwise bypass; same CNN weights for both routes.',
        mean_formula='gray=(77R+150G+29B+128)>>8; mean=(sum(gray)+25088)//50176 over224x224',
        selection='First 50 stored validation indices per class, 500 from SVHN TRAIN file, alpha1 and synthetic alpha.25. No official test or Wikimedia images used.',
        recognizer_sha256=hashlib.sha256((OUT/'real_digit_cnn.pth').read_bytes()).hexdigest(),
        best_validation=best,validation_groups=groups,
        limitation='Validation fit, not independent accuracy. Synthetic exposure is not real night/lux. A single ROI mean cannot handle every scene.')
    (dest/'validation_records.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    (dest/'threshold_scores.json').write_text(json.dumps(scores,indent=2),encoding='utf-8')
    (dest/'gate_config.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
    print('EXPOSURE_GATE_FROZEN',json.dumps(config),flush=True)

if __name__=='__main__':main()
