"""Complete validation selection, freeze candidates, then ONE unseen evaluation."""
import os,time,csv
from pathlib import Path
import cv2,numpy as np
from road_light_common import ROOT,BASE,TEACHER,VARIANTS,read,write,sha
from road_integer_common import ROOT as QROOT
from road_light_evaluate import run,validation_rows,validation_loader
from road_integer_reference import evaluate
from road_arm_common import preprocess400

def gates(m,base):
    n=m['by_time']['night'];b=base['by_time']['night']
    return dict(night_ap=n['mAP50']>=.85*b['mAP50'],person_recall=n['classes']['person']['recall']>=.8*b['classes']['person']['recall'],
      all_ap=m['all']['mAP50']>=base['all']['mAP50']-.03,total_fp=sum(v['fp'] for v in n['classes'].values())<=1.25*sum(v['fp'] for v in b['classes'].values())+5,
      person_fp=n['classes']['person']['fp']<=1.2*b['classes']['person']['fp']+2)

def camera400(row):
    im=cv2.imread(str(ROOT/'fresh/images'/row['name']))[:,:,::-1];im=cv2.resize(im,(800,480),interpolation=cv2.INTER_LINEAR)
    im=im.copy();im[:,:,(0,2)]&=248;im[:,:,1]&=252
    return ((im.astype(np.uint16).reshape(240,2,400,2,3).sum((1,3))+2)//4).astype(np.uint8)
def fresh_loader(row):return preprocess400(camera400(row))

def main():
    start=time.monotonic()
    while not (ROOT/'training_complete.json').exists():
        if time.monotonic()-start>14400:raise TimeoutError('Training has not completed; no holdout evaluated')
        time.sleep(5)
    from road_small_input import ROOT as SMALL,preprocess256,evaluate as evaluate256
    assert (SMALL/'validation_complete.json').exists()
    out=ROOT/'selection';out.mkdir(exist_ok=False);base=read(ROOT/'baseline/teacher_metrics.json');records=[];rows=validation_rows()
    for tag in VARIANTS:
        frozen=ROOT/'frozen'/tag;receipt=read(frozen/'complete.json')
        for file,digest in receipt['weights'].items():
            # best+periodic search predeclared, last also recorded; identical bytes evaluated once.
            p=frozen/file;assert sha(p)==digest
            same=next((r for r in records if r['sha256']==digest),None)
            if same:m=read(Path(same['metrics_path']))
            else:
                d=out/(tag+'_'+p.stem);d.mkdir();m=run(p,rows,validation_loader,d,'candidate')
            metric_path=same['metrics_path'] if same else str(d/'candidate_metrics.json')
            g=gates(m,base);records.append(dict(variant=tag,checkpoint=file,path=str(p),sha256=digest,gates=g,passes=all(g.values()),
                  all_ap=m['all']['mAP50'],night_ap=m['by_time']['night']['mAP50'],metrics_path=metric_path,macs=read(frozen/'complete.json')['initialization']['conv_macs320']))
            write(out/'validation_records.json',records);print('STUDENT_VALIDATION_SELECTED_CHECK',tag,file,records[-1]['night_ap'],all(g.values()),flush=True)
    passed=[r for r in records if r['passes']]
    passed.sort(key=lambda r:(r['macs'],-r['night_ap'],r['sha256']))
    quant=[]
    for tag in ['m100','m110','m125']:
        f=QROOT/'validation_r1'/tag/(tag+'_metrics.json');m=read(f);g=gates(m,base)
        quant.append(dict(tag=tag,path=str(QROOT/tag/'qmodel.bin'),sha256=sha(QROOT/tag/'qmodel.bin'),bytes=(QROOT/tag/'qmodel.bin').stat().st_size,
          gates=g,passes=all(g.values()),all_ap=m['all']['mAP50'],night_ap=m['by_time']['night']['mAP50']))
    quant.sort(key=lambda r:(not r['passes'],r['bytes'],-r['night_ap']))
    q=next((r for r in quant if r['passes']),None);student=passed[0] if passed else None
    freeze=dict(status='ALL_SELECTIONS_FROZEN_BEFORE_NEW_HOLDOUT_INFERENCE',student=student,quantized=q,
        student_records=records,quantized_records=quant,teacher_sha256=sha(TEACHER),fresh_manifest_sha256=sha(ROOT/'fresh/manifest.json'),
        quantized_rule='Smallest model bytes among candidates passing the same validation gates, then highest night AP; all three ranges passed before this ranking was written.',no_test_used_to_select=True)
    small=read(SMALL/'validation_complete.json')['metrics'];sg=gates(small,base);freeze['input256']=dict(gates=sg,passes=all(sg.values()),teacher_sha256=sha(TEACHER))
    write(out/'frozen_candidates.json',freeze)
    fresh=read(ROOT/'fresh/manifest.json');freshrows=[{**r,'label_path':str(ROOT/'fresh/labels'/(Path(r['name']).stem+'.txt'))} for r in fresh]
    final=ROOT/'fresh_evaluation';final.mkdir(exist_ok=False)
    configs=[('teacher',TEACHER,'float')]
    if student:configs.append(('student',Path(student['path']),'float'))
    if q:configs.append(('q8',Path(q['path']).parent,'integer'))
    if all(sg.values()):configs.append(('input256',TEACHER,'256'))
    results={}
    for tag,model,kind in configs:
        d=final/tag;d.mkdir()
        if kind=='integer':m=evaluate(model,freshrows,fresh_loader,d,tag)
        elif kind=='256':m=evaluate256(freshrows,lambda r:preprocess256(camera400(r)),d,tag)
        else:m=run(model,freshrows,fresh_loader,d,tag)
        results[tag]=m;write(d/'complete.json',dict(status='FROZEN_UNSEEN_HOLDOUT_COMPLETE',model=str(model),metrics=m,no_retuning_allowed_on_this_holdout=True))
        print('UNSEEN_FINAL',tag,m['all']['mAP50'],m['by_time']['night']['mAP50'],flush=True)
    write(ROOT/'optimization_complete.json',dict(status='ALL_FIXED_BUDGET_TRAINING_VALIDATION_AND_UNSEEN_EVALUATIONS_COMPLETE',frozen=freeze,metrics=results,
       duration_seconds=time.monotonic()-start,no_hardware_access=True,no_sd_write=True))
    print('ROAD_OFFLINE_OPTIMIZATION_EVALUATIONS_COMPLETE',flush=True)
if __name__=='__main__':main()
