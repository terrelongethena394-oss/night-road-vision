"""Development-only screening. No test-set tuning and no board parameter changes."""
from pathlib import Path
import numpy as np
from road_numpy_eval import correct
from car_roi_delivery_common import BASE,STUDY,ROOT,read,write,sha

OUT=BASE/'workbench_optimization_20261031_r1/current_model_screen'

def score(rows,threshold):
    tp=fp=objects=0
    for r in rows:
        a=np.asarray(r['detections'],np.float32).reshape(-1,6)
        a=a[(a[:,5]==1)&(a[:,4]>=threshold)]
        g=np.asarray(r['ground_truth'],np.float32).reshape(-1,5);g=g[g[:,0]==1]
        t=int(correct(a,g,np.array([.5],np.float32))[0].sum())
        tp+=t;fp+=len(a)-t;objects+=len(g)
    p=tp/max(1,tp+fp);recall=tp/max(1,objects)
    return dict(threshold=threshold,images=len(rows),objects=objects,tp=tp,fp=fp,fn=objects-tp,precision=p,recall=recall,f1=2*p*recall/max(1e-12,p+recall))

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    source=ROOT/'c_proof/candidate_c_post_predictions.json'
    protocol=OUT/'confidence_screen_protocol.json'
    assert not protocol.exists(),'Preserve the first screening results'
    write(protocol,dict(status='FROZEN_BEFORE_THRESHOLD_SCREEN',source=str(source),
        thresholds=[.25,.30,.35,.40,.45,.50],selection='Development set only; no confirmation set read',
        gates='F1 and precision must not decrease; recall loss <=0.005 absolute; FP drop >=5 percent',
        deployment='Diagnostic first; no automatic threshold/model/SD change'))
    data=read(source)
    if isinstance(data,dict):
        print('DEVELOPMENT_CACHE_KEYS',list(data),flush=True)
        rows=data['candidate'] if 'candidate' in data else data['records']
    else:rows=data
    records=[score(rows,t) for t in [.25,.30,.35,.40,.45,.50]];base=records[0]
    expected=read(ROOT/'selected.json')['scores']['candidate']
    assert all(base[k]==expected[k] for k in ['tp','fp','fn','objects']),(base,expected)
    for r in records[1:]:
        r['qualified']=r['f1']>=base['f1'] and r['precision']>=base['precision'] and r['recall']>=base['recall']-.005 and r['fp']<=.95*base['fp']
    qualified=[r for r in records[1:] if r['qualified']]
    write(OUT/'confidence_screen.json',dict(status='DEVELOPMENT_THRESHOLD_DIAGNOSTIC_ONLY',source_sha256=sha(source),baseline_matches_deployed_development_receipt=True,
        records=records,qualified=qualified,threshold_changed=False,model_changed=False,hardware_access=False,test_set_used=False))
    lines=['# 汽车误检阈值检查','','仅使用已用于开发的图片。没有读取确认集，没有更改板上模型或阈值。',
        '候选须同时满足：F1与精确率不下降、召回率下降不超过0.5个百分点、误检至少减少5%。','',
        '| 阈值 | 正确检出 | 误检 | 漏检 | 精确率 | 召回率 | F1 |','|---|---:|---:|---:|---:|---:|---:|']
    for r in records:lines.append(f"| {r['threshold']:.2f} | {r['tp']} | {r['fp']} | {r['fn']} | {r['precision']:.2%} | {r['recall']:.2%} | {r['f1']:.2%} |")
    lines+=['',('有候选通过开发集门槛，仍需另外验证后才能部署。' if qualified else '没有候选通过全部门槛，保留原阈值，避免以明显增加漏检换取更少的框。')]
    (OUT/'汽车误检阈值检查.md').write_text('\n'.join(lines),encoding='utf-8')
    for r in records:print('CONFIDENCE_SCREEN',r,flush=True)

if __name__=='__main__':main()
