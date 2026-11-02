"""Recompute metrics, audit identities and check actual C on selected inputs."""
from pathlib import Path
import concurrent.futures as cf
import csv
import os
import shutil
import subprocess
import numpy as np
from PIL import Image
from audit_bright_detector_20261030 import OUT, DATA, MODEL, DLL, LAB, read, write, sha
from road_accuracy_common import sensor400, truth
from road_numpy_eval import evaluate, correct
from shadowlift_lab import words

def main():
    result=read(OUT/'result.json');protocol=read(OUT/'protocol.json');samples=read(OUT/'predictions.json')
    rows=read(DATA/'manifest.json');ids=read(OUT/'image_identity.json')
    assert sha(MODEL)==protocol['model_sha256'] and sha(DLL)==protocol['enhancer_dll_sha256']
    assert sha(DATA/'manifest.json')==protocol['manifest_sha256']
    assert sha(OUT/'protocol.json')==result['protocol_sha256']
    assert sha(OUT/'predictions.json')==result['predictions_sha256']
    assert len(samples)==len(ids)==len(rows)==416
    labels={}
    for sample,row,identity in zip(samples,rows,ids):
        assert sample['name']==row['name']==identity['name']
        image=DATA/'images'/row['name'];label=DATA/'labels'/(Path(row['name']).stem+'.txt')
        assert sha(image)==identity['source_sha256']
        assert sha(OUT/'enhanced'/row['name'])==identity['enhanced_sha256']
        gt=truth(label);gt=gt[gt[:,0]==1]
        for key in ['raw_multiview','enh_global_raw_tiles','raw_global','enh_global']:
            assert np.array_equal(gt,np.asarray(sample[key]['ground_truth'],np.float32).reshape(-1,5))
        labels[row['name']]=sha(label)
    for cohort in ['low','brighter']:
        for key in ['raw_multiview','enh_global_raw_tiles','raw_global','enh_global']:
            selected=[s[key] for s,r in zip(samples,rows) if r['cohort']==cohort]
            measured=evaluate(selected)['classes']['car'];assert measured==result['scores'][cohort][key]
    write(OUT/'label_sha256.json',labels)
    # The C network/decoder was board-validated previously. Check its output
    # on actual enhanced inputs too; do not label this new hardware acceptance.
    exe=Path('E:/FPGA_Enhance_Work/road_local_enhance_20261029_r2/host/road_ap.exe')
    build=read(exe.parent/'build.json');assert sha(exe)==build['exe_sha256']
    weight=MODEL.parent/'weights.f32';assert sha(weight)==read(MODEL.parent/'complete.json')['weights_sha256']
    env=dict(os.environ);env['PATH']='E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin;'+env['PATH']
    work=OUT/'actual_c';work.mkdir(exist_ok=True)
    low=[(s,r) for s,r in zip(samples,rows) if r['cohort']=='low']
    bright=[(s,r) for s,r in zip(samples,rows) if r['cohort']=='brighter']
    selected=[low[0],low[len(low)//2],bright[0]]
    def one(task):
        sample,row,key=task
        _,raw=sensor400(DATA/'images'/row['name'])
        im=raw if key=='raw_global' else np.asarray(Image.open(OUT/'enhanced'/row['name']))
        folder=work/(Path(row['name']).stem+'_'+key);folder.mkdir(exist_ok=True)
        ip=folder/'input.u32';words(im).tofile(ip)
        p=subprocess.run([str(exe),str(weight),str(ip),str(folder)],capture_output=True,text=True,env=env,timeout=90)
        assert p.returncode==0 and 'ROAD_FP32_HOST_DONE' in p.stdout,(row['name'],key,p.stderr)
        c=np.fromfile(folder/'boxes400.f32','<f4').reshape(-1,6);c=c[c[:,5]==1]
        gpu=np.asarray(sample[key]['detections'],np.float32).reshape(-1,6)
        # Fixed-threshold car detections should have same count and nearly
        # identical coordinates/scores. Low-score ordering need not be identical.
        c=c[c[:,4]>=.25];gpu=gpu[gpu[:,4]>=.25]
        assert len(c)==len(gpu),(row['name'],key,len(c),len(gpu))
        worst_xy=worst_score=0.;unused=set(range(len(gpu)))
        for box in c:
            i=min(unused,key=lambda j:float(np.max(np.abs(box[:4]-gpu[j,:4]))))
            xy=float(np.max(np.abs(box[:4]-gpu[i,:4])));sc=float(abs(box[4]-gpu[i,4]))
            assert xy<=.1 and sc<=.001,(row['name'],key,xy,sc)
            worst_xy=max(worst_xy,xy);worst_score=max(worst_score,sc);unused.remove(i)
        return dict(name=row['name'],view=key,cars_at025=len(c),max_coordinate_diff=worst_xy,
                    max_score_diff=worst_score,input_sha256=sha(ip),output_sha256=sha(folder/'boxes400.f32'))
    tasks=[(s,r,key) for s,r in selected for key in ['raw_global','enh_global']]
    with cf.ThreadPoolExecutor(2) as pool: checks=list(pool.map(one,tasks))
    # Compare all320 raw controls against cached actual C from the previous
    # evaluation, separately from the paired GPU primary result.
    native=read(Path('E:/FPGA_Enhance_Work/road_brightness_route_20261030_r1/fresh_evaluation/routed_low/native/candidate_predictions.json'))
    crows=[]
    for row in native:
        p=np.asarray(row['detections'],np.float32).reshape(-1,6);g=np.asarray(row['ground_truth'],np.float32).reshape(-1,5)
        crows.append(dict(detections=p[p[:,5]==1].tolist(),ground_truth=g[g[:,0]==1].tolist()))
    cmetric=evaluate(crows)['classes']['car'];gmetric=result['scores']['low']['raw_multiview']
    delta={k:gmetric[k]-cmetric[k] for k in ['ap50','precision','recall','tp','fp','fn']}
    assert abs(delta['ap50'])<=.002 and abs(delta['recall'])<=.002,delta
    verified=dict(status='PAIRED_METRICS_IDENTITIES_AND_SIX_ACTUAL_C_INPUTS_CHECKED',
        images=416,label_sha256_file_sha256=sha(OUT/'label_sha256.json'),
        exact_c_enhancer_sha256=sha(DLL),actual_c_examples=checks,
        gpu_minus_previous_c_raw_control=delta,result_sha256=sha(OUT/'result.json'),
        board_access=False,sd_written=False)
    write(OUT/'verified.json',verified)
    with (OUT/'指标.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f);w.writerow(['cohort','input','AP50_percent','precision_percent','recall_percent','TP','FP','FN'])
        for cohort,configs in result['scores'].items():
            for key,m in configs.items():w.writerow([cohort,key,*[round(m[k]*100,4) for k in ['ap50','precision','recall']],*[m[k] for k in ['tp','fp','fn']]])
    dest=Path(__file__).resolve().parents[2]/'阶段展示与收尾_20261030/增强输入专项核查'
    dest.mkdir(exist_ok=True)
    for n in ['实验结论.md','指标.csv','diagnostic_examples.png','protocol.json','result.json','verified.json']:
        shutil.copy2(OUT/n,dest/n)
    print('AUDIT_CHECKED',verified,flush=True)

if __name__=='__main__':main()
