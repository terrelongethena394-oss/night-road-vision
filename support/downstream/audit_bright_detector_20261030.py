"""Fixed-model paired enhancement audit. Never accesses hardware."""
from pathlib import Path
import concurrent.futures as cf
import ctypes as ct
import hashlib
import json
import os
import shutil
import sys
import time
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
import road_accuracy_common as ac
from road_numpy_eval import evaluate, correct
from shadowlift_lab import words, unpack, mean_y

BASE = Path('E:/FPGA_Enhance_Work')
OUT = BASE / 'road_bright_detector_audit_20261030_r1'
DATA = BASE / 'road_brightness_route_20261030_r1/fresh'
LAB = BASE / 'road_shadowlift_20261030_r1'
MODEL = BASE / 'road_viewadapt_20261030_r1/export/model.pt'
DLL = LAB / 'c_proof/shadow.dll'

def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p, v): Path(p).write_text(json.dumps(v, ensure_ascii=False, indent=2), encoding='utf-8')
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

class Enhancer:
    def __init__(self):
        self.lib = ct.CDLL(str(DLL))
        class Stats(ct.Structure):
            _fields_ = [(n, ct.c_float) for n in ['mean_in','mean_out','noise_proxy','alpha','max_gain']]
        self.Stats = Stats
        self.up = ct.POINTER(ct.c_uint32)
        self.fp = ct.POINTER(ct.c_float)
        self.fn = self.lib.road_retinex_c
        self.fn.argtypes = [self.up, self.up, ct.c_uint, self.fp, ct.POINTER(Stats), ct.c_void_p, ct.c_void_p]
        self.fn.restype = ct.c_int

    def run(self, raw):
        a = words(raw).reshape(-1)
        before = a.tobytes()
        b = np.full(96002, 0x12345678, np.uint32)
        w = np.empty(17*96000+65538, np.float32)
        w.view(np.uint32)[[0,-1]] = 0x3f987654
        stats = self.Stats()
        bp = ct.cast(ct.c_void_p(b.ctypes.data+4), self.up)
        wp = ct.cast(ct.c_void_p(w.ctypes.data+4), self.fp)
        assert self.fn(a.ctypes.data_as(self.up),bp,96000,wp,ct.byref(stats),None,None) == 0
        assert b[0] == b[-1] == 0x12345678
        assert np.all(w.view(np.uint32)[[0,-1]] == 0x3f987654) and a.tobytes() == before
        return unpack(b[1:-1]).reshape(240,400,3)

def protocol():
    OUT.mkdir(exist_ok=True)
    assert sha(MODEL) == read(MODEL.parent/'complete.json')['source_checkpoint_sha256']
    assert sha(DLL) == read(LAB/'c_complete.json')['dll_sha256']
    rows = read(DATA/'manifest.json')
    assert len(rows) == 416 and sum(r['cohort']=='low' for r in rows) == 320
    p = dict(status='FIXED_PAIRED_RETROSPECTIVE_AUDIT_BEFORE_NEW_ENHANCEMENT_PREDICTIONS',
        dataset='Previously evaluated 320 low-light and 96 brighter images; NOT a new blind holdout.',
        primary='Car AP50, P/R, TP/FP/FN on all320 low-light images. Same selected new model for both arms.',
        control='96 brighter images with same model in both arms; do not claim deployed brightness router.',
        baseline='Raw global400 + three raw400 tiles from sensor800, frozen vehicle fusion weight0.75.',
        candidate='Replace ONLY global400 by exact ABI27 C-enhanced400. Three raw tiles unchanged. Same four forward passes per arm.',
        rationale='Test a minimally changed detector input path; current board still raw NN / enhanced display.',
        secondary='Single-global raw versus enhanced attribution, no tiles; cannot replace primary.',
        thresholds=dict(confidence_for_ap=.001,confidence_for_precision_recall=.25,iou_match=.5,nms=.6),
        gates=dict(low_car_ap_gain_min=.005,low_car_precision_drop_max=.005,
                   low_car_recall_drop_max=0,low_car_fp_increase_max=0,
                   brighter_car_ap_drop_max=.005),
        limits='Point-estimate audit without new blind confirmation or statistical-significance claim; no retuning on outcomes.',
        inference='CUDA FP32 same deterministic settings for both arms; PC result is not board acceptance.',
        model_sha256=sha(MODEL),enhancer_dll_sha256=sha(DLL),manifest_sha256=sha(DATA/'manifest.json'),
        hardware_access=False,sd_written=False)
    path = OUT/'protocol.json'
    if path.exists(): assert read(path)==p, 'Identity or fixed protocol changed'
    else:
        assert not (OUT/'predictions.json').exists()
        write(path,p)
    (OUT/'source').mkdir(exist_ok=True)
    shutil.copy2(Path(__file__),OUT/'source'/Path(__file__).name)
    return rows

