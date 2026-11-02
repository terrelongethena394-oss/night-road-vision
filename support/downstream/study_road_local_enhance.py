"""Build, choose on old paired validation, then run fixed road/paired regressions."""
from pathlib import Path
import json,hashlib,shutil,math,time,csv
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont
from skimage.metrics import structural_similarity
from road_local_enhance import enhance as local,PRESETS
from road_enhance_common import enhance as old_gamma

HERE=Path(__file__).resolve().parent
BASE=Path('E:/FPGA_Enhance_Work')
ROOT=BASE/'road_local_enhance_20261029_r1'
OLD=BASE/'model_upgrade_20261023'
PAIRED=BASE/'enhancement_study_20261025'
APP=BASE/'road_conv13_p16_runtime_20261028_r1/firmware'

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rgb(p):return np.array(Image.open(p).convert('RGB'))
def resize400(a,quantize=False):
    a=cv2.resize(a,(800,480),interpolation=cv2.INTER_LINEAR)
    if quantize:a[:,:,0]&=248;a[:,:,1]&=252;a[:,:,2]&=248
    b=a.astype(np.uint16)
    return ((b[0::2,0::2]+b[0::2,1::2]+b[1::2,0::2]+b[1::2,1::2]+2)//4).astype(np.uint8)
def metric(a,b):
    mse=np.mean((a.astype(np.float64)-b)**2)
    return dict(psnr=float(10*math.log10(255**2/max(mse,1e-10))),ssim=float(structural_similarity(a,b,channel_axis=2,data_range=255,gaussian_weights=True,sigma=1.5,use_sample_covariance=False)),mae=float(np.abs(a.astype(np.float64)-b).mean()),clip_fraction=float(np.any(a>=254,axis=2).mean()))
def panel(images,labels,title,path,note='同一输入；电脑参考输出，尚未上板；未对结果额外调色。'):
    f=lambda n:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n)
    canvas=Image.new('RGB',(410*len(images)+10,350),'white');d=ImageDraw.Draw(canvas)
    d.text((10,8),title,font=f(23),fill='black')
    for i,(a,label) in enumerate(zip(images,labels)):
        d.text((10+410*i,44),label,font=f(19),fill='black');canvas.paste(Image.fromarray(a),(10+410*i,78))
    d.text((10,324),note,font=f(16),fill='#555555');canvas.save(path)

def initialize():
    assert not ROOT.exists(),'Preserve previous study'
    ROOT.mkdir();(ROOT/'paired_validation').mkdir();(ROOT/'paired_regression').mkdir();(ROOT/'showcase').mkdir()
    split=read(OLD/'student_training_split.json')
    protocol=dict(status='FROZEN_BEFORE_CUSTOM_ENHANCER_OUTPUTS',custom_source_sha256=sha(HERE/'road_local_enhance.py'),candidates=PRESETS,pretrained_enhancement_weights=False,algorithm='Own implementation of classical multi-scale local illumination, dark-region bilateral RGB smoothing, RGB-shared gain, local highlight protection, frame-level bright bypass. Established principles; not a newly trained neural network or claim of novel theory.',paired_selection={'names':split['validation'],'n':len(split['validation']),'score':'mean PSNR +3*meanSSIM -5*normal-identity-MAE/255; select among3 fixed custom presets. Report oldGamma separately, no outcome-dependent changes.'},paired_regression='Previously used LOLv2-real first20, same400x240 camera proxy for all methods; paired normal reference full RGB888, no brightness matching. Image-dependent pairs include repeated normal scenes; also report grouped by normal-image hash. Not a new blind test.',road_regression='Existing original320 validation, fixed detector and same preprocess; evaluate selected custom only, no reselection. Reuse historical raw/cap32 metrics and hashes. Extra480 only if new input detection meets original validation quality gate.',showcase_names=['c81ff2c0-420a8956.jpg','b8acc534-d5b64200.jpg','baa88157-4026332f.jpg'],hardware_access=False,sd_written=False)
    write(ROOT/'protocol.json',protocol)
    shutil.copy2(HERE/'road_local_enhance.py',ROOT/'road_local_enhance.py');shutil.copy2(HERE/'study_road_local_enhance.py',ROOT/'study_source.py')
    return protocol

