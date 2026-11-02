"""Train a compact, hardware-oriented real-photo digit baseline.

No official SVHN test or previously demonstrated Wikimedia photograph is used
for fitting/checkpoint selection. This remains given-ROI digit classification.
"""
from pathlib import Path
import hashlib,json,math,time
import numpy as np
from PIL import Image
from scipy.io import loadmat
import torch
from torch import nn
from digit_model import IntegerDigit
from prepare_digit_hls import sample

ROOT=Path('E:/FPGA_Enhance_Work/real_digit_training_20261025')
OLD=Path('E:/FPGA_Enhance_Work/digit_recognition_20261023')
REAL=Path('E:/FPGA_Enhance_Work/real_scene_test_scaled_20261025')
TEST=Path('E:/FPGA_Enhance_Work/real_scene_test_20261025/test_32x32.mat')
SEED=2026102503
HIDDEN=64

class RealDigitMLP(nn.Module):
    def __init__(self):
        super().__init__();self.fc1=nn.Linear(784,HIDDEN);self.fc2=nn.Linear(HIDDEN,11)
    def forward(self,x):
        return self.fc2(torch.relu(self.fc1(x.reshape(-1,784))))

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def exact_gray(rgb):
    """Same 224 ROI resize/RGB565 and rounded 8x8 pooling as image tests."""
    rgb=np.array(Image.fromarray(rgb).resize((224,224),Image.Resampling.LANCZOS))
    rgb[:,:,0]&=248;rgb[:,:,1]&=252;rgb[:,:,2]&=248
    rgb=rgb.astype(np.uint16)
    g=(77*rgb[:,:,0]+150*rgb[:,:,1]+29*rgb[:,:,2]+128)>>8
    return ((g.reshape(28,8,28,8).sum((1,3))+32)>>6).astype(np.uint8)

def prepare(split,path,md5):
    assert hashlib.md5(path.read_bytes()).hexdigest()==md5
    cache=ROOT/'data'/(split+'_board_gray.npz')
    if cache.exists():
        d=np.load(cache);return d['x'],d['y']
    d=loadmat(path);images=d['X'].transpose(3,0,1,2);y=d['y'].reshape(-1)%10
    x=np.empty((len(y),28,28),np.uint8);start=time.monotonic()
    for i,image in enumerate(images):
        x[i]=exact_gray(image)
        if (i+1)%5000==0:print('EXACT_PREPROCESS',split,i+1,len(y),round(time.monotonic()-start,1),flush=True)
    np.savez_compressed(cache,x=x,y=y)
    return x,y

def backgrounds(n,seed):
    # Explicit blank controls, not evidence of general unknown-object rejection.
    rng=np.random.default_rng(seed)
    base=rng.uniform(0,250,(n,1,1));yy,xx=np.mgrid[-1:1:28j,-1:1:28j]
    slope=rng.normal(0,15,(n,2,1,1))
    v=base+slope[:,0]*xx+slope[:,1]*yy+rng.normal(0,3,(n,28,28))
    return np.clip(v,0,255).astype(np.uint8),np.full(n,10,np.int64)

@torch.inference_mode()
def predict(model,x):
    return torch.cat([model(z).argmax(1) for z in x.split(1024)]).numpy()

def metrics(model,q,x,y):
    floating=predict(model,torch.from_numpy(x.copy()).float()/256)
    # Chunk int64 matmul to keep RAM bounded on Windows.
    integer=np.concatenate([q.infer(z)[0] for z in np.array_split(x,max(1,math.ceil(len(x)/512)))])
    return dict(n=len(y),float_accuracy=float((floating==y).mean()),integer_accuracy=float((integer==y).mean()),
        integer_float_agreement=float((floating==integer).mean()),
        correct=int((integer==y).sum()),predicted_background=int((integer==10).sum()),
        per_digit={str(k):dict(n=int((y==k).sum()),correct=int(((integer==y)&(y==k)).sum())) for k in sorted(set(y.tolist()))}),integer

