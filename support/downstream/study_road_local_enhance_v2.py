"""RGB888 static-photo revision; full actual-C detector regression, CPU only."""
from pathlib import Path
import concurrent.futures as cf,json,hashlib,math,os,subprocess,shutil,time
import cv2,numpy as np
from PIL import Image
from road_local_enhance_v2 import enhance,PRESETS,gamma_baseline
from road_enhance_common import enhance as old_gamma
from study_road_local_enhance import panel,metric,resize400,rgb
from road_numpy_eval import by_time

HERE=Path(__file__).resolve().parent
BASE=Path('E:/FPGA_Enhance_Work')
ROOT=BASE/'road_local_enhance_20261029_r2'
OLD=BASE/'model_upgrade_20261023'
PAIRED=BASE/'enhancement_study_20261025'
APP=BASE/'road_conv13_p16_runtime_20261028_r1/firmware'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def apply(a,method):
    if method=='old_gamma':return old_gamma(a,1,32)[0]
    if method.startswith('gamma_'):return gamma_baseline(a,float(method.split('_')[1]))
    return enhance(a,method)[0]
def words(a,p):
    b=a.astype(np.uint32);(b[:,:,0]|b[:,:,1]<<8|b[:,:,2]<<16).astype('<u4').tofile(p)
def initialize():
    assert not ROOT.exists(),'Preserve all prior results'
    ROOT.mkdir();(ROOT/'quality_validation').mkdir();(ROOT/'paired_regression').mkdir();(ROOT/'showcase').mkdir();(ROOT/'source').mkdir()
    protocol=dict(status='FROZEN_BEFORE_R2_CALIBRATION_AND_REGRESSION',revision='R1 showed strong RGB565 chroma posterization; one known rain-night development image used to diagnose and improve input precision/color handling. No claim of blind test for that image.',input='Static public JPGs preserve all RGB888 channels; 1280x720 ->800x480 bilinear ->2x2 integer rounded average400x240, no 565 truncation. All comparison methods receive exact same RGB888.',algorithm='Own3x3 edge-aware dark RGB smoothing, 7x7 dark chroma smoothing/confidence,25x15 two-scale illumination, noise-proxy gain limit, common RGB gain and headlights protection. No pretrained enhancement weights or new neural network.',candidates=PRESETS,paired_selection_names=read(OLD/'student_training_split.json')['validation'],selection='Same12 old paired validation: maximize PSNR+3SSIM-5*normalIdentityMAE/255 among3 fixed presets; independently tune simple gamma0.25/0.35/0.45 on same12 as a stronger control. Freeze before road320 and reused paired20 regression. No post-test parameter changes.',road='All320 old validation, actual same FP32 C detector, raw/oldGamma/new at identical RGB888. AP floor0.001, confidence0.25 for operating counts, IoU0.5, NMS0.6. New input format means recompute all3 baselines, do not borrow prior565 scores.',quality='Same resized normal reference. PSNR/SSIM,normalidentityerror,clipping; reused public20 grouped by normal-image hash. Small subset, not full official benchmark.',showcase=['c81ff2c0-420a8956.jpg','b8acc534-d5b64200.jpg','baa88157-4026332f.jpg'],evaluator_check='NumPy evaluator independently reproduced all4 time groups AP50 and per-class TP/FP/FN exactly on historical320 predictions.',hardware_access=False,sd_written=False)
    for n in ['road_local_enhance_v2.py','road_numpy_eval.py','study_road_local_enhance_v2.py','study_road_local_enhance.py']:
        shutil.copy2(HERE/n,ROOT/'source'/n)
    shutil.copy2(BASE/'road_detection_20261026/yolov5/LICENSE',ROOT/'source/YOLOv5_LICENSE')
    write(ROOT/'protocol.json',protocol);return protocol
