"""Train a small recognizer on MNIST and augmented printed digits, then freeze.

No enhanced/dark test examples are used to select weights. Low-light evaluation
is a subsequent fixed-protocol experiment; it may show no gain or regressions.
"""
from pathlib import Path
import gzip
import hashlib
import json
import struct
import time
import urllib.request
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import torch
from digit_model import ROOT,DigitMLP,IntegerDigit

SEED=2026102302
torch.manual_seed(SEED);torch.set_num_threads(4)
rng=np.random.default_rng(SEED)
TRAIN_FONTS=['arialbd.ttf','calibrib.ttf','timesbd.ttf','verdanab.ttf','tahomabd.ttf','courbd.ttf']
TEST_FONTS=['consolab.ttf','georgiab.ttf']


def font_digit(label,font,rng,jitter=True):
    canvas=Image.new('L',(112,112),0)
    size=int(rng.integers(68,91)) if jitter else 80
    f=ImageFont.truetype(str(Path('C:/Windows/Fonts')/font),size)
    d=ImageDraw.Draw(canvas);box=d.textbbox((0,0),str(label),font=f)
    dx=int(rng.integers(-10,11)) if jitter else 0
    dy=int(rng.integers(-9,10)) if jitter else 0
    d.text(((112-box[2]+box[0])//2-box[0]+dx,(112-box[3]+box[1])//2-box[1]+dy),str(label),font=f,fill=255)
    if jitter:canvas=canvas.rotate(float(rng.uniform(-9,9)),resample=Image.Resampling.BICUBIC)
    return np.array(canvas.resize((28,28),Image.Resampling.LANCZOS))


def mnist():
    res=[('train-images-idx3-ubyte.gz','f68b3c2dcbeaaa9fbdd348bbdeb94873'),
         ('train-labels-idx1-ubyte.gz','d53e105ee54ea40749a09fcbcd1e9432'),
         ('t10k-images-idx3-ubyte.gz','9fb629c4189551a2d022fa330f9573f3'),
         ('t10k-labels-idx1-ubyte.gz','ec29112dd5afa0611ce80d1b7f02629c')]
    dest=ROOT/'mnist';dest.mkdir(parents=True,exist_ok=True)
    data=[];manifest=[]
    for name,md5 in res:
        p=dest/name;url='https://ossci-datasets.s3.amazonaws.com/mnist/'+name
        if not p.exists():p.write_bytes(urllib.request.urlopen(url,timeout=90).read())
        b=p.read_bytes();assert hashlib.md5(b).hexdigest()==md5
        manifest.append(dict(url=url,sha256=hashlib.sha256(b).hexdigest(),md5=md5))
        b=gzip.decompress(b);magic,n=struct.unpack_from('>II',b)
        if magic==2051:
            assert struct.unpack_from('>II',b,8)==(28,28)
            a=np.frombuffer(b,dtype=np.uint8,offset=16).reshape(n,28,28).copy()
        else:
            assert magic==2049
            a=np.frombuffer(b,dtype=np.uint8,offset=8).copy()
        data.append(a)
        print('MNIST_VERIFIED',name,flush=True)
    (ROOT/'mnist_manifest.json').write_text(json.dumps(manifest,indent=2))
    return data


def printed(n,fonts,seed):
    g=np.random.default_rng(seed)
    x=[font_digit(i%10,fonts[int(g.integers(len(fonts)))],g) for i in range(n)]
    return np.stack(x),np.arange(n)%10


def background(n,seed):
    g=np.random.default_rng(seed)
    x=np.clip(g.normal(3,2,(n,28,28)),0,255).astype(np.uint8)
    for i in range(n):
        if i%3==0:x[i]=0
        if i%3==1:x[i]=g.integers(0,35)
    return x,np.full(n,10,dtype=np.int64)


def main():
    ROOT.mkdir(exist_ok=True)
    assert not (ROOT/'training_validation.json').exists(),'Do not overwrite a validated frozen model'
    mx,my,tx,ty=mnist()
    idx=rng.permutation(len(mx));train_idx=idx[:55000];val_idx=idx[55000:]
    px,py=printed(18000,TRAIN_FONTS,SEED+1);vx,vy=printed(2000,TRAIN_FONTS,SEED+2)
    bx,by=background(4000,SEED+3);bvx,bvy=background(500,SEED+4)
    x=np.concatenate([mx[train_idx],px,bx]);y=np.concatenate([my[train_idx],py,by]).astype(np.int64)
    valx=np.concatenate([mx[val_idx],vx,bvx]);valy=np.concatenate([my[val_idx],vy,bvy]).astype(np.int64)
    x=torch.from_numpy(x.copy()).float().reshape(-1,784)/256
    y=torch.from_numpy(y)
    xv=torch.from_numpy(valx.copy()).float().reshape(-1,784)/256
    yv=torch.from_numpy(valy)
    m=DigitMLP();opt=torch.optim.Adam(m.parameters(),lr=1e-3)
    best=-1;history=[];start=time.time()
    for epoch in range(1,25):
        m.train();order=torch.randperm(len(x));losses=[]
        for batch in order.split(256):
            # Normal-light training augmentation only: 0.65-1.0 foreground
            # intensity, mild sensor-like noise. No test-light levels used.
            z=x[batch]*torch.empty((len(batch),1)).uniform_(0.65,1.0)
            z=(z+torch.randn_like(z)*0.006).clamp(0,255/256)
            loss=torch.nn.functional.cross_entropy(m(z),y[batch])
            opt.zero_grad(set_to_none=True);loss.backward();opt.step()
            losses.append(float(loss.detach()))
        m.eval()
        with torch.inference_mode():pred=m(xv).argmax(1);acc=float((pred==yv).float().mean())
        row=dict(epoch=epoch,loss=float(np.mean(losses)),validation_accuracy=acc,seconds=time.time()-start)
        history.append(row);print(json.dumps(row),flush=True)
        if acc>best:
            best=acc;torch.save(m.state_dict(),ROOT/'best_training.pth')
    m.load_state_dict(torch.load(ROOT/'best_training.pth',map_location='cpu',weights_only=True));m.eval()
    torch.save(m.state_dict(),ROOT/'digit_model.pth')
    state=m.state_dict();q=IntegerDigit(state);bounds=q.bounds()
    testpx,testpy=printed(120,TEST_FONTS,SEED+5)
    # Four fixed official MNIST test examples per class, without outcome selection.
    tidx=np.concatenate([np.flatnonzero(ty==k)[:4] for k in range(10)])
    ex=np.concatenate([testpx,tx[tidx]])
    ey=np.concatenate([testpy,ty[tidx]]).astype(np.int64)
    np.savez(ROOT/'downstream_test_inputs.npz',images=ex,labels=ey,
             sources=np.array(['unseen_font']*len(testpx)+['MNIST_test']*len(tidx)))
    tests=[('MNIST_test',tx,ty),('unseen_fonts',testpx,testpy)]
    metrics=[]
    for name,xx,yy in tests:
        with torch.inference_mode():fl=m(torch.tensor(xx.reshape(-1,784).copy()).float()/256).argmax(1).numpy()
        qi,_=q.infer(xx)
        metrics.append(dict(name=name,n=len(yy),float_accuracy=float((fl==yy).mean()),integer_accuracy=float((qi==yy).mean()),
                            integer_float_agreement=float((fl==qi).mean())))
    assert min(v['integer_float_agreement'] for v in metrics)>=0.995
    assert metrics[0]['integer_accuracy']>=0.94 and metrics[1]['integer_accuracy']>=0.9
    np.savez(ROOT/'digit_weights_integer.npz',w1=q.w1,b1=q.b1,w2=q.w2,b2=q.b2)
    report=dict(status='PASS',seed=SEED,architecture='784 -> 32 ReLU -> 11 logits',parameters=sum(p.numel() for p in m.parameters()),
        classes='0-9 and 10=blank/background; not a calibrated rejection mechanism for arbitrary objects',
        training=dict(mnist_train=55000,printed=18000,background=4000,train_fonts=TRAIN_FONTS,validation_mnist=5000,validation_printed=2000),
        validation_best_accuracy=best,history=history,clean_test=metrics,integer_bounds=bounds,
        test_fonts=TEST_FONTS,recognizer_sha256=hashlib.sha256((ROOT/'digit_model.pth').read_bytes()).hexdigest(),
        limitations='Single centered white digit on black; fixed ROI. No plate detection, Chinese characters, multi-character segmentation, or real camera verification. Enhancement benefit is not assumed.')
    (ROOT/'training_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    # Printable/displayable target sheets: each file contains exactly one digit.
    chart=ROOT/'demo_targets';chart.mkdir(exist_ok=True)
    for k in range(10):
        im=font_digit(k,'consolab.ttf',np.random.default_rng(SEED),jitter=False)
        Image.fromarray(im).resize((896,896),Image.Resampling.NEAREST).save(chart/f'digit_{k}.png')
    print('DIGIT_CLASSIFIER_TRAIN_AND_INTEGER_PASS',json.dumps(metrics),flush=True)


if __name__=='__main__':main()
