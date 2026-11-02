"""Evaluate frozen choices once on fresh data, then previous-test regression."""
from pathlib import Path
import concurrent.futures as cf,subprocess,time
import cv2,numpy as np
from road_adapt_common import BASE,ROOT,REF,REF_SHA,POLICIES,TRAIN_MILD,NAMES,read,write,sha,canonical,apply_policy,luma

def main():
    selection=read(ROOT/'selected.json');selection_hash=sha(ROOT/'selected.json')
    assert sha(REF)==REF_SHA and sha(selection['weights'])==selection['weights_sha256']
    assert sha(ROOT/'fresh_selection.json')==selection['fresh_selection_sha256']
    assert sha(ROOT/'validation/selection_rules.json')==selection['selection_rules_sha256']
    assert read(ROOT/'metric_regression/complete.json')['fusion_highlight_bypass']
    assert read(ROOT/'bounded_numeric_proof/complete.json')
    assert sha(ROOT/'fresh/manifest.json')==read(ROOT/'fresh/complete.json')['manifest_sha256']
    out=ROOT/'test';out.mkdir(exist_ok=False)
    # Fix reported views and example indices BEFORE accessing any fresh image pixels.
    models={'previous':BASE/'frozen/road4_best.pt','raw_control':ROOT/'frozen/raw_control/best.pt','mixed':ROOT/'frozen/mixed/best.pt'}
    plan={'previous':['raw'],'raw_control':['raw','full_net',TRAIN_MILD['name']],'mixed':['raw','full_net',TRAIN_MILD['name']]}
    fresh=read(ROOT/'fresh/manifest.json');old=[r for r in read(BASE/'dataset/manifest.json') if r['split']=='test' and r['status']=='READY']
    examples=[r['name'] for p,n in [('night',3),('dawn/dusk',2),('daytime',1)] for r in [x for x in fresh if x['timeofday']==p][:n]]
    write(out/'test_protocol.json',dict(status='FROZEN_BEFORE_FRESH_INFERENCE',selection_sha256=selection_hash,models={k:sha(v) for k,v in models.items()},plan=plan,
          examples=examples,example_rule='First three night, first two dawn/dusk, first daytime in metadata-frozen manifest.',
          diagnostic_views='All predeclared views are reported; no re-selection on fresh results.',old480='REGRESSION_ONLY',board_deployed=False,sd_written=False))
    from road_adapt_eval_core import Evaluator,supplement_predictions,evaluate_serial_predictions
    views=out/'fresh_frames';views.mkdir();temp=out/'reference_inputs';temp.mkdir()
    def prepare(r):
        image=ROOT/'fresh/images'/r['name'];assert sha(image)==r['image_sha256']
        raw=canonical(cv2.imread(str(image))[:,:,::-1]);stem=Path(r['name']).stem
        ip=temp/(stem+'.rgb');op=temp/(stem+'.net.rgb');ip.write_bytes(raw.tobytes())
        p=subprocess.run([str(REF),str(ip),'240','400',str(op)],capture_output=True,text=True)
        assert p.returncode==0 and 'MULTINEX_CPP_DONE' in p.stdout
        net=np.fromfile(op,np.uint8).reshape(240,400,3)
        for kind,a in [('raw',raw),('net',net)]:
            assert cv2.imwrite(str(views/(stem+'.'+kind+'.png')),a[:,:,::-1])
        return dict(name=r['name'],raw_sha256=sha(views/(stem+'.raw.png')),net_sha256=sha(views/(stem+'.net.png')))
    manifest=[]
    with cf.ThreadPoolExecutor(4) as pool:
        for v in pool.map(prepare,fresh):
            manifest.append(v)
            if len(manifest)%120==0:print('FRESH_CANONICAL_VIEWS',len(manifest),flush=True)
    write(out/'fresh_frames_manifest.json',manifest)
    results={}
    for split,rows in [('fresh',fresh),('regression',old)]:
        folder=out/split;folder.mkdir()
        rows=[{**r,'label_path':str((ROOT/'fresh/labels' if split=='fresh' else BASE/'dataset/labels/test')/(Path(r['name']).stem+'.txt'))} for r in rows]
        frames={}
        for r in rows:
            stem=Path(r['name']).stem
            paths=({'raw':views/(stem+'.raw.png'),'net':views/(stem+'.net.png')} if split=='fresh' else
                   {'raw':BASE/'test/enhancement_inputs'/(stem+'.raw400.png'),'net':BASE/'test/enhancement_inputs'/(stem+'.multinex400.png')})
            frames[r['name']]={k:cv2.imread(str(p))[:,:,::-1].copy() for k,p in paths.items()}
        scores={}
        for mode,weights in models.items():
            evaluator=Evaluator(weights)
            for name in plan[mode]:
                policy=next(p for p in POLICIES if p['name']==name);tag=mode+'__'+name
                scores[tag]=evaluator.run(rows,lambda r,p=policy:apply_policy(frames[r['name']]['raw'],frames[r['name']]['net'],p),folder,tag)
            evaluator.close()
        choice=selection['mode']+'__'+selection['policy']['name']
        if choice not in scores:
            policy=selection['policy'];mode=selection['mode']
            if policy['kind']=='supplement':
                a={r['name']:r['detections'] for r in read(folder/(mode+'__raw_predictions.json'))};b={r['name']:r['detections'] for r in read(folder/(mode+'__full_net_predictions.json'))}
                preds={r['name']:supplement_predictions(a[r['name']],b[r['name']],policy,int((luma(frames[r['name']]['raw']).sum()+48000)//96000)) for r in rows}
                scores[choice]=evaluate_serial_predictions(rows,preds,folder,choice)
            else:
                evaluator=Evaluator(models[mode]);scores[choice]=evaluator.run(rows,lambda r:apply_policy(frames[r['name']]['raw'],frames[r['name']]['net'],policy),folder,choice);evaluator.close()
        changes={}
        baseline={r['name']:r for r in read(folder/'raw_control__raw_predictions.json')}
        for tag in scores:
            counts={p:{c:dict(recovered=0,lost=0) for c in NAMES} for p in ['night','dawn/dusk','daytime']}
            for r in read(folder/(tag+'_predictions.json')):
                before=set(baseline[r['name']]['matched_gt']);after=set(r['matched_gt'])
                for kind,ids in [('recovered',after-before),('lost',before-after)]:
                    for i in ids:counts[r['timeofday']][NAMES[int(r['ground_truth'][i][0])]][kind]+=1
            changes[tag]=counts
        results[split]=dict(scores=scores,selected=choice,changes_vs_matched_raw_control=changes,images=len(rows),
                           active_dark_fraction=sum(int((luma(v['raw']).sum()+48000)//96000)<48 for v in frames.values())/len(rows))
        write(folder/'summary.json',results[split]);print('FROZEN_SPLIT_EVALUATED',split,choice,flush=True)
    assert sha(ROOT/'selected.json')==selection_hash
    write(out/'complete.json',dict(status='SECOND_ROUND_FRESH_AND_REGRESSION_EVALUATION_COMPLETE',results=results,selection_sha256=selection_hash,
          fresh_manifest_sha256=sha(ROOT/'fresh/manifest.json'),no_policy_retuning=True,board_deployed=False,sd_written=False))
    print('ROAD_ADAPTATION_FRESH_TEST_COMPLETE',flush=True)
if __name__=='__main__':main()