def calibrate(protocol):
    methods=['old_gamma','gamma_0.25','gamma_0.35','gamma_0.45',*PRESETS];rows=[]
    for at,n in enumerate(protocol['paired_selection_names']):
        a=resize400(rgb(OLD/'dataset/our485/low'/n));g=resize400(rgb(OLD/'dataset/our485/high'/n))
        for m in methods:
            z=apply(a,m);identity=apply(g,m)
            rows.append(dict(name=n,method=m,**metric(z,g),identity_mae=float(np.abs(identity.astype(np.float32)-g).mean())))
        print('R2_QUALITY_VALIDATION',at+1,flush=True)
    summary={m:{k:float(np.mean([r[k] for r in rows if r['method']==m])) for k in ['psnr','ssim','mae','clip_fraction','identity_mae']} for m in methods}
    for m,v in summary.items():v['score']=v['psnr']+3*v['ssim']-5*v['identity_mae']/255
    chosen=max(PRESETS,key=lambda m:summary[m]['score']);control=max([m for m in methods if m.startswith('gamma_')],key=lambda m:summary[m]['psnr'])
    selected=dict(status='R2_METHOD_AND_STRONG_GAMMA_CONTROL_FROZEN',method=chosen,strong_control=control,parameters=PRESETS[chosen],quality_validation=summary,source_sha256=sha(HERE/'road_local_enhance_v2.py'),pretrained_enhancement_weights=False)
    write(ROOT/'quality_validation/per_image.json',rows);write(ROOT/'selected.json',selected)
    print('R2_SELECTED',json.dumps(selected),flush=True);return chosen,control
def quality_and_examples(protocol,chosen,control):
    rows=[]
    for at,p in enumerate(sorted((PAIRED/'data/Low').glob('*.png'))):
        ref=PAIRED/'data/Normal'/p.name.replace('low','normal');a=resize400(rgb(p));g=resize400(rgb(ref))
        outs={m:apply(a,m) for m in ['old_gamma',control,chosen]}
        for m,z in {'raw':a,**outs}.items():rows.append(dict(name=p.name,group=sha(ref),method=m,**metric(z,g)))
        folder=ROOT/'paired_regression'/p.stem;folder.mkdir()
        for m,z in {'raw':a,**outs,'normal_reference':g}.items():Image.fromarray(z).save(folder/(m+'.png'))
        if at<4:panel([a,outs['old_gamma'],outs[chosen],g],['原图RGB888','旧保守Gamma','项目定制增强','正常曝光参考'],p.name,folder/'comparison.png')
    methods=['raw','old_gamma',control,chosen];groups=sorted({r['group'] for r in rows})
    summary={m:{k:float(np.mean([r[k] for r in rows if r['method']==m])) for k in ['psnr','ssim','mae','clip_fraction']} for m in methods}
    grouped={m:{k:float(np.mean([np.mean([r[k] for r in rows if r['method']==m and r['group']==g]) for g in groups])) for k in ['psnr','ssim']} for m in methods}
    write(ROOT/'paired_regression/complete.json',dict(images=20,unique_reference_groups=len(groups),per_image=summary,per_reference_group=grouped,rows=rows,not_new_blind_test=True))
    print('R2_PAIRED_REGRESSION',json.dumps(summary),flush=True)
    examples=[]
    for name in protocol['showcase']:
        p=BASE/'road_realtime_20261027/fresh/images'/name;a=resize400(rgb(p));z,s=enhance(a,chosen);g=old_gamma(a,1,32)[0]
        folder=ROOT/'showcase'/Path(name).stem;folder.mkdir()
        for m,im in [('raw',a),('old_gamma',g),('custom',z)]:Image.fromarray(im).save(folder/(m+'.png'));words(im,folder/(m+'400.u32'))
        panel([a,g,z],['同一原图RGB888','原来的保守Gamma','新：项目定制局部增强'],name,folder/'comparison.png')
        q=resize400(rgb(p),True);qz,_=enhance(q,chosen)
        panel([qz,z],['同算法但先截为RGB565','静态照片保留RGB888'],name+' 输入精度诊断',folder/'precision_diagnostic.png',note='诊断图用于说明输入精度差别，不能混入同条件算法胜负对比。')
        examples.append(dict(name=name,source_sha256=sha(p),stats=s,path=str(folder/'comparison.png')))
    write(ROOT/'showcase/manifest.json',examples)
