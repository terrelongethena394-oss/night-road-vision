"""Train a small complete-plate CTC reader; validate before any test/deployment."""
from pathlib import Path
import json,time,sys,math
import numpy as np
import torch
import torch.nn.functional as F
from plate_common import ROOT,SEED,CHARS,PROVINCES,ALPHABETS,ADS,sha,write,decode,edit_distance
from tiny_plate_model import TinyPlate
OUT=ROOT/'tiny_student01'
def gray_np(x):
    z=x.astype(np.uint32);return ((29*z[:,:,:,0]+150*z[:,:,:,1]+77*z[:,:,:,2]+128)>>8).astype(np.uint8)
def normalized(x):
    a=x.reshape(-1,3072).to(torch.int32);lo=a.kthvalue(154,dim=1).values;hi=a.kthvalue(2919,dim=1).values
    span=(hi-lo).clamp_min(16)[:,None];center=((lo+hi+1)//2)[:,None]
    d=a-center;q=(d.abs()*192+span//2)//span;b=(128+torch.where(d<0,-q,q)).clamp(0,255)
    return ((b.float()*2-255)/256).reshape(-1,1,32,96)
def valid_word(s):return len(s)==7 and s[0] in PROVINCES and s[1] in ALPHABETS and all(c in ADS for c in s[2:])
@torch.inference_mode()
def inference(model,raw,device,gain=1):
    pred=[]
    for z in raw.split(128):
        a=torch.floor(z.float()*gain+.5).clamp(0,255).byte().to(device)
        pred.extend(decode(model(normalized(a))))
    return pred
def main():
    stop=int(sys.argv[1]) if len(sys.argv)>1 else 12000;total=12000;interval=300
    OUT.mkdir(exist_ok=True);assert not (OUT/'training_complete.json').exists()
    torch.set_num_threads(4);torch.manual_seed(SEED);rng=np.random.default_rng(SEED)
    device='cuda' if torch.cuda.is_available() else 'cpu'
    if device=='cuda':torch.backends.cudnn.benchmark=True;torch.cuda.manual_seed_all(SEED)
    tr=np.load(ROOT/'data/train.npz');va=np.load(ROOT/'data/validation.npz');tc=np.load(ROOT/'teacher_cache/train.npz')
    assert np.array_equal(tr['texts'],tc['texts'])
    train=torch.from_numpy(gray_np(tr['x']));val=torch.from_numpy(gray_np(va['x']));texts=tr['texts'].tolist();truth=va['texts'].tolist()
    neg=torch.from_numpy(np.load(ROOT/'negatives/train.npz')['x']);negval=torch.from_numpy(np.load(ROOT/'negatives/validation.npz')['x'])
    teacher=torch.from_numpy(tc['logits']);correct=torch.from_numpy(tc['correct'])
    dictionary={c:i for i,c in enumerate(CHARS)};labels=torch.tensor([[dictionary[c] for c in s] for s in texts],dtype=torch.long)
    model=TinyPlate(len(CHARS)).to(device);optimizer=torch.optim.AdamW(model.parameters(),lr=.0015,weight_decay=.0001)
    scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,total,eta_min=.0001)
    scaler=torch.amp.GradScaler('cuda',enabled=device=='cuda');ctc=torch.nn.CTCLoss(blank=len(CHARS)-1,reduction='mean',zero_infinity=True)
    if not (OUT/'protocol.json').exists():
        write(OUT/'protocol.json',dict(status='FROZEN_BEFORE_STUDENT_FITTING',seed=SEED,steps=total,architecture='1->16 conv3 stride2; depthwise/pointwise32,64,96; flattenH2 to192; temporalConv3->128; pointwise68;24-stepCTC. ReLU6 throughout.',parameters=sum(p.numel() for p in model.parameters()),input='96x32 BGR->gray29/150/77, byte P5rank154/P95rank2919;minspan16; normalize tobyte128+-roundaway(diff*192/span); (2*byte-255)/256.',batch=dict(plates=96,nonplates=16),lr=.0015,loss='GT CTC +.15 teacher T2KL on teacher-correct TRAIN samples only +.25 nonplate mean blank crossentropy after step500.',selection='Validation only: normal fullplate>=.80, syntheticgain.25>=.75, valid-format nonplate falseaccept<=.01; maximize .6normal+.3dim+.1reject. Keep best provisional and eligible separately.',test_acceptance='Frozen candidate: normal>=.80 and no worse than upstream same-crop teacher; syntheticgain.25>=.75; negatives valid-format falseaccept<=.01; all tests count rejected positive words as wrong. Known live frame is regression, not fit.',teacher_data_overlap='Unknown upstream pretraining overlap. Student train/val/test plate IDs disjoint. No new blind generalization claim.',board_written=False,sd_written=False))
    start_step=0;best=-1.;provisional=-1.;history=[];elapsed_base=0
    if (OUT/'resume.pth').exists():
        state=torch.load(OUT/'resume.pth',weights_only=True,map_location='cpu');model.load_state_dict(state['model']);optimizer.load_state_dict(state['optimizer']);scheduler.load_state_dict(state['scheduler'])
        if state['scaler']:scaler.load_state_dict(state['scaler'])
        start_step=state['step'];best=state['best'];provisional=state['provisional'];history=state['history'];elapsed_base=state['elapsed'];torch.set_rng_state(state['torch_rng']);rng.bit_generator.state=state['numpy_rng']
        print('RESUMING',start_step,device,flush=True)
    else:print('STARTING',device,flush=True)
    start=time.monotonic();loss_sum=0.;last=start_step
    def evaluate(step):
        nonlocal best,provisional
        model.eval();normal=inference(model,val,device);dim=inference(model,val,device,.25);negative=inference(model,negval,device)
        a=float(np.mean([p==y for p,y in zip(normal,truth)]));b=float(np.mean([p==y for p,y in zip(dim,truth)]));fa=float(np.mean([valid_word(s) for s in negative]));score=.6*a+.3*b+.1*(1-fa)
        eligible=a>=.8 and b>=.75 and fa<=.01
        row=dict(step=step,normal=a,synthetic_dim=b,nonplate_false_accept=fa,normal_cer=sum(edit_distance(p,y) for p,y in zip(normal,truth))/(7*len(truth)),eligible=eligible,score=score,loss=loss_sum/max(1,step-last),seconds=elapsed_base+time.monotonic()-start,device=device)
        history.append(row);print(json.dumps(row),flush=True);write(OUT/'training_progress.json',history)
        if score>provisional:provisional=score;torch.save(model.state_dict(),OUT/'best_provisional.pth');write(OUT/'best_provisional.json',row)
        if eligible and score>best:best=score;torch.save(model.state_dict(),OUT/'best_eligible.pth');write(OUT/'best_eligible.json',row)
        model.train()
    if start_step==0:evaluate(0)
    for step in range(start_step+1,min(stop,total)+1):
        model.train();ids=torch.randint(len(train),(96,));ni=torch.randint(len(neg),(16,));raw=train[ids].float()
        # Stochastic image formation precedes exact byte normalization.
        gain=torch.where(torch.rand(96,1,1)<.5,torch.empty(96,1,1).uniform_(.12,.65),torch.empty(96,1,1).uniform_(.8,1.2))
        raw=(raw*gain+torch.randn_like(raw)*torch.empty(96,1,1).uniform_(0,1.3)).clamp(0,255)
        raw=torch.floor(raw+.5).byte();images=torch.cat([raw,neg[ni]]).to(device);x=normalized(images)
        if step%3==0:
            # Small translations preserve word order; no flips or target-image fitting.
            dx=int(rng.integers(0,3));dy=int(rng.integers(0,3));x=F.pad(x,(1,1,1,1),mode='replicate')[:,:,dy:dy+32,dx:dx+96]
        with torch.autocast(device_type='cuda',enabled=device=='cuda',dtype=torch.float16):scores=model(x)
        lp=scores.float().log_softmax(1);targets=labels[ids].flatten().to(device)
        loss_ctc=ctc(lp[:96].permute(2,0,1).contiguous(),targets,torch.full((96,),24,dtype=torch.long),torch.full((96,),7,dtype=torch.long))
        mask=correct[ids].to(device);ref=F.interpolate(teacher[ids].to(device),size=24,mode='linear',align_corners=False)
        kd=F.kl_div(F.log_softmax(scores[:96][mask].float()/2,dim=1),F.softmax(ref[mask]/2,dim=1),reduction='sum')*4/(max(1,int(mask.sum()))*24)
        loss=loss_ctc+.15*kd+(.25 if step>=500 else 0)*(-lp[96:,len(CHARS)-1].mean())
        assert torch.isfinite(loss),('NonfiniteCTC',step)
        optimizer.zero_grad(set_to_none=True);scaler.scale(loss).backward();scaler.unscale_(optimizer);torch.nn.utils.clip_grad_norm_(model.parameters(),5);scaler.step(optimizer);scaler.update();scheduler.step();loss_sum+=float(loss.detach())
        if step%interval==0 or step==min(stop,total):evaluate(step);loss_sum=0.;last=step
    final_step=min(stop,total)
    torch.save(dict(model=model.state_dict(),optimizer=optimizer.state_dict(),scheduler=scheduler.state_dict(),scaler=scaler.state_dict(),step=final_step,best=best,provisional=provisional,history=history,elapsed=elapsed_base+time.monotonic()-start,torch_rng=torch.get_rng_state(),numpy_rng=rng.bit_generator.state),OUT/'resume.pth')
    if final_step==total:
        if best>=0:write(OUT/'frozen_candidate.json',dict(model=str(OUT/'best_eligible.pth'),sha256=sha(OUT/'best_eligible.pth'),selection=json.loads((OUT/'best_eligible.json').read_text()),protocol_sha256=sha(OUT/'protocol.json'),test_data_used=False))
        write(OUT/'training_complete.json',dict(status='VALIDATION_ELIGIBLE' if best>=0 else 'NO_ELIGIBLE_CANDIDATE_DO_NOT_DEPLOY',steps=total,device=device,seconds=elapsed_base+time.monotonic()-start,test_data_used=False))
    print('TRAIN_STAGE_COMPLETE',final_step,device,'eligible',best>=0,flush=True)
if __name__=='__main__':main()
