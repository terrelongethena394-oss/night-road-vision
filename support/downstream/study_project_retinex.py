"""Paper-informed third candidate; all outcomes retained, no board changes."""
from pathlib import Path
import concurrent.futures as cf,json,subprocess,os,hashlib,shutil,time
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import study_road_local_enhance_v2 as common
from road_retinex_project import enhance,paper_reference,PRESETS
from road_local_enhance_v2 import gamma_baseline
from road_enhance_common import enhance as old_gamma
from road_numpy_eval import by_time,correct

BASE=common.BASE;OLD=common.OLD;HERE=common.HERE;APP=common.APP
ROOT=BASE/'road_project_retinex_20261029_r3'
R2=BASE/'road_local_enhance_20261029_r2'
read=common.read;write=common.write;sha=common.sha;rgb=common.rgb;resize400=common.resize400;panel=common.panel;metric=common.metric;words=common.words
def apply(a,m):
    if m=='raw':return a
    if m=='old_gamma':return old_gamma(a,1,32)[0]
    if m.startswith('gamma_'):return gamma_baseline(a,float(m.split('_')[1]))
    if m=='paper_reference':return paper_reference(a)[0]
    return enhance(a,m)[0]
def main():
    assert not ROOT.exists();ROOT.mkdir();(ROOT/'source').mkdir();(ROOT/'paired_regression').mkdir();(ROOT/'showcase').mkdir()
    names=read(OLD/'student_training_split.json')['validation']
    protocol=dict(status='R3_FROZEN_BEFORE_CALIBRATION_OR_OUTPUTS',reference_doi='10.1109/TCSII.2024.3361561',reference='Independent float implementation of equations2-12,11x11, sigma4, exp(-abs(d)/32), mirror reflect101. Not author RTL or same8segment fixed-point approximation.',own_additions='5x5 edge-aware dark smoothing,9x9 low-confidence chroma smoothing, adaptive scene bypass and highlight protection, noise-aware gain cap, generalized illumination tone exponent chosen on existing12 paired validation',candidates=PRESETS,pretrained_enhancement_weights=False,input='Identical RGB888 static photo profile as R2 for every method. RGB565 shown only as precision diagnostic.',selection='Select custom preset by PSNR+3SSIM-5*normalIdentityMAE/255 on old12 paired validation; gamma0.25/.35/.45 controls tune on same12; paper_reference control not selected as custom. Then freeze all parameters before20 reused paired and320 road regressions.',paired_validation_names=names,road_baseline='Reuse exact R2 raw/oldGamma actual-C320 predictions, verify every regenerated raw-input SHA matches; run paper and custom with identical C executable/weights/thresholds.',showcase=['c81ff2c0-420a8956.jpg','b8acc534-d5b64200.jpg','baa88157-4026332f.jpg'],hardware_access=False,sd_written=False)
    write(ROOT/'protocol.json',protocol)
    for n in ['road_retinex_project.py','study_project_retinex.py','road_local_enhance_v2.py','road_numpy_eval.py']:
        shutil.copy2(HERE/n,ROOT/'source'/n)
    shutil.copy2(R2/'source/YOLOv5_LICENSE',ROOT/'source/YOLOv5_LICENSE')
    methods=['old_gamma','gamma_0.25','gamma_0.35','gamma_0.45','paper_reference',*PRESETS];rows=[]
    for i,n in enumerate(names):
        a=resize400(rgb(OLD/'dataset/our485/low'/n));g=resize400(rgb(OLD/'dataset/our485/high'/n))
        for m in methods:
            z=apply(a,m);identity=apply(g,m)
            rows.append(dict(name=n,method=m,**metric(z,g),identity_mae=float(np.abs(identity.astype(np.float32)-g).mean())))
        print('R3_QUALITY_CALIBRATION',i+1,flush=True)
    summary={m:{k:float(np.mean([r[k] for r in rows if r['method']==m])) for k in ['psnr','ssim','mae','clip_fraction','identity_mae']} for m in methods}
    for v in summary.values():v['score']=v['psnr']+3*v['ssim']-5*v['identity_mae']/255
    chosen=max(PRESETS,key=lambda m:summary[m]['score']);control=max([m for m in methods if m.startswith('gamma_')],key=lambda m:summary[m]['psnr'])
    write(ROOT/'quality_validation.json',rows);write(ROOT/'selected.json',dict(status='R3_PRESET_FROZEN_BEFORE_REGRESSIONS',method=chosen,parameters=PRESETS[chosen],quality_validation=summary,strong_control=control,source_sha256=sha(HERE/'road_retinex_project.py')))
    print('R3_SELECTED',chosen,json.dumps(summary),flush=True)
    paired_rows=[]
    for at,p in enumerate(sorted((BASE/'enhancement_study_20261025/data/Low').glob('*.png'))):
        ref=p.parent.parent/'Normal'/p.name.replace('low','normal');a=resize400(rgb(p));g=resize400(rgb(ref));outs={m:apply(a,m) for m in ['old_gamma',control,'paper_reference',chosen]}
        for m,z in {'raw':a,**outs}.items():paired_rows.append(dict(name=p.name,group=sha(ref),method=m,**metric(z,g)))
        folder=ROOT/'paired_regression'/p.stem;folder.mkdir()
        for m,z in {'raw':a,**outs,'normal_reference':g}.items():Image.fromarray(z).save(folder/(m+'.png'))
        if at<4:panel([a,outs['old_gamma'],outs[chosen],g],['原图','旧保守Gamma','项目定制Retinex','正常曝光参考'],p.name,folder/'comparison.png')
    method_names=['raw','old_gamma',control,'paper_reference',chosen]
    scores={m:{k:float(np.mean([r[k] for r in paired_rows if r['method']==m])) for k in ['psnr','ssim','mae','clip_fraction']} for m in method_names}
    groups=sorted({r['group'] for r in paired_rows});grouped={m:{k:float(np.mean([np.mean([r[k] for r in paired_rows if r['method']==m and r['group']==g]) for g in groups])) for k in ['psnr','ssim']} for m in method_names}
    write(ROOT/'paired_regression/complete.json',dict(images=20,unique_reference_groups=len(groups),per_image=scores,per_reference_group=grouped,rows=paired_rows,not_new_blind_test=True))
    print('R3_PAIRED_REGRESSION',json.dumps(scores),flush=True)
    showcase(protocol,chosen)
    road320(chosen)
    write(ROOT/'complete.json',dict(status='PROJECT_RETINEX_QUALITY_AND_C320_COMPLETE',selected=chosen,hardware_access=False,sd_written=False))