def main():
    ROOT.mkdir(exist_ok=True)
    assert not (ROOT/'training_report.json').exists(),'Keep a completed candidate frozen'
    torch.set_num_threads(4);torch.manual_seed(SEED);rng=np.random.default_rng(SEED)
    start=time.monotonic()
    x,y=prepare('train',ROOT/'data/train_32x32.mat','e26dedcc434d2e4c54c9b2d4a06d8373')
    assert len(y)==73257
    # Fixed, per-class split before fitting; the official test is never used here.
    vi=[];ti=[]
    for k in range(10):
        ids=rng.permutation(np.flatnonzero(y==k));vi.extend(ids[:800]);ti.extend(ids[800:])
    vi=np.array(vi);ti=np.array(ti)
    np.savez(ROOT/'split_indices.npz',train=ti,validation=vi)
    bx,by=backgrounds(5000,SEED+1);vx,vy=backgrounds(500,SEED+2)
    trainx=torch.from_numpy(np.concatenate([x[ti],bx])).float()/256
    trainy=torch.from_numpy(np.concatenate([y[ti],by])).long()
    valx=torch.from_numpy(np.concatenate([x[vi],vx])).float()/256
    valy=np.concatenate([y[vi],vy])
    # Synthetic dim validation uses only the validation partition.
    valdim=torch.floor(valx[:len(vi)]*256*.25+.5)/256
    model=RealDigitMLP();opt=torch.optim.AdamW(model.parameters(),lr=.002,weight_decay=.0001)
    epochs=64;scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(opt,epochs,eta_min=.0001)
    best=-1;history=[]
    for epoch in range(1,epochs+1):
        model.train();total=0.;order=torch.randperm(len(trainx))
        for ids in order.split(512):
            z=trainx[ids].clone()
            # Preserve digit direction; no horizontal flips and no test images.
            dx=int(rng.integers(0,5));dy=int(rng.integers(0,5))
            z=torch.nn.functional.pad(z[:,None],(2,2,2,2),mode='replicate')[:,:,dy:dy+28,dx:dx+28].squeeze(1)
            mean=z.mean((1,2),keepdim=True)
            z=(z-mean)*torch.empty(len(ids),1,1).uniform_(.75,1.25)+mean
            normal=torch.empty(len(ids),1,1).uniform_(.75,1.15)
            dark=torch.empty(len(ids),1,1).uniform_(.20,.75)
            gain=torch.where(torch.rand(len(ids),1,1)<.35,dark,normal)
            z=(z*gain+torch.randn_like(z)*.005).clamp(0,255/256)
            loss=torch.nn.functional.cross_entropy(model(z),trainy[ids])
            opt.zero_grad(set_to_none=True);loss.backward();opt.step();total+=float(loss.detach())*len(ids)
        scheduler.step();model.eval()
        p=predict(model,valx);pd=predict(model,valdim)
        a=float((p[:len(vi)]==valy[:len(vi)]).mean());ad=float((pd==valy[:len(vi)]).mean())
        blank=float((p[len(vi):]==10).mean());score=.70*a+.25*ad+.05*blank
        row=dict(epoch=epoch,loss=total/len(trainx),validation_real_accuracy=a,
            validation_synthetic_dim_accuracy=ad,validation_blank_accuracy=blank,
            checkpoint_score=score,elapsed_seconds=round(time.monotonic()-start,2))
        history.append(row);print(json.dumps(row),flush=True)
        if score>best:
            best=score;torch.save(model.state_dict(),ROOT/'best_validation.pth')
        (ROOT/'training_progress.json').write_text(json.dumps(history,indent=2),encoding='utf-8')
    model.load_state_dict(torch.load(ROOT/'best_validation.pth',weights_only=True));model.eval()
    torch.save(model.state_dict(),ROOT/'real_digit_model.pth')
    q=IntegerDigit(model.state_dict());bounds=q.bounds()
    np.savez(ROOT/'real_digit_weights_integer.npz',w1=q.w1,b1=q.b1,w2=q.w2,b2=q.b2)
    # Freeze identity BEFORE touching official test data for the new candidate.
    freeze=dict(sha256=sha(ROOT/'real_digit_model.pth'),selection='Train-split validation only',
        official_test_used_for_fit_or_selection=False,architecture='784 -> 64 ReLU -> 11',parameters=sum(p.numel() for p in model.parameters()))
    (ROOT/'frozen_candidate.json').write_text(json.dumps(freeze,indent=2),encoding='utf-8')
    tx,ty=prepare('official_test',TEST,'eb5a983be6a315427106f1b164d9cef3')
    test,p=metrics(model,q,tx,ty)
    np.savez(ROOT/'official_test_predictions.npz',labels=ty,predictions=p)
    original=IntegerDigit(torch.load(OLD/'digit_model.pth',map_location='cpu',weights_only=True))
    op=np.concatenate([original.infer(z)[0] for z in np.array_split(tx,52)])
    test['old_integer_accuracy_same_inputs']=float((op==ty).mean())
    manifest=json.loads((REAL/'case_manifest.json').read_text(encoding='utf-8'))
    rows=[]
    for c in manifest['cases']:
        row=dict(id=c['id'],truth=c['truth'],group=c['group'])
        for kind,path in [('raw',REAL/'inputs'/(c['id']+'.png')),('enh',REAL/'pc_reference_previews'/(c['id']+'_PC_REFERENCE.png'))]:
            gray=sample(np.array(Image.open(path).convert('RGB')),480,112)
            label,logits=q.infer(gray);row[kind+'_prediction']=int(label[0]);row[kind+'_correct']=int(label[0])==c['truth']
        rows.append(row)
    report=dict(status='OFFLINE_TRAINED_NOT_FPGA_VERIFIED',seed=SEED,model=freeze,
        data=dict(svhn_train=65257,svhn_validation=8000,blank_train=5000,blank_validation=500,
            preprocessing='LANCZOS 32->224, RGB565 truncation, integer luma and rounded 8x8 average ->28x28',
            augmentation='replicate translation +/-2px, contrast, brightness .20-1.15, mild noise; train split only',
            no_official_test_images_used_for_fit_or_selection=True),
        checkpoint_score=best,history=history,integer_bounds=bounds,official_svhn_test=test,
        previously_seen_regression_33=dict(n=33,raw_correct=sum(r['raw_correct'] for r in rows),
            enhanced_pc_reference_correct=sum(r['enh_correct'] for r in rows),results=rows,
            caveat='Previously seen regression set, not a newly untouched benchmark. ENH images are CPU references, not FPGA readback.'),
        limitations=['Given ROI single digit; no automatic detection, multi-digit OCR or plate recognition.',
            'SVHN normal photographs are not a measured real low-light dataset.',
            'Blank controls do not establish arbitrary unknown-object rejection.',
            'New integer classifier is not yet built/downloaded; old board numerical mismatch remains unresolved.',
            'Enhancement network was not retrained. Real-camera performance remains untested.'])
    (ROOT/'training_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('REAL_DIGIT_TRAINING_COMPLETE',json.dumps(dict(official_test=test,regression_raw=report['previously_seen_regression_33']['raw_correct'],
        regression_enh=report['previously_seen_regression_33']['enhanced_pc_reference_correct'])),flush=True)

if __name__=='__main__':main()
