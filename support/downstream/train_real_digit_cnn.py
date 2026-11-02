"""Small real-photo CNN, fixed-point reference and frozen holdout evaluation."""
from pathlib import Path
import hashlib,json,time,math
import numpy as np
from PIL import Image
import torch
from torch import nn
from train_real_digit import ROOT,OLD,REAL,SEED,backgrounds,prepare,TEST
from digit_model import IntegerDigit,round_away,rshift
from prepare_digit_hls import sample

OUT=ROOT/'cnn_candidate'

class RealDigitCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1=nn.Conv2d(1,8,3,padding=1)
        self.conv2=nn.Conv2d(8,16,3,padding=1)
        self.fc1=nn.Linear(16*7*7,32);self.fc2=nn.Linear(32,11)
    def forward(self,x):
        x=x.reshape(-1,1,28,28)
        x=torch.nn.functional.max_pool2d(torch.relu(self.conv1(x)),2)
        x=torch.nn.functional.max_pool2d(torch.relu(self.conv2(x)),2)
        return self.fc2(torch.relu(self.fc1(x.flatten(1))))

class IntegerCNN:
    def __init__(self,state):
        self.s={k:round_away(v.numpy()*(1048576 if k.endswith('bias') else 4096)) for k,v in state.items()}
        for k,v in self.s.items():
            assert np.abs(v).max()<(1<<31 if k.endswith('bias') else 32768)
        self.ranges={}

    def activate(self,acc,name):
        self.ranges[name]=dict(acc_min=int(acc.min()),acc_max=int(acc.max()))
        assert np.abs(acc).max()<(1<<39)
        return np.clip(rshift(acc,12),0,1048575)

    def conv(self,x,name):
        win=np.lib.stride_tricks.sliding_window_view(np.pad(x,((0,0),(0,0),(1,1),(1,1))),(3,3),axis=(2,3))
        acc=np.einsum('nchwkl,ockl->nohw',win,self.s[name+'.weight'],optimize=True)+self.s[name+'.bias'][None,:,None,None]
        z=self.activate(acc,name)
        n,c,h,w=z.shape
        return z.reshape(n,c,h//2,2,w//2,2).max((3,5))

    def infer(self,x):
        x=np.asarray(x,np.int64).reshape(-1,1,28,28)
        z=self.conv(self.conv(x,'conv1'),'conv2').reshape(len(x),-1)
        z=self.activate(z@self.s['fc1.weight'].T+self.s['fc1.bias'],'fc1')
        logits=z@self.s['fc2.weight'].T+self.s['fc2.bias']
        assert np.abs(logits).max()<(1<<39)
        return logits.argmax(1),logits

@torch.inference_mode()
def predict(m,x):return torch.cat([m(z).argmax(1) for z in x.split(512)]).numpy()

def evaluate(m,q,x,y,tag):
    floating=predict(m,torch.from_numpy(x.copy()).float()/256)
    preds=[];start=time.monotonic()
    for i in range(0,len(x),128):
        preds.append(q.infer(x[i:i+128])[0])
        if i%4096==0:print('CNN_INTEGER_EVALUATION',tag,i,len(x),round(time.monotonic()-start,1),flush=True)
    integer=np.concatenate(preds)
    report=dict(n=len(y),float_accuracy=float((floating==y).mean()),integer_accuracy=float((integer==y).mean()),
        float_integer_agreement=float((floating==integer).mean()),correct=int((integer==y).sum()),
        predicted_background=int((integer==10).sum()),
        per_digit={str(k):dict(n=int((y==k).sum()),correct=int(((integer==y)&(y==k)).sum())) for k in sorted(set(y.tolist()))})
    return report,integer

def conservative_bounds(q):
    lower=np.zeros(1,np.int64);upper=np.full(1,255,np.int64);rows=[]
    for name in ('conv1','conv2','fc1','fc2'):
        w=q.s[name+'.weight'];b=q.s[name+'.bias']
        if name.startswith('conv'):
            lo=np.minimum(lower,0);hi=np.maximum(upper,0)
            a=(np.maximum(w,0)*lo[None,:,None,None]+np.minimum(w,0)*hi[None,:,None,None]).sum((1,2,3))+b
            z=(np.maximum(w,0)*hi[None,:,None,None]+np.minimum(w,0)*lo[None,:,None,None]).sum((1,2,3))+b
        else:
            if name=='fc1':lower=np.repeat(lower,49);upper=np.repeat(upper,49)
            a=np.maximum(w,0)@lower+np.minimum(w,0)@upper+b
            z=np.maximum(w,0)@upper+np.minimum(w,0)@lower+b
        assert min(a)>-(1<<39) and max(z)<(1<<39)
        rows.append(dict(layer=name,acc_min=int(a.min()),acc_max=int(z.max()),bits=40))
        lower=np.clip(rshift(a,12),0,1048575);upper=np.clip(rshift(z,12),0,1048575)
    return rows

def main():
    OUT.mkdir(exist_ok=True)
    assert not (OUT/'training_report.json').exists(),'Preserve frozen completed CNN'
    torch.set_num_threads(4);torch.manual_seed(SEED+10);rng=np.random.default_rng(SEED+10)
    data=np.load(ROOT/'data/train_board_gray.npz');x,y=data['x'],data['y']
    split=np.load(ROOT/'split_indices.npz');ti,vi=split['train'],split['validation']
    bx,by=backgrounds(5000,SEED+1);vx,vy=backgrounds(500,SEED+2)
    trainx=torch.from_numpy(np.concatenate([x[ti],bx])).float()/256
    trainy=torch.from_numpy(np.concatenate([y[ti],by])).long()
    valx=torch.from_numpy(np.concatenate([x[vi],vx])).float()/256
    valy=np.concatenate([y[vi],vy]);valdim=torch.floor(valx[:len(vi)]*256*.25+.5)/256
    m=RealDigitCNN();opt=torch.optim.AdamW(m.parameters(),lr=.002,weight_decay=.0001)
    epochs=36;schedule=torch.optim.lr_scheduler.CosineAnnealingLR(opt,epochs,eta_min=.0001)
    best=-1;history=[];start=time.monotonic()
    for epoch in range(1,epochs+1):
        m.train();total=0.
        for ids in torch.randperm(len(trainx)).split(256):
            z=trainx[ids].clone();dx=int(rng.integers(0,5));dy=int(rng.integers(0,5))
            z=torch.nn.functional.pad(z[:,None],(2,2,2,2),mode='replicate')[:,:,dy:dy+28,dx:dx+28].squeeze(1)
            mean=z.mean((1,2),keepdim=True)
            z=(z-mean)*torch.empty(len(ids),1,1).uniform_(.75,1.25)+mean
            gain=torch.where(torch.rand(len(ids),1,1)<.35,
                torch.empty(len(ids),1,1).uniform_(.20,.75),torch.empty(len(ids),1,1).uniform_(.75,1.15))
            z=(z*gain+torch.randn_like(z)*.005).clamp(0,255/256)
            loss=torch.nn.functional.cross_entropy(m(z),trainy[ids])
            opt.zero_grad(set_to_none=True);loss.backward();opt.step();total+=float(loss.detach())*len(ids)
        schedule.step();m.eval();p=predict(m,valx);pd=predict(m,valdim)
        a=float((p[:len(vi)]==valy[:len(vi)]).mean());ad=float((pd==valy[:len(vi)]).mean());blank=float((p[len(vi):]==10).mean())
        score=.70*a+.25*ad+.05*blank
        row=dict(epoch=epoch,loss=total/len(trainx),validation_real_accuracy=a,validation_synthetic_dim_accuracy=ad,
            validation_blank_accuracy=blank,checkpoint_score=score,elapsed_seconds=round(time.monotonic()-start,2))
        print(json.dumps(row),flush=True);history.append(row)
        if score>best:best=score;torch.save(m.state_dict(),OUT/'best_validation.pth')
        (OUT/'training_progress.json').write_text(json.dumps(history,indent=2),encoding='utf-8')
    m.load_state_dict(torch.load(OUT/'best_validation.pth',weights_only=True));m.eval()
    torch.save(m.state_dict(),OUT/'real_digit_cnn.pth')
    freeze=dict(sha256=hashlib.sha256((OUT/'real_digit_cnn.pth').read_bytes()).hexdigest(),
        selection='Train-split validation only',official_test_used_for_fit_or_selection=False,
        architecture='Conv3x3(1->8),ReLU,MaxPool2,Conv3x3(8->16),ReLU,MaxPool2,784->32 ReLU->11',
        parameters=sum(v.numel() for v in m.parameters()))
    (OUT/'frozen_candidate.json').write_text(json.dumps(freeze,indent=2),encoding='utf-8')
    q=IntegerCNN(m.state_dict());bounds=conservative_bounds(q);np.savez(OUT/'integer_weights.npz',**q.s)
    tx,ty=prepare('official_test',TEST,'eb5a983be6a315427106f1b164d9cef3')
    test,p=evaluate(m,q,tx,ty,'official_test')
    np.savez(OUT/'official_test_predictions.npz',labels=ty,predictions=p)
    rows=[];manifest=json.loads((REAL/'case_manifest.json').read_text(encoding='utf-8'))
    for c in manifest['cases']:
        row=dict(id=c['id'],truth=c['truth'],group=c['group'])
        for kind,path in [('raw',REAL/'inputs'/(c['id']+'.png')),('enh',REAL/'pc_reference_previews'/(c['id']+'_PC_REFERENCE.png'))]:
            gray=sample(np.array(Image.open(path).convert('RGB')),480,112)
            label,logits=q.infer(gray);row[kind+'_prediction']=int(label[0]);row[kind+'_correct']=int(label[0])==c['truth']
        rows.append(row)
    report=dict(status='OFFLINE_TRAINED_NOT_FPGA_VERIFIED',model=freeze,seed=SEED+10,history=history,
        training=dict(real_train=len(ti),real_validation=len(vi),blank_train=5000,blank_validation=500,
            split_file=str(ROOT/'split_indices.npz'),test_used_for_training=False),
        integer_format='Signed Q12 int16 weights, Q20 int32 biases, rounded Q8 nonnegative 20-bit activations; int40 accumulators',
        conservative_integer_bounds=bounds,official_svhn_test=test,
        previously_seen_regression_33=dict(n=33,raw_correct=sum(r['raw_correct'] for r in rows),
            enhanced_pc_reference_correct=sum(r['enh_correct'] for r in rows),results=rows,
            caveat='Previously seen regression pictures. ENH is CPU enhancement reference, not captured FPGA output.'),
        limitations=['Given ROI single digit; no automatic whole-scene detection or plate OCR.',
            'Synthetic brightness augmentation is not real low-light or camera verification.',
            'Blank controls do not establish unknown-object rejection.',
            'Weights are not deployed. Board resource/timing feasibility and numerical consistency need verification.',
            'Enhancement model is unchanged. Recognition improvement alone does not prove enhancement benefit.'])
    (OUT/'training_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('REAL_CNN_TRAIN_COMPLETE',json.dumps(dict(test=test,regression_raw=report['previously_seen_regression_33']['raw_correct'],
        regression_enh=report['previously_seen_regression_33']['enhanced_pc_reference_correct'])),flush=True)

if __name__=='__main__':main()
