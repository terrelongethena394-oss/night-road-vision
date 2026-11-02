"""Offline validation-only rejection study; never changes the deployed program."""
from pathlib import Path
import json
import numpy as np
from recognition_upgrade_common import ROOT,BASE,SEED,normalize_np,sha,write
from evaluate_recognition_upgrade import native
from train_real_digit import backgrounds
OUT=BASE/'rejection_calibration_20261026'
RUN=ROOT/'run03'
def features(s):
    a=np.asarray(s,np.float64)/1048576
    p=np.exp(a-a.max(1,keepdims=True));p/=p.sum(1,keepdims=True)
    order=np.sort(a,axis=1)
    return dict(pred=a.argmax(1),confidence=p.max(1),margin=order[:,-1]-order[:,-2])
def main():
    OUT.mkdir(exist_ok=True);assert not (OUT/'results.json').exists(),'Preserve completed calibration'
    freeze=json.loads((RUN/'frozen_candidate.json').read_text());assert sha(freeze['model'])==freeze['sha256']
    write(OUT/'protocol.json',dict(status='FROZEN_BEFORE_VALIDATION_SCORE_EXTRACTION',model_sha256=freeze['sha256'],selection_data='Existing SVHN/Chars74K/fonts/MNIST validation only; no test images or new camera frames for selection.',confidence='Softmax score is an uncalibrated model score, not probability of correctness.',rule='Reject if predicted background OR softmax max belowp OR top-two Q20-logit margin belowm.',threshold_p=[0,.3,.4,.5,.6,.65,.7,.75,.8,.85,.9,.95,.98],threshold_m=[0,.25,.5,.75,1,1.5,2,3],selection='Retain at least95% of baseline correctly classified digits in EACH positive validation group, then minimize weighted negative false acceptance (letters.6,flat.2,noise.2); tie maximize worst positive retention.',acceptance='At least20% relative reduction in weighted negative acceptance; report previously seen live false-positive frame as regression ONLY, never tune thresholds to it. Even a passing rule is not deployed without heldout regression and ARM numeric verification.',board_written=False,sd_written=False))
    data=np.load(BASE/'real_digit_training_20261025/data/train_board_gray.npz');split=np.load(BASE/'real_digit_training_20261025/split_indices.npz')
    datasets={'svhn':(data['x'][split['validation']],data['y'][split['validation']])}
    for tag in ['chars','fonts','mnist']:
        d=np.load(ROOT/f'data/{tag}_validation.npz');mask=d['y']<10;datasets[tag]=(d['x'][mask],d['y'][mask])
    c=np.load(ROOT/'data/chars_validation.npz');mask=c['y']==10;datasets['letters']=(c['x'][mask],c['y'][mask])
    datasets['flat']=backgrounds(1000,SEED+144)
    datasets['noise']=(np.random.default_rng(SEED+145).integers(0,256,(1000,28,28),dtype=np.uint8),np.full(1000,10))
    fs={};labels={}
    for name,(x,y) in datasets.items():
        s=native(RUN/'native/digit_arm_host.exe',normalize_np(x),OUT,name);fs[name]=features(s);labels[name]=y
        print('VALIDATION_SCORED',name,len(y),flush=True)
    pos=['svhn','chars','fonts','mnist'];neg={'letters':.6,'flat':.2,'noise':.2}
    baseline={k:float((fs[k]['pred']<10).mean()) for k in neg};base=sum(neg[k]*baseline[k] for k in neg)
    candidates=[]
    for p in [0,.3,.4,.5,.6,.65,.7,.75,.8,.85,.9,.95,.98]:
        for m in [0,.25,.5,.75,1,1.5,2,3]:
            masks={k:(v['pred']<10)&(v['confidence']>=p)&(v['margin']>=m) for k,v in fs.items()}
            retention={k:float(masks[k][fs[k]['pred']==labels[k]].mean()) for k in pos}
            if min(retention.values())<.95:continue
            rates={k:float(masks[k].mean()) for k in neg};weighted=sum(neg[k]*rates[k] for k in neg)
            metrics={k:dict(n=len(labels[k]),baseline_correct=int((fs[k]['pred']==labels[k]).sum()),accepted_correct=int(((fs[k]['pred']==labels[k])&masks[k]).sum()),coverage=float(masks[k].mean())) for k in pos}
            candidates.append(dict(p=p,m=m,retention=retention,false_acceptance=rates,weighted_false_acceptance=weighted,positive=metrics))
    best=min(candidates,key=lambda v:(v['weighted_false_acceptance'],-min(v['retention'].values()),v['p'],v['m']))
    reduction=(base-best['weighted_false_acceptance'])/base if base else 0
    live=features(np.fromfile(BASE/'multinex_camera_digit_upgrade_20261026/live_snapshot/digit_scores.i64',dtype='<i8').reshape(3,11))
    live_accepted=(live['pred']<10)&(live['confidence']>=best['p'])&(live['margin']>=best['m'])
    result=dict(status='VALIDATION_RULE_FOUND_NOT_DEPLOYED' if reduction>=.2 else 'INSUFFICIENT_REJECTION_IMPROVEMENT_DO_NOT_DEPLOY',model_sha256=freeze['sha256'],baseline_negative_false_acceptance=baseline,baseline_weighted_false_acceptance=base,best=best,relative_negative_reduction=reduction,validation_gate_passed=bool(reduction>=.2),eligible_threshold_pairs=len(candidates),seen_live_regression=dict(predictions=live['pred'].tolist(),softmax_scores=live['confidence'].tolist(),accepted=live_accepted.tolist(),all_false_positive_views_rejected=bool(not live_accepted.any())),test_data_used=False,board_written=False,sd_written=False)
    write(OUT/'results.json',result)
    note=f'''# 拒识规则离线检查

未修改板上程序，也未写SD。使用当前冻结识别器，在验证数据中选择规则，未使用测试图或本次真实摄像头误报帧挑阈值。

选择的规则：预测为背景、softmax评分低于{best['p']:g}、或前两类logit差低于{best['m']:g}时显示未知。softmax评分不是校准后的正确率。

在SVHN、场景字符、字体、手写数字各组，均要求保留至少95%原本识别正确的数字。此限制下，字母/平坦背景/随机噪声的加权误接受率从{base:.4f}降到{best['weighted_false_acceptance']:.4f}，相对下降{100*reduction:.2f}%。这些控制并不代表所有未知物体。

事后回归检查之前的摄像头误报（不参与选阈值）：三路是否仍接受数字={live_accepted.tolist()}。如果仍有一路误报，就不能说简单置信度门限已经解决了实景无数字误报。

当前仅完成阈值选择实验，不作为部署结论。即使验证门槛通过，后续也要在固定评测集检查误拒数字，并补充独立衣物、书本、桌面等非数字场景；没有重新训练或上板。
'''
    (OUT/'拒识检查结果.md').write_text(note,encoding='utf-8');print(json.dumps(result),flush=True)
if __name__=='__main__':main()
