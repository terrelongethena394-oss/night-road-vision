"""Train on original TRAIN counterfactuals; select only on exposed480 development."""
import math,shutil,time
from pathlib import Path
import numpy as np
from road_task_router_common import *
from confirm_road_viewadapt import statistics,car_ap50
from road_numpy_eval import evaluate
import road_accuracy_common as ac

def main():
    import torch
    assert (ROOT/'prepared.json').exists() and not (ROOT/'selected.json').exists();shutil.copy2(__file__,ROOT/'source'/Path(__file__).name);torch.set_num_threads(2);torch.manual_seed(SEED);np.random.seed(SEED)
    outcomes=read(ROOT/'training_outcomes.json');f=np.fromfile(ROOT/'features.f32',np.float32).reshape(1060,68);target=np.array([r['label'] for r in outcomes]);fit=np.array([r['split']=='fit' for r in outcomes]);assert fit.sum()>700 and (~fit).sum()>100
    mean=f[fit].mean(0);scale=np.maximum(f[fit].std(0),np.float32(.01));np.savez(ROOT/'normalization.npz',mean=mean,scale=scale)
    x=torch.from_numpy((f-mean)/scale);y=torch.from_numpy(target).long();model=make_model();assert sum(p.numel() for p in model.parameters())==1155
    freq=np.bincount(target[fit],minlength=3);weight=np.sqrt(fit.sum()/(3*np.maximum(freq,1)));weight=weight/weight.mean();criterion=torch.nn.CrossEntropyLoss(weight=torch.tensor(weight,dtype=torch.float32));opt=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.05);history=[];begin=time.monotonic()
    write(ROOT/'training_config.json',dict(status='FROZEN_BEFORE_ROUTER_GRADIENTS',fit_sources=int(fit.sum()),internal_sources=int((~fit).sum()),fit_class_counts=freq.tolist(),class_weights=weight.tolist(),normalization_fit_only=True,parameters=1155,main_unchanged_sha256=sha(MAIN)))
    for epoch in range(1,81):
        model.train();order=np.random.default_rng(SEED+epoch).permutation(np.where(fit)[0]);losses=[];lr=.0001+.0009*(1+math.cos(math.pi*(epoch-1)/79))*.5
        for group in opt.param_groups:group['lr']=lr
        for at in range(0,len(order),64):
            ids=order[at:at+64];loss=criterion(model(x[ids]),y[ids]);assert torch.isfinite(loss);opt.zero_grad(set_to_none=True);loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5);opt.step();losses.append(float(loss.detach()))
        model.eval()
        with torch.inference_mode():pred=model(x).argmax(1).numpy()
        confusion=np.zeros((3,3),np.int32)
        for a,b in zip(target[~fit],pred[~fit]):confusion[a,b]+=1
        rec=dict(epoch=epoch,lr=lr,loss=float(np.mean(losses)),internal_confusion=confusion.tolist(),internal_accuracy=float((pred[~fit]==target[~fit]).mean()));history.append(rec)
        if epoch in EPOCHS:
            folder=ROOT/'frozen'/f'epoch{epoch}';folder.mkdir(parents=True);torch.save(model.state_dict(),folder/'model.pt');write(folder/'frozen.json',dict(**rec,sha256=sha(folder/'model.pt'),parameters=1155,protocol_sha256=sha(ROOT/'protocol.json')))
        if epoch%20==0:print('TASK_ROUTER_TRAIN',rec,flush=True)
    write(ROOT/'history.json',history);write(ROOT/'training_complete.json',dict(status='TASK_OUTCOME_ROUTER_TRAINED',seconds=time.monotonic()-begin,main_unchanged_sha256=sha(MAIN),hardware_access=False,sd_written=False))
    train=BASE/'road_allview_gammafit_20261031_r1';previous=read(train/'selected.json');base=previous['accepted_baseline'];matched=previous['raw_control']['scores']['raw'];raw_same=next(r['scores']['raw'] for r in previous['records'] if r['epoch']==8)
    rr=read(train/'development/enh8/predictions.json');rows=[r for r in read(train/'development_manifest.json') if r['cohort']=='low'];assert len(rows)==480 and [r['name'] for r in rr['raw']]==[r['name'] for r in rows]
    feat=[]
    for r in rows:
        _,a=ac.sensor400(Path(r['data_root'])/'images'/r['name']);feat.append(features(a))
    feat=np.asarray(feat,np.float32);feat.tofile(ROOT/'development_features.f32');xx=torch.from_numpy((feat-mean)/scale);ss={k:statistics(rr[k]) for k in ['raw','enh']};cc={k:np.asarray([counts(r) for r in rr[k]]) for k in ['raw','enh']};candidates=[];scores_by_epoch={}
    for epoch in EPOCHS:
        folder=ROOT/'frozen'/f'epoch{epoch}';assert sha(folder/'model.pt')==read(folder/'frozen.json')['sha256'];model.load_state_dict(torch.load(folder/'model.pt',map_location='cpu',weights_only=True));model.eval()
        with torch.inference_mode():pp=model(xx).softmax(1).numpy();decision_score=pp[:,2]-pp[:,0]
        scores_by_epoch[epoch]=decision_score
        for threshold in THRESHOLDS:
            on=decision_score>=np.float32(threshold);st=[ss['enh' if yes else 'raw'][i] for i,yes in enumerate(on)];tp,fp,fn=[int(v) for v in np.where(on[:,None],cc['enh'],cc['raw']).sum(0)]
            m=dict(objects=tp+fn,ap50=car_ap50(st,np.arange(480)),tp=tp,fp=fp,fn=fn,precision=tp/(tp+fp),recall=tp/(tp+fn));gg=dict(accepted_raw7=gates(base,m),matched_trained_raw7=gates(matched,m),same_main_raw=dict(ap=m['ap50']>=raw_same['ap50']+.002,tp=m['tp']>=raw_same['tp'],fp=m['fp']<=raw_same['fp']));qualified=all(all(v.values()) for v in gg.values());candidates.append(dict(epoch=epoch,threshold=threshold,routed_images=int(on.sum()),scores=m,gates=gg,qualified=qualified))
    good=[c for c in candidates if c['qualified']];chosen=max(good,key=lambda c:c['scores']['ap50']) if good else None
    if chosen:
        score=scores_by_epoch[chosen['epoch']];on=score>=np.float32(chosen['threshold']);actual=[rr['enh' if yes else 'raw'][i] for i,yes in enumerate(on)];full=evaluate(actual)['classes']['car'];assert abs(full['ap50']-chosen['scores']['ap50'])<1e-12;chosen['scores_full']=full;write(ROOT/'chosen_predictions.json',actual);write(ROOT/'chosen_decisions.json',[dict(name=r['name'],score=float(s),enhance=bool(active)) for r,s,active in zip(rows,score,on)])
    write(ROOT/'candidates.json',candidates);write(ROOT/'development_manifest.json',rows);result=dict(status='TASK_ROUTER_REQUIRES_ACTUAL_C_AND_UNUSED_CONFIRMATION' if chosen else 'NO_TASK_ROUTER_PASSED_KEEP_ABI29',qualified=bool(chosen),chosen=chosen,accepted_baseline=base,matched_raw_control=matched,same_main_raw=raw_same,best_descriptive=max(candidates,key=lambda c:c['scores']['ap50']),candidates=len(candidates),main_checkpoint_sha256=sha(MAIN),new_independent_test_used=False,hardware_access=False,sd_written=False)
    write(ROOT/'selected.json',result);print('TASK_ROUTER_RESULT',result,flush=True)
if __name__=='__main__':main()