def host_run(exe,env,a,folder):
    folder.mkdir();ip=folder/'input.u32';words(a,ip)
    run=subprocess.run([str(exe),str(APP/'runtime/weights.f32'),str(ip),str(folder)],capture_output=True,text=True,env=env,timeout=90)
    assert run.returncode==0 and 'ROAD_FP32_HOST_DONE' in run.stdout,(run.stdout,run.stderr)
    p=np.fromfile(folder/'boxes400.f32','<f4').reshape(-1,6);assert np.isfinite(p).all()
    return p
def host_tools():
    exe=R2/'host/road_ap.exe';build=read(R2/'host/build.json');assert sha(exe)==build['exe_sha256'] and sha(APP/'runtime/weights.f32')==build['weights_sha256']
    env=dict(os.environ);env['PATH']='E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin;'+env['PATH'];return exe,env
def showcase(protocol,chosen):
    exe,env=host_tools();examples=[];ground={r['name']:r['ground_truth'] for r in read(BASE/'road_enhance_20261027/regression480/raw/raw_predictions.json')}
    for name in protocol['showcase']:
        p=BASE/'road_realtime_20261027/fresh/images'/name;a=resize400(rgb(p));folder=ROOT/'showcase'/p.stem;folder.mkdir();stats={};images={}
        for m in ['raw','old_gamma','paper_reference',chosen]:
            z=apply(a,m);images[m]=z;Image.fromarray(z).save(folder/(m+'.png'));words(z,folder/(m+'400.u32'))
            pred=host_run(exe,env,z,folder/('native_'+m));op=pred[pred[:,4]>=.25];g=np.array(ground[name],np.float32);ok=correct(op,g,np.array([.5],np.float32))[0][:,0]
            vehicle=np.isin(op[:,5],[1,2,3]);tp=int((vehicle&ok).sum());fp=int((vehicle&~ok).sum());stats[m]=dict(tp=tp,fp=fp,operating_boxes=op.tolist())
        panel([images['raw'],images['old_gamma'],images['paper_reference'],images[chosen]],['原图RGB888','旧保守Gamma','论文公式浮点参考','项目定制Retinex'],name,folder/'comparison.png')
        labels=['原图','旧Gamma','论文浮点参考','项目定制'];ims=[]
        for m in ['raw','old_gamma','paper_reference',chosen]:
            im=Image.fromarray(images[m]);d=ImageDraw.Draw(im)
            for x1,y1,x2,y2,score,cls in stats[m]['operating_boxes']:
                if int(cls)==0:continue
                d.rectangle((x1,y1,x2,y2),outline='cyan',width=1)
            ims.append(np.array(im))
        labels=[label+f' TP{stats[m]["tp"]}/FP{stats[m]["fp"]}' for label,m in zip(labels,['raw','old_gamma','paper_reference',chosen])]
        panel(ims,labels,name+' 固定检测器实际C结果',folder/'detection_comparison.png',note='TP/FP据真实标注核对；不调阈值；此图是电脑C推理，不是开发板截图。')
        examples.append(dict(name=name,source_sha256=sha(p),results=stats,path=str(folder/'comparison.png')))
        print('R3_EXAMPLE',name,{m:(v['tp'],v['fp']) for m,v in stats.items()},flush=True)
    write(ROOT/'showcase/manifest.json',examples)