def calibrate(protocol):
    rows=[]
    for at,name in enumerate(protocol['paired_selection']['names']):
        low=resize400(rgb(OLD/'dataset/our485/low'/name),True);high=resize400(rgb(OLD/'dataset/our485/high'/name))
        for method in ['old_gamma',*PRESETS]:
            z=old_gamma(low,1,32)[0] if method=='old_gamma' else local(low,method)[0]
            identity=old_gamma(high,1,32)[0] if method=='old_gamma' else local(high,method)[0]
            rows.append(dict(name=name,method=method,**metric(z,high),identity_mae=float(np.abs(identity.astype(np.float32)-high).mean())))
        print('PAIRED_VALIDATION',at+1,name,flush=True)
    summary={m:{k:float(np.mean([r[k] for r in rows if r['method']==m])) for k in ['psnr','ssim','mae','clip_fraction','identity_mae']} for m in ['old_gamma',*PRESETS]}
    for m,v in summary.items():v['score']=v['psnr']+3*v['ssim']-5*v['identity_mae']/255
    method=max(PRESETS,key=lambda m:summary[m]['score'])
    selected=dict(status='CUSTOM_PRESET_FROZEN_BEFORE_ROAD_AND_PAIRED_REGRESSION',method=method,parameters=PRESETS[method],validation=summary,source_sha256=sha(HERE/'road_local_enhance.py'),no_pretrained_enhancement_weights=True)
    write(ROOT/'paired_validation/per_image.json',rows);write(ROOT/'selected.json',selected)
    print('LOCAL_SELECTED',json.dumps(selected),flush=True);return method

