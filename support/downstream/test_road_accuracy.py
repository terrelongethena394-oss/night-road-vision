"""One frozen candidate and matched enhancement control on unseen groups."""
import collections,shutil
from road_accuracy_common import *
from evaluate_road_accuracy import cache_views,make_fused,summarize

def main():
    assert not (ROOT/'fresh_result.json').exists()
    s=read(ROOT/'selected.json');assert s['qualified'] and s['protocol_sha256']==sha(ROOT/'protocol.json')
    chosen=s['chosen'];assert chosen['geometry']=='three' and chosen['mode']=='raw'
    matched=[r for r in s['records'] if r['geometry']==chosen['geometry'] and r['weight']==chosen['weight'] and r['mode'] in ['gamma080','gamma065']]
    control=max(matched,key=lambda r:r['metrics']['by_time']['night']['classes']['car']['ap50'])
    policy=dict(status='FROZEN_BEFORE_FRESH_PREDICTIONS',selected_sha256=sha(ROOT/'selected.json'),selected=chosen['tag'],candidate_geometry=chosen['geometry'],candidate_mode=chosen['mode'],weight=chosen['weight'],matched_enhancement_mode=control['mode'],matched_control_selection='Highest night-car AP50 among two mild gamma inputs on old320 at exactly the chosen geometry/weight. Attribution only; cannot become replacement based on fresh result.',comparisons=['candidate minus global_raw','matched enhancement minus identical raw geometry'],manifest_sha256=sha(ROOT/'fresh/manifest.json'),no_fresh_driven_reselection=True,hardware_access=False,sd_written=False)
    write(ROOT/'fresh_policy.json',policy)
    shutil.copy2(Path(__file__),ROOT/'source'/Path(__file__).name)
    rows=[dict(name=r['name'],timeofday=r['timeofday'],image=str(ROOT/'fresh/images'/r['name']),label=str(ROOT/'fresh/labels'/(Path(r['name']).stem+'.txt'))) for r in read(ROOT/'fresh/manifest.json')]
    assert collections.Counter(r['timeofday'] for r in rows)==QUOTA
    request=[('global','raw',None)]+[('tile',m,i) for m in ['raw',control['mode']] for i in range(3)]
    predictions=cache_views(rows,ROOT/'fresh_gpu/views',False,request)
    records=dict(baseline=predictions['global_raw'],candidate=make_fused(predictions,chosen['geometry'],'raw',chosen['weight']),enhanced_control=make_fused(predictions,chosen['geometry'],control['mode'],chosen['weight']))
    scores={}
    for tag,rr in records.items():
        m=metrics(rr);scores[tag]=m;write(ROOT/'fresh_gpu'/(tag+'_predictions.json'),rr);write(ROOT/'fresh_gpu'/(tag+'_metrics.json'),m)
        print('FRESH_ACCURACY_SCORE',tag,summarize(m),flush=True)
    write(ROOT/'fresh_gpu/complete.json',dict(status='FROZEN_CANDIDATE_AND_MATCHED_CONTROL_FRESH672_GPU_FP32_COMPLETE',scores=scores,policy_sha256=sha(ROOT/'fresh_policy.json'),arithmetic='CUDA FP32, TF32 disabled, exact integer board preprocessing',no_reselection=True,hardware_access=False,sd_written=False))
    print('FRESH_ACCURACY_GPU_COMPLETE',flush=True)

if __name__=='__main__':main()