def paired_counts(row):
    p=np.asarray(row['detections'],np.float32).reshape(-1,6)
    p=p[p[:,4]>=.25]
    g=np.asarray(row['ground_truth'],np.float32).reshape(-1,5)
    ok=correct(p,g,np.array([.5],np.float32))[0][:,0]
    return int(ok.sum()),int(len(p)-ok.sum())

def report(rows, samples):
    keys=['raw_multiview','enh_global_raw_tiles','raw_global','enh_global']
    groups={r['name']:r['cohort'] for r in rows}
    scores={cohort:{key:evaluate([r[key] for r in samples if groups[r['name']]==cohort])['classes']['car']
                    for key in keys} for cohort in ['low','brighter']}
    a=scores['low']['raw_multiview'];b=scores['low']['enh_global_raw_tiles']
    ab=scores['brighter']['raw_multiview'];bb=scores['brighter']['enh_global_raw_tiles']
    gates=dict(low_car_ap_gain=b['ap50']>=a['ap50']+.005,
               low_car_precision=b['precision']>=a['precision']-.005,
               low_car_recall=b['recall']>=a['recall'],low_car_fp=b['fp']<=a['fp'],
               brighter_car_ap=bb['ap50']>=ab['ap50']-.005)
    differences=[]
    for r in samples:
        if groups[r['name']]!='low':continue
        aa=paired_counts(r['raw_multiview']);bc=paired_counts(r['enh_global_raw_tiles'])
        differences.append(dict(name=r['name'],delta_tp=bc[0]-aa[0],delta_fp=bc[1]-aa[1],raw=aa,enhanced=bc))
    arr=np.array([[r['delta_tp'],r['delta_fp']] for r in differences])
    rng=np.random.default_rng(2026103007)
    boot=arr[rng.integers(0,len(arr),(5000,len(arr)))].mean(1)*100
    interval=np.quantile(boot,[.005,.995],axis=0).tolist()
    write(OUT/'per_image_differences.json',differences)
    result=dict(status='PASS_REQUIRES_FRESH_CONFIRMATION' if all(gates.values()) else 'REJECT_KEEP_RAW_NN_ENHANCED_DISPLAY',
        gates=gates,scores=scores,descriptive_paired_99pct_interval_per100_images_tp_fp=interval,
        examples_selected_after_results=True,images=len(samples),
        reused_evaluation_data=True,new_blind_confirmation=False,board_verified=False,
        protocol_sha256=sha(OUT/'protocol.json'),predictions_sha256=sha(OUT/'predictions.json'),
        hardware_access=False,sd_written=False)
    write(OUT/'result.json',result)
    # Diagnostic contact sheet: best TP change, worst TP change, most extra FP.
    chosen=[]
    for r in [max(differences,key=lambda z:(z['delta_tp'],-z['delta_fp'])),
              min(differences,key=lambda z:(z['delta_tp'],-z['delta_fp'])),
              max(differences,key=lambda z:z['delta_fp'])]:
        if r['name'] not in [z['name'] for z in chosen]:chosen.append(r)
    canvas=Image.new('RGB',(800,len(chosen)*280),(15,15,15));font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',13)
    samplemap={r['name']:r for r in samples}
    for y,r in enumerate(chosen):
        _,raw=ac.sensor400(DATA/'images'/r['name']);enh=np.asarray(Image.open(OUT/'enhanced'/r['name']))
        for x,(key,im,title) in enumerate([('raw_multiview',raw,'RAW NN'),('enh_global_raw_tiles',enh,'ENH GLOBAL / RAW TILES')]):
            frame=Image.fromarray(im);d=ImageDraw.Draw(frame)
            for box in samplemap[r['name']][key]['detections']:
                if box[4]>=.25:d.rectangle(tuple(box[:4]),outline=(0,255,80),width=1)
            canvas.paste(frame,(x*400,y*280+40));d=ImageDraw.Draw(canvas)
            count=r['raw'] if x==0 else r['enhanced']
            d.text((x*400+4,y*280+2),f'{title} TP {count[0]} FP {count[1]}',fill='white',font=font)
            d.text((x*400+4,y*280+20),r['name'],fill='white',font=font)
    canvas.save(OUT/'diagnostic_examples.png')
    table=['| 条件 | 汽车AP50 | 精确率 | 召回率 | TP | FP | FN |','|---|---:|---:|---:|---:|---:|---:|']
    for label,v in [('暗光原图多视图',a),('暗光增强全图＋原图细节',b),('较亮原图多视图',ab),('较亮增强全图＋原图细节',bb)]:
        table.append(f"| {label} | {v['ap50']*100:.2f}% | {v['precision']*100:.2f}% | {v['recall']*100:.2f}% | {v['tp']} | {v['fp']} | {v['fn']} |")
    text='# 固定检测模型的增强输入对照\n\n'+ '\n'.join(table)
    text+=f"\n\n结论：`{result['status']}`。验收门槛：`{json.dumps(gates,ensure_ascii=False)}`。\n"
    text+='\n两组使用同一汽车专项模型、同一原图与标注。仅替换全图400×240输入为当前ABI27增强图，三个原图细节视图保持不变；融合、阈值、框数上限均冻结。相同图像的原图细节预测在两组中共享。\n'
    text+='\n这是电脑CUDA FP32审计，不是新增上板验收。320张暗光图和96张较亮图已被此前评测使用；部分图片也用于增强效果预览，不能再称为新盲测。图示按结果选取，包含退步和误检案例。所有参数在这次新增增强推理前固定，未根据结果调参。\n'
    text+='\n当前板卡仍为原图识别、增强显示。本次未写板卡、SD卡或Flash。即使本次候选通过，也应先用未看过的标注图片确认，再移植；若未通过，保留原图识别，不能将亮度提升包装成识别提升。\n'
    for cohort in ['low','brighter']:
        ar=scores[cohort]['raw_global'];br=scores[cohort]['enh_global']
        text+=f"\n次要单视图消融（{cohort}）：AP50 {ar['ap50']*100:.2f}%→{br['ap50']*100:.2f}%。这项不能替代主要多视图结论。\n"
    (OUT/'实验结论.md').write_text(text,encoding='utf-8')
    work=Path(__file__).resolve().parents[2]
    (work/'增强输入识别对照_20261030.md').write_text(text,encoding='utf-8')
    print('BRIGHT_DETECTOR_AUDIT_COMPLETE',json.dumps(result,ensure_ascii=True),flush=True)

