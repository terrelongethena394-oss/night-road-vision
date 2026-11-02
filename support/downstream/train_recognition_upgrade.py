"""Train from train splits; select with validation only. Test caches are not opened."""
import json,time,math,sys
import numpy as np
import torch
import torch.nn.functional as F
from recognition_upgrade_common import ROOT,BASE,OLD,SEED,UpgradeCNN,initialize_from_old,normalize_np,normalize_torch,sha,write
from train_real_digit import backgrounds

@torch.inference_mode()
def logits(model,x):
    return torch.cat([model(z) for z in x.split(512)])

def bank(x,y):
    return torch.from_numpy(np.asarray(x).copy()).float()/256,torch.from_numpy(np.asarray(y).copy()).long()

def main():
    wide=len(sys.argv)>1 and sys.argv[1]=='wide'
    extended=wide or len(sys.argv)>1 and sys.argv[1]=='extended'
    out=ROOT/('run03' if wide else ('run02' if extended else 'run01'));out.mkdir(exist_ok=True)
    assert not (out/'training_complete.json').exists(),'Preserve completed experiment'
    assert (ROOT/'data_complete.json').exists()
    torch.set_num_threads(4);torch.manual_seed(SEED);rng=np.random.default_rng(SEED)
    protocol_sha=sha(ROOT/'training_protocol.json');start=time.monotonic()
    steps=12000 if wide else (20000 if extended else 2000);interval=500 if extended else 100
    ns=256 if extended else 128;nm=128 if extended else 48;nt=ns+64
    if wide:
        previous=json.loads((ROOT/'run02/test/results.json').read_text())
        assert not previous['accepted'] and not previous['gates']['chars']
        write(out/'training_revision.json',dict(reason='Previous frozen candidate passed four gates but real-character test improved5/120, less than required6/120. No per-image test diagnosis or test-based epoch selection. Increase hidden head64->128, add domain-wide affine augmentation, reduce ambiguous real-letter background exposure.',initialization_sha256=sha(ROOT/'run02/best_eligible.pth'),steps=steps,hidden=128,batch=dict(svhn=ns,views=64,fonts=96,mnist=nm,chars=48,background_flat=28,background_letter=4),lr=.0003,distill_weight=.35,acceptance='Original validation and heldout numeric thresholds unchanged',test_data_used_for_fit=False,evaluation_caveat='Official external test sets now reused as engineering acceptance/regression benchmarks after aggregate feedback; do not describe this iteration as a new blind test. No test image used in gradient training or checkpoint selection.'))
    elif extended:
        write(out/'training_revision.json',dict(reason='First2000steps failed validation; no heldout tests opened. Extend fitting, increase original SVHN and MNIST exposure, reduce teacher penalty to allow supervised improvement.',initialization_sha256=sha(ROOT/'run01/last.pth'),steps=steps,batch=dict(svhn=ns,views=64,fonts=96,mnist=nm,chars=48,background=32),lr=.0004,distill_weight=.35,acceptance='Original validation and heldout acceptance unchanged',test_data_used=False))
    teacher=UpgradeCNN(32);teacher.load_state_dict(torch.load(OLD/'real_digit_cnn.pth',weights_only=True));teacher.eval()
    for p in teacher.parameters():p.requires_grad_(False)
    d=np.load(BASE/'real_digit_training_20261025/data/train_board_gray.npz')
    split=np.load(BASE/'real_digit_training_20261025/split_indices.npz');ti,vi=split['train'],split['validation']
    raw_train=d['x'][ti];raw_val=d['x'][vi];sy=d['y'][ti];vy=d['y'][vi]
    sv=bank(normalize_np(raw_train),sy)
    tv=logits(teacher,bank(raw_train,sy)[0]);svteacher=(tv,tv.argmax(1)==sv[1])
    v=np.load(BASE/'robust_digit_20261025/train_views.npz')
    keys=['raw_normal','raw_dim','nn8_normal','nn8_dim','multinex_normal','multinex_dim']
    vx=np.concatenate([v[k] for k in keys]);yl=np.tile(v['labels'],6)
    views=bank(normalize_np(vx),yl);vl=logits(teacher,bank(vx,yl)[0]);viewteacher=(vl,vl.argmax(1)==views[1])
    valviews=np.load(BASE/'robust_digit_20261025/validation_views.npz')
    vv=bank(normalize_np(np.concatenate([valviews[k] for k in keys])),np.tile(valviews['labels'],6))
    fd=np.load(ROOT/'data/fonts_train.npz');fonts=bank(normalize_np(fd['x']),fd['y'])
    md=np.load(ROOT/'data/mnist_train.npz');mnist=bank(normalize_np(md['x']),md['y'])
    cd=np.load(ROOT/'data/chars_train.npz');pos=cd['y']<10
    chars=bank(normalize_np(cd['x'][pos]),cd['y'][pos]);letters=bank(normalize_np(cd['x'][~pos]),cd['y'][~pos])
    bx,by=backgrounds(5000,SEED+13);bg=bank(normalize_np(bx),by)
    val={'svhn':bank(normalize_np(raw_val),vy),'views':vv}
    for tag in ['fonts','mnist','chars']:
        a=np.load(ROOT/'data'/f'{tag}_validation.npz');mask=a['y']<10
        val[tag]=bank(normalize_np(a['x'][mask]),a['y'][mask])
    bx,by=backgrounds(1000,SEED+14);val['background']=bank(normalize_np(bx),by)
    # Baseline controls distinguish normalization from weight training.
    baseline={}
    for tag,(x,y) in val.items():baseline[tag+'_old_normalized']=float((logits(teacher,x).argmax(1)==y).float().mean())
    baseline['svhn_old_raw']=float((logits(teacher,bank(raw_val,vy)[0]).argmax(1)==torch.from_numpy(vy)).float().mean())
    a=np.load(ROOT/'data/chars_validation.npz');mask=a['y']<10
    baseline['chars_old_raw']=float((logits(teacher,bank(a['x'][mask],a['y'][mask])[0]).argmax(1)==torch.from_numpy(a['y'][mask])).float().mean())
    write(out/'baseline_validation.json',baseline);print('BASELINE',json.dumps(baseline),flush=True)
    # Verify independent CPU normalizers on data and numerical edge controls.
    checks=np.concatenate([raw_train[:64],np.zeros((1,28,28),np.uint8),np.full((1,28,28),255,np.uint8)])
    assert np.array_equal(normalize_np(checks),(normalize_torch(torch.from_numpy(checks))*256).byte().numpy())
    model=initialize_from_old()
    if wide:
        original=torch.load(ROOT/'run02/best_eligible.pth',weights_only=True);model=UpgradeCNN(128)
        with torch.no_grad():
            for key in ['conv1.weight','conv1.bias','conv2.weight','conv2.bias']:model.state_dict()[key].copy_(original[key])
            model.fc1.weight[:64].copy_(original['fc1.weight']);model.fc1.bias[:64].copy_(original['fc1.bias'])
            model.fc2.weight[:,:64].copy_(original['fc2.weight']);model.fc2.weight[:,64:].zero_();model.fc2.bias.copy_(original['fc2.bias'])
    elif extended:model.load_state_dict(torch.load(ROOT/'run01/last.pth',weights_only=True))
    opt=torch.optim.AdamW(model.parameters(),lr=.0003 if wide else (.0004 if extended else .0005),weight_decay=.0001)
    schedule=torch.optim.lr_scheduler.CosineAnnealingLR(opt,steps,eta_min=.00003 if extended else .00008)
    history=[];best=-1;provisional=-1;loss_sum=0
    def choose(b,n):
        ids=torch.randint(len(b[0]),(n,));return b[0][ids],b[1][ids],ids
    def augment(z,invert=False):
        z=z.clone()
        if invert:
            mask=torch.rand(len(z))<.5;z[mask]=255/256-z[mask]
        if wide:
            angle=torch.empty(len(z)).uniform_(-.21,.21);scale=torch.empty(len(z)).uniform_(.85,1.15)
            theta=torch.zeros(len(z),2,3);theta[:,0,0]=theta[:,1,1]=scale*angle.cos();theta[:,0,1]=-scale*angle.sin();theta[:,1,0]=scale*angle.sin();theta[:,:,2].uniform_(-.06,.06)
            grid=F.affine_grid(theta,(len(z),1,28,28),align_corners=False)
            z=F.grid_sample(z[:,None],grid,mode='bilinear',padding_mode='border',align_corners=False).squeeze(1)
        dx=int(rng.integers(0,3));dy=int(rng.integers(0,3))
        z=F.pad(z[:,None],(1,1,1,1),mode='replicate')[:,:,dy:dy+28,dx:dx+28].squeeze(1)
        return (z+torch.randn_like(z)*.003).clamp(0,255/256)
    def validate(step):
        nonlocal best,provisional
        model.eval();r={tag:float((logits(model,x).argmax(1)==y).float().mean()) for tag,(x,y) in val.items()}
        eligible=(r['svhn']>=baseline['svhn_old_raw'] and r['chars']>=max(baseline['chars_old_raw']+.1,.7) and r['fonts']>=.9 and r['mnist']>=.95 and r['background']>=.95)
        score=.5*r['svhn']+.2*r['chars']+.15*r['fonts']+.05*r['mnist']+.1*r['views']
        row=dict(step=step,validation=r,eligible=eligible,score=score,loss_last_interval=loss_sum/interval if step else None,seconds=round(time.monotonic()-start,2))
        history.append(row);print(json.dumps(row),flush=True);write(out/'training_progress.json',history)
        if score>provisional:
            provisional=score;torch.save(model.state_dict(),out/'best_provisional.pth');write(out/'best_provisional.json',row)
        if eligible and score>best:
            best=score;torch.save(model.state_dict(),out/'best_eligible.pth');write(out/'best_eligible.json',row)
        model.train()
    validate(0)
    for step in range(1,steps+1):
        zs,ys,si=choose(sv,ns);zv,yv,ui=choose(views,64)
        zf,yf,_=choose(fonts,96);zm,ym,_=choose(mnist,nm);zc,yc,_=choose(chars,48)
        zb,yb,_=choose(bg,28 if wide else 16);zl,yl,_=choose(letters,4 if wide else 16)
        x=torch.cat([zs,zv,augment(zf,True),augment(zm,True),augment(zc,True),zb,zl]);y=torch.cat([ys,yv,yf,ym,yc,yb,yl])
        pred=model(x);ce=F.cross_entropy(pred,y)
        ref=torch.cat([svteacher[0][si],viewteacher[0][ui]]);mask=torch.cat([svteacher[1][si],viewteacher[1][ui]])
        kl=F.kl_div(F.log_softmax(pred[:nt][mask]/2,dim=1),F.softmax(ref[mask]/2,dim=1),reduction='batchmean')*4
        loss=ce+(.35 if extended else .65)*kl;opt.zero_grad(set_to_none=True);loss.backward();opt.step();schedule.step();loss_sum+=float(loss.detach())
        if step%interval==0:validate(step);loss_sum=0
    torch.save(model.state_dict(),out/'last.pth')
    accepted=best>=0
    if accepted:
        path=out/'best_eligible.pth';write(out/'frozen_candidate.json',dict(status='VALIDATION_SELECTED_BEFORE_TEST',model=str(path),sha256=sha(path),protocol_sha256=protocol_sha,training_revision_sha256=sha(out/'training_revision.json') if extended else None,parameters=sum(p.numel() for p in model.parameters()),selection=json.loads((out/'best_eligible.json').read_text()),official_test_used=False))
    write(out/'training_complete.json',dict(status='VALIDATION_ELIGIBLE_CANDIDATE' if accepted else 'NO_ELIGIBLE_CANDIDATE_DO_NOT_DEPLOY',protocol_sha256=protocol_sha,steps=steps,seconds=time.monotonic()-start,test_data_read=False,board_touched=False))
    print('TRAINING_COMPLETE',accepted,flush=True)
if __name__=='__main__':main()
