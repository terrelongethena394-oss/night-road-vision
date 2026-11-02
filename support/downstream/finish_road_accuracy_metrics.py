"""Frozen comparisons and paired-image bootstrap; never reselect on test."""
import time
from road_accuracy_common import *
from road_numpy_eval import evaluate

def cached(rows):
    out=[]
    for r in rows:
        p=np.asarray(r['detections'],np.float32).reshape(-1,6);g=np.asarray(r['ground_truth'],np.float32).reshape(-1,5)
        tp=correct(p,g,np.array([.5],np.float32))[0][:,0]
        out.append(dict(conf=p[:,4],cls=p[:,5],tp=tp,gt=int((g[:,0]==1).sum())))
    return out
def carap(cache,ids):
    conf=np.concatenate([cache[i]['conf'] for i in ids]);cls=np.concatenate([cache[i]['cls'] for i in ids]);tp=np.concatenate([cache[i]['tp'] for i in ids]);n=sum(cache[i]['gt'] for i in ids)
    order=np.argsort(-conf);tp=tp[order][cls[order]==1]
    if not n or not len(tp):return 0.
    t=tp.cumsum(0);f=(1-tp).cumsum(0);r=t/(n+1e-16);p=t/(t+f)
    mr=np.r_[0.,r,1.];mp=np.r_[1.,p,0.];mp=np.maximum.accumulate(mp[::-1])[::-1]
    return float(np.trapezoid(np.interp(np.linspace(0,1,101),mr,mp),np.linspace(0,1,101)))
def bootstrap(a,b,label,expected_count=480,alpha=.025):
    a=[r for r in a if r['timeofday']=='night'];b=[r for r in b if r['timeofday']=='night']
    assert len(a)==len(b)==expected_count and [r['name'] for r in a]==[r['name'] for r in b]
    ca,cb=cached(a),cached(b);ids=np.arange(len(a))
    assert abs(carap(ca,ids)-evaluate(a)['classes']['car']['ap50'])<1e-10
    assert abs(carap(cb,ids)-evaluate(b)['classes']['car']['ap50'])<1e-10
    rng=np.random.default_rng(SEED+71);values=[];begin=time.monotonic()
    for j in range(1000):
        ids=rng.integers(0,len(a),len(a));delta=carap(cb,ids)-carap(ca,ids)
        if j<3:
            full=evaluate([b[i] for i in ids])['classes']['car']['ap50']-evaluate([a[i] for i in ids])['classes']['car']['ap50']
            assert abs(full-delta)<1e-10
        values.append(delta)
        if (j+1)%200==0:print('ACCURACY_PAIRED_BOOTSTRAP',label,j+1,round(time.monotonic()-begin),flush=True)
    key='interval99' if alpha==.01 else 'interval97_5'
    return dict(replicates=1000,unit='one previously unseen first8 filename group/image',seed=SEED+71,**{key:np.quantile(values,[alpha/2,1-alpha/2]).tolist()},point_difference=carap(cb,np.arange(len(a)))-carap(ca,np.arange(len(a))),first3_checked_against_full_10iou_evaluator=True)

def main():
    assert not (ROOT/'fresh_result.json').exists()
    n=read(ROOT/'native/complete.json');g=read(ROOT/'fresh_gpu/complete.json');s=read(ROOT/'selected.json')
    assert n['all_c_fusion_byte_exact'] and n['selection_sha256']==sha(ROOT/'selected.json') and g['no_reselection']
    base=read(ROOT/'native/baseline_predictions.json');cand=read(ROOT/'native/candidate_predictions.json')
    gpu_raw=read(ROOT/'fresh_gpu/candidate_predictions.json');gpu_enh=read(ROOT/'fresh_gpu/enhanced_control_predictions.json')
    ci=bootstrap(base,cand,'actual_C_candidate_minus_baseline');enhci=bootstrap(gpu_raw,gpu_enh,'same_views_enhancement_minus_raw')
    b=n['scores']['baseline'];c=n['scores']['candidate'];bn=b['by_time']['night'];cn=c['by_time']['night'];bc=bn['classes']['car'];cc=cn['classes']['car']
    gates=dict(primary_gain=cc['ap50']>=bc['ap50']+.01,primary_interval_positive=ci['interval97_5'][0]>0,car_precision=cc['precision']>=bc['precision']-.01,night=cn['mAP50']>=bn['mAP50']-.005,overall=c['all']['mAP50']>=b['all']['mAP50']-.005,person_outputs_unchanged=True)
    changes=[]
    for a,z in zip(base,cand):
        assert a['name']==z['name'] and a['ground_truth']==z['ground_truth']
        pa=np.asarray(a['detections'],np.float32).reshape(-1,6);pz=np.asarray(z['detections'],np.float32).reshape(-1,6);gt=np.asarray(a['ground_truth'],np.float32).reshape(-1,5)
        ap=pa[pa[:,5]==0];zp=pz[pz[:,5]==0]
        assert np.array_equal(np.sort(ap,axis=0),np.sort(zp,axis=0))
        pa=pa[pa[:,4]>=.25];pz=pz[pz[:,4]>=.25]
        oa,ma=correct(pa,gt,np.array([.5],np.float32));oz,mz=correct(pz,gt,np.array([.5],np.float32));cars={i for i,v in enumerate(gt[:,0]) if v==1}
        recovered=sorted(map(int,(mz[0]-ma[0])&cars));lost=sorted(map(int,(ma[0]-mz[0])&cars))
        fp_a=int(((pa[:,5]==1)&~oa[:,0]).sum());fp_z=int(((pz[:,5]==1)&~oz[:,0]).sum())
        changes.append(dict(name=a['name'],timeofday=a['timeofday'],recovered_car_gt_indices=recovered,lost_car_gt_indices=lost,baseline_car_fp=fp_a,candidate_car_fp=fp_z))
    write(ROOT/'changes_all672.json',changes)
    result=dict(status='INDEPENDENT672_ACTUAL_C_QUALITY_ACCEPTED' if all(gates.values()) else 'INDEPENDENT672_REJECTED_RETAIN_CURRENT',quality_accepted=all(gates.values()),gates=gates,primary='Night car AP50',actual_c_scores=n['scores'],actual_c_uncertainty=ci,enhancement_comparison=dict(backend='GPU FP32, identical geometry/network/weights',scores=g['scores'],uncertainty=enhci,extra_gain_proven=enhci['interval97_5'][0]>0),selection_sha256=sha(ROOT/'selected.json'),no_test_driven_reselection=True,board_verified=False,sd_written=False)
    write(ROOT/'fresh_result.json',result)
    print('ACCURACY_INDEPENDENT_ACCEPTANCE',result['status'],gates,'car',bc,cc,'CI',ci,'enhCI',enhci,flush=True)

if __name__=='__main__':main()
