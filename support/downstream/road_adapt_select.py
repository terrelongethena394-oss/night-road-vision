"""Freeze candidate and pixel policy from old validation only, before fresh test."""
import time
from pathlib import Path
import cv2
from road_adapt_common import BASE,ROOT,POLICIES,FUSION_POLICIES,read,write,sha,apply_policy,frame_path,luma
def main():
    print('WAITING_FOR_BOTH_MATCHED_CANDIDATES',flush=True);start=time.monotonic()
    while not all((ROOT/'frozen'/m/'complete.json').exists() for m in ['raw_control','mixed']):
        if time.monotonic()-start>7200:raise TimeoutError('Matched adaptation incomplete')
        time.sleep(3)
    OUT=ROOT/'validation';OUT.mkdir(exist_ok=False)
    rules=dict(status='FROZEN_BEFORE_VALIDATION_POLICY_SEARCH',confidence=.25,match_iou=.5,nms_iou=.6,
               candidate_raw_gate='allAP50>=raw_control-.01 and night-person recall>=raw_control-.02',
               policy_gate='nightAP50>=same-model raw+.005; night-person recall>=raw-.02; nightFP<=rawFP*1.10+2; allAP50>=raw-.005; daytimeAP50>=raw-.005',
               score='Highest validation night mAP50 among gated nonraw combinations, tie by allAP50. If none pass, explicitly mark enhancement not accepted and retain best admissible raw model.',
               policies=POLICIES,dual_fallback_policies=FUSION_POLICIES,
               dual_fallback='Only if no single-pass policy passes: high-confidence enhanced-only boxes supplement raw detections in mean-luma<48 frames, class-aware NMS. Require same gates plus no loss of night-person recall and personFP<=1.10*rawPersonFP+2. Two detector passes in active dark frames; count cost explicitly.',
               fresh_test_used=False,original480_used=False)
    write(OUT/'selection_rules.json',rules)
    from road_adapt_eval_core import Evaluator,supplement_predictions,evaluate_serial_predictions
    rows=[{**r,'label_path':str(BASE/'dataset/labels/val'/(Path(r['name']).stem+'.txt'))} for r in read(ROOT/'paired_manifest.json') if r['split']=='val']
    frames={r['name']:{k:cv2.imread(str(frame_path('val',k,r['name'])))[:,:,::-1].copy() for k in ['raw','net']} for r in rows}
    scores={};weights={m:ROOT/'frozen'/m/'best.pt' for m in ['raw_control','mixed']}
    for mode in ['raw_control','mixed']:
        proof=read(ROOT/'frozen'/mode/'complete.json');assert sha(weights[mode])==proof['weight_sha256']
        evaluator=Evaluator(weights[mode]);scores[mode]={}
        for policy in POLICIES:
            tag=mode+'__'+policy['name']
            scores[mode][policy['name']]=evaluator.run(rows,lambda r,p=policy:apply_policy(frames[r['name']]['raw'],frames[r['name']]['net'],p),OUT,tag)
        evaluator.close()
    raw_control=scores['raw_control']['raw'];admissible=[];accepted=[]
    for mode in scores:
        raw=scores[mode]['raw'];night=raw['by_time']['night'];person=night['classes']['person']['recall']
        gate=raw['all']['mAP50']>=raw_control['all']['mAP50']-.01 and person>=raw_control['by_time']['night']['classes']['person']['recall']-.02
        if not gate:continue
        admissible.append(mode)
        for policy in POLICIES:
            if policy['kind']=='raw':continue
            out=scores[mode][policy['name']];n=out['by_time']['night'];fps=sum(c['fp'] for c in n['classes'].values());rawfps=sum(c['fp'] for c in night['classes'].values())
            good=n['mAP50']>=night['mAP50']+.005 and n['classes']['person']['recall']>=person-.02 and fps<=rawfps*1.10+2 and out['all']['mAP50']>=raw['all']['mAP50']-.005 and out['by_time']['daytime']['mAP50']>=raw['by_time']['daytime']['mAP50']-.005
            if good:accepted.append((n['mAP50'],out['all']['mAP50'],mode,policy))
    passes=1
    if not accepted:
        for mode in admissible:
            raw=scores[mode]['raw'];night=raw['by_time']['night'];rperson=night['classes']['person'];rawfps=sum(c['fp'] for c in night['classes'].values())
            rp={r['name']:r['detections'] for r in read(OUT/(mode+'__raw_predictions.json'))};ep={r['name']:r['detections'] for r in read(OUT/(mode+'__full_net_predictions.json'))}
            for policy in FUSION_POLICIES:
                fused={r['name']:supplement_predictions(rp[r['name']],ep[r['name']],policy,int((luma(frames[r['name']]['raw']).sum()+48000)//96000)) for r in rows}
                out=evaluate_serial_predictions(rows,fused,OUT,mode+'__'+policy['name']);scores[mode][policy['name']]=out;n=out['by_time']['night'];person=n['classes']['person'];fps=sum(c['fp'] for c in n['classes'].values())
                good=n['mAP50']>=night['mAP50']+.005 and person['recall']>=rperson['recall'] and person['fp']<=rperson['fp']*1.10+2 and fps<=rawfps*1.10+2 and out['all']['mAP50']>=raw['all']['mAP50']-.005 and out['by_time']['daytime']['mAP50']>=raw['by_time']['daytime']['mAP50']-.005
                if good:accepted.append((n['mAP50'],out['all']['mAP50'],mode,policy))
    if accepted:
        _,_,mode,policy=max(accepted,key=lambda a:(a[0],a[1]));enhancement_accepted=True
        passes=2 if policy['kind']=='supplement' else 1
    else:
        assert admissible
        mode=max(admissible,key=lambda m:scores[m]['raw']['by_time']['night']['mAP50']);policy=POLICIES[0];enhancement_accepted=False
    choice=dict(status='DETECTOR_AND_POLICY_FROZEN_BEFORE_FRESH_TEST',mode=mode,policy=policy,enhancement_validation_accepted=enhancement_accepted,
                weights=str(weights[mode]),weights_sha256=sha(weights[mode]),active_dark_detector_passes=passes,all_candidate_sha256={m:sha(p) for m,p in weights.items()},validation_scores=scores,
                accepted_nonraw=[dict(mode=a[2],policy=a[3],night_map50=a[0]) for a in accepted],selection_rules_sha256=sha(OUT/'selection_rules.json'),
                fresh_selection_sha256=sha(ROOT/'fresh_selection.json'),fresh_test_inference_performed=False,previous480='not used for selection',board_modified=False,sd_written=False)
    write(ROOT/'selected.json',choice);print('JOINT_ADAPTATION_POLICY_FROZEN',mode,policy,enhancement_accepted,flush=True)
if __name__=='__main__':main()
