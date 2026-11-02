"""Package a fixed-image quality mode from existing frozen/verified components."""
from pathlib import Path
import hashlib,json,shutil
import numpy as np
from PIL import Image,ImageDraw
from road_enhance_common import enhance

HERE=Path(__file__).resolve().parent
WORK=HERE.parents[1]
BASE=Path('E:/FPGA_Enhance_Work')
ROOT=BASE/'road_static_quality_demo_20261029'
APP=BASE/'road_conv13_p16_runtime_20261028_r1/firmware'

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def fnv(p):
    v=2166136261
    for b in Path(p).read_bytes():v=((v^b)*16777619)&0xffffffff
    return v
def vehicle(m):
    cs=[m['classes'][k] for k in ['car','truck','bus']]
    tp=sum(c['tp'] for c in cs);fp=sum(c['fp'] for c in cs);fn=sum(c['fn'] for c in cs)
    return dict(vehicle_mAP50=sum(c['ap50'] for c in cs)/3,tp=tp,fp=fp,fn=fn,precision=tp/(tp+fp) if tp+fp else 0,recall=tp/(tp+fn) if tp+fn else 0,car_ap50=cs[0]['ap50'])

def main():
    assert not ROOT.exists(),'Preserve existing demonstration package'
    ROOT.mkdir();(ROOT/'reference').mkdir();(ROOT/'photos').mkdir()
    selected=read(BASE/'road_roi_guard_20261028/selected.json')
    raw=selected['baseline'];detail=selected['chosen']['metrics']
    val={'single':vehicle(raw['all']),'detail':vehicle(detail['all'])}
    assert val['detail']['vehicle_mAP50']>val['single']['vehicle_mAP50']
    sources=[('first480',BASE/'road_roi_guard_20261028/fresh_evaluation/original_metrics.json',BASE/'road_roi_guard_20261028/fresh_evaluation/guarded_roi_metrics.json'),('second480',BASE/'road_roi_spatial_verifier_20261028/fresh_evaluation/original_metrics.json',BASE/'road_roi_spatial_verifier_20261028/fresh_ablation/geometry_without_verifier_metrics.json')]
    results={}
    for name,p,q in sources:
        a,b=read(p),read(q)
        results[name]={'source_sha256':{str(p):sha(p),str(q):sha(q)},'all':{'single':vehicle(a['all']),'detail':vehicle(b['all'])},'by_time':{t:{'single':vehicle(a['by_time'][t]),'detail':vehicle(b['by_time'][t])} for t in a['by_time']}}
    write(ROOT/'vehicle_comparison.json',dict(scope='Post-hoc three-vehicle-class summary of existing frozen evaluations, not new blind validation; same policies and scores, no threshold tuning',validation320=val,existing_test_batches=results,prior_four_class_release_failed_due_to_person_false_positives=True))
    fixtures=read(BASE/'road_roi_spatial_verifier_20261028/native_detector_full/complete.json')['cases']
    photos=[]
    for f in fixtures:
        if f['kind']!='real':continue
        idx=len(photos)+1;case=APP/'runtime/cases'/f['name'];words=np.fromfile(case/'input400.u32','<u4').reshape(240,400)
        rgb=np.stack([words&255,(words>>8)&255,(words>>16)&255],axis=-1).astype(np.uint8)
        enhanced,stats=enhance(rgb,1,32)
        encoded=(enhanced[:,:,0].astype(np.uint32)|(enhanced[:,:,1].astype(np.uint32)<<8)|(enhanced[:,:,2].astype(np.uint32)<<16)).astype('<u4')
        encoded.tofile(ROOT/'reference'/f'{idx:02}_enhanced.u32')
        panel=Image.new('RGB',(800,270));panel.paste(Image.fromarray(rgb),(0,30));panel.paste(Image.fromarray(enhanced),(400,30))
        ImageDraw.Draw(panel).text((10,8),f'PHOTO {idx}  RAW / ENHANCED  {f["timeofday"]}  same image',fill='white')
        panel.save(ROOT/'photos'/f'{idx:02}_same_image_enhancement.png')
        for mode in [0,1]:
            ui=np.zeros(16,dtype='<u4');ui[7]=1;ui[8]=1;ui[9]=1;ui[11]=stats['mean_in'];ui[12]=stats['alpha'];ui[13]=32;ui[14]=2;ui[15]=mode
            boxes=np.fromfile(case/('gold_detail_boxes400.f32' if mode else 'gold_raw_boxes400.f32'),'<f4').reshape(-1,6)
            ui[6]=len(boxes)
            view=Image.fromarray(enhanced).copy();draw=ImageDraw.Draw(view)
            for x1,y1,x2,y2,score,cls in boxes:
                label=['PERSON','CAR','TRUCK','BUS'][int(cls)]
                color=['orange','cyan','violet','lime'][int(cls)]
                draw.rectangle((float(x1),float(y1),float(x2),float(y2)),outline=color,width=1)
                draw.text((max(0,float(x1)),max(0,float(y1)-10)),f'{label} {score:.2f}',fill=color)
            view.save(ROOT/'photos'/f'{idx:02}_{"detail" if mode else "single"}_host_preview.png')
        names=['input400.u32','roi400.u32','gold_raw_boxes400.f32','gold_detail_boxes400.f32']
        photos.append(dict(id=f['name'],timeofday=f['timeofday'],source=f['source'],input_fnv32=fnv(case/'input400.u32'),roi_fnv32=fnv(case/'roi400.u32'),enhancement_stats=stats,sha256={n:sha(case/n) for n in names}))
    assert len(photos)==6
    for name in ['static_quality_demo.py','static_quality_demo.tcl']:shutil.copy2(HERE/name,ROOT/name)
    firmware=['road_detail.elf','display.bit','runtime/weights.f32','camera_common.tcl','host/render.exe','source/road_detail_config.h']
    manifest=dict(status='FIXED_IMAGE_DEMO_PREPARED_BOARD_CHECK_PENDING',verified_firmware=str(APP),default_detail_mode=1,selection_basis='Existing validation320 vehicle-only mean AP higher with unchanged geometry policy; latency no longer main goal; prior person FP issue remains disclosed',firmware_sha256={n:sha(APP/n) for n in firmware},entry_sha256={n:sha(ROOT/n) for n in ['static_quality_demo.py','static_quality_demo.tcl']},photos=photos,sd_written=False)
    write(ROOT/'manifest.json',manifest)
    python='E:\\FPGA_Enhance_Work\\nn_env312\\Scripts\\python.exe'
    def cmd(name,args):
        (ROOT/name).write_bytes(('@echo off\r\ncd /d "%~dp0"\r\n"'+python+'" "%~dp0static_quality_demo.py" '+args+'\r\npause\r\n').encode('ascii'))
    cmd('00_start_fixed_demo.cmd','start')
    for i in range(1,7):cmd(f'{i:02}_photo_{i}.cmd',f'show {i}')
    cmd('07_compare_photo1.cmd','compare 1')
    cmd('08_photo1_single.cmd','show 1 0')
    (ROOT/'09_restore_camera.cmd').write_bytes(('@echo off\r\n"'+python+'" "'+str(APP/'user_start.py')+'"\r\npause\r\n').encode('ascii'))
    text='''# 固定图片：图像增强＋车辆检测（2026-10-29）

项目主线改为逐张道路图片处理，不要求实时摄像头检测。选择原YOLOv5n四类FP32权重＋已验收的16路共享卷积核；固定图片默认全景与中心区域各检测一次。第二次检测利用原800×480图中保留的中心像素，帮助发现更小目标，不是超分辨率或新训练模型。高细节界面仍标记EXPERIMENT，因为此前四类默认发布门槛中的行人误检项没有通过。

## 演示方式

- 独立供电、接好JTAG后运行`00_start_fixed_demo.cmd`，完整加载既有程序和权重，随后处理第1张固定图。相机仍需按原硬件连接完成启动初始化，但推理和显示结果来自固定图片。
- 板卡程序已在运行时，用`01_photo_1.cmd`至`06_photo_6.cmd`逐张切换；每张完成后冻结，方便讲解和拍摄。JTAG传图、结果读回另需等待，不能与纯推理耗时混为一谈。
- 屏幕左侧是本张固定原图，右侧是同一张图的增强显示与检测框；不再是左右不同时间的摄像头画面。
- `07_compare_photo1.cmd`对同一图执行单次和双次检测，保存两份独立实板证据；最后保留双次结果。`08_photo1_single.cmd`可返回单次。
- `09_restore_camera.cmd`恢复此前已验收的摄像头模式。全部为JTAG/RAM操作，SD卡与Flash不写；断电后需重新加载。

## 模型选择与效果边界

原FP32权重保留：压缩、量化及增强训练候选未稳定胜过它。接受更长处理时间后，优先比较既有双次细节模式，而不是继续压缩网络。该选择只在已评测并实板验证的方案中作出，不能称为所有开源模型中的最好。

默认Gamma增强用于显示，检测使用原图支路。已有实验显示增强输入可能降低检测AP，因此不能宣传“通过增强使检测更准”。目前完成的是增强可视化＋车辆检测；若最终必须证明增强能改善识别，需要另做新算法与独立对照。

保留person/car/truck/bus四类网络，展示重点是汽车、卡车和公交车；没有把缺失识别类别当作背景重新训练。两批已有测试的车辆子集结果见下表，这是既有结果的描述性汇总，不是新盲测或重新证明以前四类发布通过。图片和阈值没有根据这次汇总再调。单张框数多不等于准确，漏检和误检都保留。

| 既有测试批次 | 单次车辆三类mAP@0.5 | 双次车辆三类mAP@0.5 | 单次车辆TP / FP | 双次车辆TP / FP |
|---|---:|---:|---:|---:|
'''
    for batch,v in results.items():
        a,b=v['all']['single'],v['all']['detail']
        text+=f'| {batch}（480图） | {a["vehicle_mAP50"]*100:.2f}% | {b["vehicle_mAP50"]*100:.2f}% | {a["tp"]} / {a["fp"]} | {b["tp"]} / {b["fp"]} |\n'
    text+='''
AP是检测指标，不是正确图片比例；TP/FP使用原固定置信度0.25与匹配IoU0.5。两批绝对分数不能混比。测试来自相同BDD来源，不证明本机摄像头或真实连续行车效果。该模式仍有误检，尤其行人误检问题没有消失。扩大中心细节的收益也不能归因于Gamma增强。

## 已准备的资料

六张图按此前冻结实板夹具顺序保留：3张真实夜间、2张黎明/黄昏、1张日间，以实际manifest元数据为准。`photos/`内有同图原/增强对比和两种检测主机预览，主机预览不是板上截图。板端处理后`board_evidence/`保存实际帧缓存、框、错误状态和逐字节核对，`last_board_result.json`记录最后一次结果。

模型和HLS源码及GPL许可继续在此前16路验收包内。此小包依赖本电脑E盘的已验收固件、Python和XSCT，未冒充可在任何电脑直接运行的独立软件。
'''
    (ROOT/'使用说明.md').write_text(text,encoding='utf-8')
    report=WORK/'固定图片增强与车辆检测方案_20261029.md'
    report.write_text(text+'\n\n演示入口：['+str(ROOT/'00_start_fixed_demo.cmd')+']('+str(ROOT/'00_start_fixed_demo.cmd').replace('\\','/')+')。\n',encoding='utf-8')
    print('STATIC_QUALITY_DEMO_PREPARED',ROOT,flush=True)
    print(json.dumps(val,indent=2),flush=True)

if __name__=='__main__':main()