def build_host():
    src=BASE/'road_arm_prototype_20261026/source_r2';out=ROOT/'host';out.mkdir()
    gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH']
    exe=out/'road_ap.exe';cmd=[str(gcc),'-O3','-std=c99','-msse2','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror','-DROAD_HOST_CONFIDENCE=.001f','-I'+str(src),str(src/'road_fp32.c'),str(HERE/'road_fp32_host.c'),'-lm','-o',str(exe)]
    p=subprocess.run(cmd,capture_output=True,text=True,env=env);(out/'build.log').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stderr
    write(out/'build.json',dict(command=cmd,source_sha256={str(p):sha(p) for p in [src/'road_fp32.c',src/'road_graph.h',HERE/'road_fp32_host.c']},exe_sha256=sha(exe),weights_sha256=sha(APP/'runtime/weights.f32')))
    return exe,env
def road_validation(chosen):
    exe,env=build_host();out=ROOT/'road_validation320';out.mkdir();work=out/'working';work.mkdir()
    dataset=BASE/'road_detection_20261026/dataset';rows=[r for r in read(dataset/'manifest.json') if r['split']=='val'];assert len(rows)==320
    refs={}
    for r in rows:
        t=np.array([[float(v) for v in line.split()] for line in (dataset/'labels/val'/(Path(r['name']).stem+'.txt')).read_text().splitlines()],np.float32).reshape(-1,5)
        g=t.copy();g[:,1]=(t[:,1]-t[:,3]/2)*400;g[:,2]=(t[:,2]-t[:,4]/2)*240;g[:,3]=(t[:,1]+t[:,3]/2)*400;g[:,4]=(t[:,2]+t[:,4]/2)*240;refs[r['name']]=g.tolist()
    results={}
    for method in ['raw','old_gamma',chosen]:
        records=[];start=time.monotonic()
        def one(task):
            i,r=task;source=dataset/'images/val'/r['name'];a=resize400(rgb(source));z=a if method=='raw' else apply(a,method)
            folder=work/f'{method}_{i:03}';folder.mkdir();ip=folder/'input.u32';words(z,ip)
            p=subprocess.run([str(exe),str(APP/'runtime/weights.f32'),str(ip),str(folder)],capture_output=True,text=True,env=env,timeout=90)
            assert p.returncode==0 and 'ROAD_FP32_HOST_DONE' in p.stdout,(r['name'],p.stdout,p.stderr)
            pred=np.fromfile(folder/'boxes400.f32','<f4').reshape(-1,6);assert np.isfinite(pred).all()
            result=dict(name=r['name'],timeofday=r['timeofday'],detections=pred.tolist(),ground_truth=refs[r['name']],input_sha256=sha(ip))
            # Only generated scratch files under this explicit experiment root.
            for f in folder.iterdir():
                assert f.resolve().is_relative_to(work.resolve()) and f.is_file()
                f.unlink()
            folder.rmdir();return result
        with cf.ThreadPoolExecutor(2) as pool:
            for i,r in enumerate(pool.map(one,enumerate(rows)),1):
                records.append(r)
                if i%32==0:print('R2_ACTUAL_C_ROAD',method,i,320,flush=True)
        metrics=by_time(records);write(out/(method+'_predictions.json'),records);write(out/(method+'_metrics.json'),metrics)
        results[method]=metrics;print('R2_ACTUAL_C_METHOD_COMPLETE',method,metrics['all']['mAP50'],time.monotonic()-start,flush=True)
    write(out/'complete.json',dict(status='R2_RGB888_ALL320_ALL3_ACTUAL_C_DETECTORS_COMPLETE',results=results,input_format='All3 methods same RGB888400 input',new_blind_test=False,source_labels=str(dataset/'labels/val'),hardware_access=False,sd_written=False))
def main():
    protocol=initialize();chosen,control=calibrate(protocol);quality_and_examples(protocol,chosen,control);road_validation(chosen)
    write(ROOT/'complete.json',dict(status='CUSTOM_R2_QUALITY_AND_ACTUAL_C_ROAD_REGRESSION_COMPLETE',selected=chosen,pretrained_enhancement_weights=False,hardware_access=False,sd_written=False))
if __name__=='__main__':main()