def main():
    rows=protocol();engine=Enhancer();cv2.setNumThreads(1)
    start=time.monotonic();_,probe=ac.sensor400(DATA/'images'/rows[0]['name']);enh=engine.run(probe)
    print('ENHANCER_BENCHMARK_SECONDS',round(time.monotonic()-start,3),'MEANS',mean_y(probe),mean_y(enh),flush=True)
    if '--prepare-only' in sys.argv:return
    cache=OUT/'enhanced';cache.mkdir(exist_ok=True)
    for cohort in ['low','brighter']:
        assert sum(r['cohort']==cohort for r in rows)==(320 if cohort=='low' else 96)
    # PNG bytes despite original JPEG filename, to preserve exact enhanced pixels.
    def enhance_one(r):
        p=cache/r['name'];_,im=ac.sensor400(DATA/'images'/r['name'])
        if p.exists():
            a=np.asarray(Image.open(p));assert a.shape==im.shape and a.dtype==np.uint8
        else:
            a=engine.run(im);Image.fromarray(a).save(p,format='PNG')
        return dict(name=r['name'],source_sha256=sha(DATA/'images'/r['name']),
                    enhanced_sha256=sha(p),mean_raw=mean_y(im),mean_enhanced=mean_y(a))
    begin=time.monotonic();image_records=[]
    with cf.ThreadPoolExecutor(4) as pool:
        for i,item in enumerate(pool.map(enhance_one,rows)):
            image_records.append(item)
            if (i+1)%32==0:print('EXACT_C_ENHANCEMENT',i+1,len(rows),round(time.monotonic()-begin,1),flush=True)
    write(OUT/'image_identity.json',image_records)
    ac.WEIGHTS=MODEL
    detector=ac.Detector();samples=[]
    for at in range(0,len(rows),8):
        rr=rows[at:at+8];images=[]
        for r in rr:
            sensor,full=ac.sensor400(DATA/'images'/r['name']);en=np.asarray(Image.open(cache/r['name']))
            images.extend([full,en]+[sensor[y:y+240,x:x+400] for x,y in ac.TILES])
        pred=detector.run(images)
        for j,r in enumerate(rr):
            p=pred[j*5:j*5+5];tiles=[ac.map_tile(p[k+2],*ac.TILES[k]) for k in range(3)]
            variants={'raw_multiview':ac.fuse(p[0],tiles,.75),'enh_global_raw_tiles':ac.fuse(p[1],tiles,.75),
                      'raw_global':np.asarray(p[0],np.float32).reshape(-1,6),'enh_global':np.asarray(p[1],np.float32).reshape(-1,6)}
            gt=ac.truth(DATA/'labels'/(Path(r['name']).stem+'.txt'));gt=gt[gt[:,0]==1]
            sample=dict(name=r['name'])
            for key,v in variants.items():
                v=v[v[:,5]==1]
                sample[key]=dict(name=r['name'],ground_truth=gt.tolist(),detections=v.tolist())
            samples.append(sample)
        if (at+len(rr))%32==0:print('CUDA_PAIRED_DETECTION',at+len(rr),len(rows),round(time.monotonic()-begin,1),flush=True)
    write(OUT/'predictions.json',samples)
    write(OUT/'timing.json',dict(total_seconds=time.monotonic()-start,images=len(rows),forwards=5*len(rows),hardware_access=False))
    report(rows,samples)

if __name__=='__main__':main()
