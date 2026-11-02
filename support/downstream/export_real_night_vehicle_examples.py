"""Real BDD night photos, honest illustrative selection, fresh native-C inference."""
from pathlib import Path
import json,hashlib,subprocess,os,shutil
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont
from road_enhance_common import enhance

HERE=Path(__file__).resolve().parent
BASE=Path('E:/FPGA_Enhance_Work')
OUT=BASE/'road_real_night_examples_20261029'
REG=BASE/'road_enhance_20261027/regression480'
DATA=BASE/'road_realtime_20261027/fresh'
APP=BASE/'road_conv13_p16_runtime_20261028_r1/firmware'
HOST=BASE/'road_roi_spatial_verifier_20261028/native_detector_full/host.exe'
WEIGHTS=APP/'runtime/weights.f32'
NAMES=['PERSON','CAR','TRUCK','BUS']

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def font(size):return ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',size)
def sensor(rgb):
    a=cv2.resize(rgb,(800,480),interpolation=cv2.INTER_LINEAR);a[:,:,0]&=248;a[:,:,1]&=252;a[:,:,2]&=248;b=a.astype(np.uint16)
    return ((b[0::2,0::2]+b[0::2,1::2]+b[1::2,0::2]+b[1::2,1::2]+2)//4).astype(np.uint8)
def encode(rgb,path):
    a=rgb.astype(np.uint32);(a[:,:,0]|(a[:,:,1]<<8)|(a[:,:,2]<<16)).astype('<u4').tofile(path)
def match(pred,gt):
    if not len(pred) or not len(gt):return set()
    a=gt[:,None,1:];b=pred[None,:,:4]
    wh=np.maximum(0,np.minimum(a[:,:,2:],b[:,:,2:])-np.maximum(a[:,:,:2],b[:,:,:2]));inter=wh.prod(2)
    area_a=(a[:,:,2:]-a[:,:,:2]).prod(2);area_b=(b[:,:,2:]-b[:,:,:2]).prod(2)
    iou=inter/(area_a+area_b-inter+1e-7)
    t,p=np.where((iou>=.5)&(gt[:,0:1]==pred[None,:,5]))
    if not len(t):return set()
    m=np.stack([t,p,iou[t,p]],axis=1)
    if len(m)>1:
        m=m[m[:,2].argsort()[::-1]];m=m[np.unique(m[:,1],return_index=True)[1]];m=m[np.unique(m[:,0],return_index=True)[1]]
    return {int(v) for v in m[:,0] if int(gt[int(v),0]) in (1,2,3)}
def summarize(row):
    gt=row['ground_truth'];matched={i for i in row['matched_gt'] if int(gt[i][0]) in (1,2,3)}
    n=sum(p[4]>=.25 and int(p[5]) in (1,2,3) for p in row['detections'])
    return matched,n-len(matched)
def draw_boxes(rgb,boxes):
    im=Image.fromarray(rgb).copy();d=ImageDraw.Draw(im)
    for x1,y1,x2,y2,score,cls in boxes:
        if int(cls) not in (1,2,3):continue
        color=['orange','cyan','violet','lime'][int(cls)]
        d.rectangle((float(x1),float(y1),float(x2),float(y2)),outline=color,width=1)
        d.text((max(0,float(x1)),max(0,float(y1)-10)),f'{NAMES[int(cls)]} {score:.2f}',fill=color,font=font(10))
    return im
def main():
    assert not OUT.exists(),'Preserve prior images/evidence'
    OUT.mkdir()
    raw=read(REG/'raw/raw_predictions.json');enh={r['name']:r for r in read(REG/'auto/auto_predictions.json')}
    stats={r['name']:r for r in read(REG/'auto/enhancement_stats.json')}
    rows=[]
    for r in raw:
        if r['timeofday']!='night':continue
        e=enh[r['name']];assert r['ground_truth']==e['ground_truth']
        a,fp0=summarize(r);b,fp1=summarize(e)
        rows.append(dict(name=r['name'],tp0=len(a),tp1=len(b),fp0=fp0,fp1=fp1,new=sorted(b-a),lost=sorted(a-b),stats=stats[r['name']]))
    positive=[r for r in rows if r['tp1']>r['tp0'] and r['fp1']<=r['fp0'] and not r['lost']]
    positive.sort(key=lambda r:(r['tp1']-r['tp0'],r['fp0']-r['fp1'],-r['stats']['mean_in'],r['name']),reverse=True)
    negative=[r for r in rows if r['tp1']<r['tp0']]
    negative.sort(key=lambda r:(r['tp0']-r['tp1'],r['fp1']-r['fp0'],r['name']),reverse=True)
    chosen=positive[:3]+negative[:1]
    population=dict(night_images=len(rows),more_correct_vehicles=sum(r['tp1']>r['tp0'] for r in rows),fewer_correct_vehicles=len(negative),unchanged_correct_count=sum(r['tp1']==r['tp0'] for r in rows),note='Counts describe fixed-threshold TP only, not per-image accuracy or AP; images selected after viewing outcomes for illustration.')
    write(OUT/'全部夜间图片统计.json',dict(population=population,all_images=rows,source_sha256={str(p):sha(p) for p in [REG/'raw/raw_predictions.json',REG/'auto/auto_predictions.json',REG/'auto/enhancement_stats.json']}))
    meta={r['name']:r for r in read(DATA/'manifest.json')};rawmap={r['name']:r for r in raw}
    env=dict(os.environ);env['PATH']='E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin;'+env.get('PATH','')
    examples=[];panels=[]
    for at,row in enumerate(chosen):
        case=OUT/f'{at+1:02}_{Path(row["name"]).stem}';case.mkdir();shutil.copy2(DATA/'images'/row['name'],case/'source_original.jpg')
        assert sha(case/'source_original.jpg')==meta[row['name']]['image_sha256']
        decoded=cv2.imdecode(np.fromfile(case/'source_original.jpg',np.uint8),cv2.IMREAD_COLOR)
        assert decoded is not None
        rgb=sensor(decoded[:,:,::-1].copy());e,s=enhance(rgb,1,32);assert s=={k:v for k,v in row['stats'].items() if k!='name'}
        encode(rgb,case/'input400.u32');encode(e,case/'enhanced400.u32')
        Image.fromarray(rgb).save(case/'raw.png');Image.fromarray(e).save(case/'enhanced.png')
        gt=np.array(rawmap[row['name']]['ground_truth'],dtype=np.float32).reshape(-1,5)
        outputs=[]
        for name,input_path,gpu_row in [('raw',case/'input400.u32',rawmap[row['name']]),('enhanced',case/'enhanced400.u32',enh[row['name']])]:
            dest=case/('native_'+name);dest.mkdir()
            p=subprocess.run([str(HOST),str(WEIGHTS),str(input_path),str(dest)],capture_output=True,text=True,env=env,timeout=90)
            (dest/'run.log').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stdout+p.stderr
            boxes=np.fromfile(dest/'boxes400.f32','<f4').reshape(-1,6);matched=match(boxes,gt)
            expected,_=summarize(gpu_row);assert matched==expected,'Native C changed the illustrative matching result'
            n=int(np.isin(boxes[:,5],[1,2,3]).sum());outputs.append(dict(tp=len(matched),fp=n-len(matched),matched_gt=sorted(matched),boxes=boxes))
        panel=Image.new('RGB',(1640,480),'white');d=ImageDraw.Draw(panel)
        d.text((12,8),('成功样例（按结果筛选）' if at<3 else '失败样例（保留限制）')+'  '+row['name'],font=font(23),fill='black')
        headings=['(a) 同一张真实夜间原图','(b) 当前板端算法增强','(c) 原图送入同一检测器','(d) 增强图送入同一检测器']
        ims=[Image.fromarray(rgb),Image.fromarray(e),draw_boxes(rgb,outputs[0]['boxes']),draw_boxes(e,outputs[1]['boxes'])]
        for j,(label,im) in enumerate(zip(headings,ims)):
            x=10+j*410;d.text((x,45),label,font=font(19),fill='black');panel.paste(im,(x,78))
        for j,o in enumerate(outputs):d.text((830+j*410,328),f'正确车辆 {o["tp"]} / 误检 {o["fp"]}',font=font(19),fill='#164c3b')
        d.text((12,360),f'相同权重；置信度≥0.25；匹配IoU≥0.5；均为电脑实际C推理。亮度均值 {s["mean_in"]}→{s["mean_out"]}。',font=font(20),fill='black')
        d.text((12,394),'未人工压暗原图，未对增强结果二次提亮；所有车辆预测框均保留，不用框数冒充正确数。',font=font(20),fill='black')
        d.text((12,430),'这些是个例展示，不能代表整体提升；原1280×720照片经已声明的板端采集代理流程变为400×240。',font=font(19),fill='#555555')
        panel.save(case/'four_column_comparison.png');panels.append(panel)
        examples.append({**row,'source':meta[row['name']],'directory':str(case),'source_sha256':sha(case/'source_original.jpg'),'input_sha256':sha(case/'input400.u32'),'enhanced_sha256':sha(case/'enhanced400.u32'),'native_results':[{k:v for k,v in o.items() if k!='boxes'} for o in outputs]})
        print('NATIVE_EXAMPLE',row['name'],[(o['tp'],o['fp']) for o in outputs],flush=True)
    overview=Image.new('RGB',(1640,480*3),'white')
    for i,p in enumerate(panels[:3]):overview.paste(p,(0,i*480))
    overview.save(OUT/'三张成功样例_四列对比.png')
    write(OUT/'来源与验证.json',dict(status='ILLUSTRATIVE_REAL_NIGHT_NATIVE_C_RESULTS_BOARD_PENDING',selection='Success: higher vehicle TP, no FP increase, no previously matched vehicle lost; sort by TP gain then FP decrease then darker input, take3. Failure: largest TP decrease then FP increase, take1. Entire selection is post-hoc, not new validation.',population=population,weights_sha256=sha(WEIGHTS),host_sha256=sha(HOST),algorithm='Frozen adaptive Gamma0.65/cap32, same integer pixel algorithm as current board',examples=examples,hardware_access=False,sd_written=False))
    text=f'''# 真实夜间道路：增强与检测同图对比

已从本地已下载、带真实标注的BDD100K道路数据中找到照片，不使用人工暗化图或生成图。原始来源为[BDD100K](https://github.com/bdd100k/bdd100k)，下载镜像及固定版本沿用原项目来源记录。三张成功样例和一张失败样例均重新运行实际C检测器，核对到既有GPU评测的正确匹配目标；不是手画检测框。

每图四列：原图、增强图、原图检测、增强后检测。增强为目前板端相同的自适应Gamma，检测器权重固定，置信度0.25、匹配IoU0.5。图中框均来自实际推理；TP/FP使用真实标注事后核对。原图没有人为压暗，增强没有事后补亮或调色。当前图片是电脑实际C结果，还不是新图片的实板读回。

本次从240张既有夜间回归图中按结果筛选展示：{population['more_correct_vehicles']}张增强后正确检出车辆数增加、{population['fewer_correct_vehicles']}张减少、{population['unchanged_correct_count']}张正确数相同。相同正确数不代表全部框相同。整体夜间四类mAP50此前为24.23%→22.30%，不能用这些成功个例声称整体检测更好。完整240张的统计和失败例保留在本目录。

逐图源文件、哈希、真值匹配索引及新C输出在来源与验证.json和各子目录；这些照片已经用于过往评测，只作展示，不充当新盲测。目标是把已有能力展示清楚，不改变已有整体结论。下一步可将同一份输入和增强检测路径送入7020，核对框与帧缓存，再做实体屏幕拍摄。
'''
    (OUT/'说明.md').write_text(text,encoding='utf-8');print('REAL_NIGHT_EXAMPLES_READY',OUT,flush=True)

if __name__=='__main__':main()