def paired_regression(method):
    rows=[]
    for at,p in enumerate(sorted((PAIRED/'data/Low').glob('*.png'))):
        ref=PAIRED/'data/Normal'/p.name.replace('low','normal')
        low=resize400(rgb(p),True);high=resize400(rgb(ref));g=old_gamma(low,1,32)[0];z,stats=local(low,method)
        for name,im in [('raw',low),('old_gamma',g),('custom',z)]:rows.append(dict(name=p.name,group=sha(ref),method=name,**metric(im,high)))
        folder=ROOT/'paired_regression'/p.stem;folder.mkdir()
        for name,im in [('raw',low),('old_gamma',g),('custom',z),('reference',high)]:Image.fromarray(im).save(folder/(name+'.png'))
        if at<4:panel([low,g,z,high],['原图','旧Gamma','项目定制增强','正常曝光参考'],p.name,folder/'comparison.png')
    summary={m:{k:float(np.mean([r[k] for r in rows if r['method']==m])) for k in ['psnr','ssim','mae','clip_fraction']} for m in ['raw','old_gamma','custom']}
    groups=sorted({r['group'] for r in rows});grouped={m:{k:float(np.mean([np.mean([r[k] for r in rows if r['method']==m and r['group']==g]) for g in groups])) for k in ['psnr','ssim','mae']} for m in summary}
    write(ROOT/'paired_regression/complete.json',dict(images=len(rows)//3,unique_normal_hash_groups=len(groups),per_image_mean=summary,per_group_mean=grouped,rows=rows))
    print('PAIRED_REGRESSION',json.dumps(summary),flush=True)

def showcase(protocol,method):
    source=BASE/'road_realtime_20261027/fresh/images'
    outputs=[]
    for name in protocol['showcase_names']:
        low=resize400(rgb(source/name),True);g,gs=old_gamma(low,1,32);z,s=local(low,method)
        folder=ROOT/'showcase'/Path(name).stem;folder.mkdir()
        for tag,im in [('raw',low),('old_gamma',g),('custom',z)]:Image.fromarray(im).save(folder/(tag+'.png'))
        # Native RGB words for later actual-C/board port; not itself a board run.
        words=z.astype(np.uint32);(words[:,:,0]|words[:,:,1]<<8|words[:,:,2]<<16).astype('<u4').tofile(folder/'custom400.u32')
        panel([low,g,z],['真实夜间原图','原来的保守Gamma','新：局部照明＋暗部平滑'],name,folder/'comparison.png')
        outputs.append(dict(name=name,source_sha256=sha(source/name),old=gs,custom=s,path=str(folder/'comparison.png')))
    write(ROOT/'showcase/manifest.json',outputs);print('LOCAL_SHOWCASES_READY',flush=True)

def road_regression(method):
    from road_light_evaluate import validation_rows
    from road_arm_common import preprocess400
    from road_adapt_eval_core import torch,non_max_suppression,scale_boxes,evaluate_serial_predictions
    torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    rows=validation_rows();assert len(rows)==320
    frames=BASE/'road_pipeline_diagnostic_20261026/camera_order/frames'
    model=torch.load(BASE/'road_detection_20261026/frozen/road4_best.pt',map_location='cpu',weights_only=False)['model'].float().fuse().cuda().eval()
    out=ROOT/'road_validation320';out.mkdir();predictions={};stats=[]
    with torch.inference_mode():
        for at in range(0,len(rows),8):
            rs=rows[at:at+8];batch=[]
            for r in rs:
                low=rgb(frames/(Path(r['name']).stem+'.sim565.png'));z,s=local(low,method);stats.append(dict(name=r['name'],**s))
                batch.append(preprocess400(z).transpose(2,0,1))
            x=torch.from_numpy(np.ascontiguousarray(np.stack(batch))).cuda().float()/255
            ps=non_max_suppression(model(x),.001,.6,max_det=300)
            for r,p in zip(rs,ps):
                if len(p):scale_boxes((320,320),p[:,:4],(240,400),ratio_pad=((.8,.8),(0.,64.)))
                predictions[r['name']]=p.cpu().float().tolist()
            if at%64==0:print('LOCAL_ROAD_VALIDATION',at+len(rs),len(rows),flush=True)
    metrics=evaluate_serial_predictions(rows,predictions,out,'custom')
    raw_path=BASE/'road_enhance_20261027/validation320/raw/raw_metrics.json';gamma_path=BASE/'road_enhance_20261027/validation320/cap32/cap32_metrics.json'
    raw,gamma=read(raw_path),read(gamma_path)
    vehicle=lambda r:float(np.mean([r['classes'][k]['ap50'] for k in ['car','truck','bus']]))
    comparisons={t:{m:dict(four_class_mAP50=v['all' if t=='all' else 'by_time'][t]['mAP50'] if t!='all' else v['all']['mAP50'],vehicle_mAP50=vehicle(v['all'] if t=='all' else v['by_time'][t])) for m,v in [('raw',raw),('old_gamma',gamma),('custom',metrics)]} for t in ['all','night','dawn/dusk','daytime']}
    gates=dict(night_ap=metrics['by_time']['night']['mAP50']>=.95*raw['by_time']['night']['mAP50'],all_ap=metrics['all']['mAP50']>=.97*raw['all']['mAP50'],person_recall=metrics['by_time']['night']['classes']['person']['recall']>=.9*raw['by_time']['night']['classes']['person']['recall'])
    write(out/'complete.json',dict(status='CUSTOM_QUALITY_SELECTED_ROAD_REGRESSION_COMPLETE',comparisons=comparisons,enhanced_input_gate=gates,enhanced_input_eligible=all(gates.values()),default_detector_input='raw until separate enhanced-input evaluation passes',baseline_source_sha256={str(p):sha(p) for p in [raw_path,gamma_path]},stats=stats,sd_written=False,hardware_access=False))
    print('LOCAL_ROAD_REGRESSION_COMPLETE',json.dumps(comparisons),gates,flush=True)

def main():
    protocol=initialize();method=calibrate(protocol);paired_regression(method);showcase(protocol,method);road_regression(method)
    write(ROOT/'complete.json',dict(status='CUSTOM_ENHANCEMENT_OFFLINE_STUDY_COMPLETE',selected=method,hardware_access=False,sd_written=False))

if __name__=='__main__':main()