def road320(chosen):
    exe,env=host_tools();out=ROOT/'road_validation320';out.mkdir();work=out/'scratch';work.mkdir()
    dataset=BASE/'road_detection_20261026/dataset';refs=read(R2/'road_validation320/raw_predictions.json');raw_inputs={r['name']:r['input_sha256'] for r in refs}
    results={m:read(R2/'road_validation320'/(m+'_metrics.json')) for m in ['raw','old_gamma']}
    baseline_files={str(R2/'road_validation320'/(m+'_predictions.json')):sha(R2/'road_validation320'/(m+'_predictions.json')) for m in ['raw','old_gamma']}
    for method in ['paper_reference',chosen]:
        start=time.monotonic();records=[]
        def one(task):
            i,r=task;a=resize400(rgb(dataset/'images/val'/r['name']));v=a.astype(np.uint32);encoded=(v[:,:,0]|v[:,:,1]<<8|v[:,:,2]<<16).astype('<u4').tobytes();assert hashlib.sha256(encoded).hexdigest()==raw_inputs[r['name']]
            z=apply(a,method);folder=work/f'{method}_{i:03}';pred=host_run(exe,env,z,folder)
            result=dict(name=r['name'],timeofday=r['timeofday'],ground_truth=r['ground_truth'],detections=pred.tolist())
            for p in folder.iterdir():assert p.resolve().is_relative_to(work.resolve()) and p.is_file();p.unlink()
            folder.rmdir();return result
        with cf.ThreadPoolExecutor(2) as pool:
            for i,r in enumerate(pool.map(one,enumerate(refs)),1):
                records.append(r)
                if i%32==0:print('R3_C320',method,i,flush=True)
        metrics=by_time(records);write(out/(method+'_predictions.json'),records);write(out/(method+'_metrics.json'),metrics);results[method]=metrics
        print('R3_C320_COMPLETE',method,metrics['all']['mAP50'],time.monotonic()-start,flush=True)
    write(out/'complete.json',dict(status='R3_PAPER_AND_CUSTOM_ACTUAL_C320_COMPLETE',results=results,baseline_source_sha256=baseline_files,all320_regenerated_raw_input_hashes_match=True,weights_unchanged=True,hardware_access=False,sd_written=False))
if __name__=='__main__':main()
