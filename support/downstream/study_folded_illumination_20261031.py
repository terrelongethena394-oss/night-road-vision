"""Algebraically fold original linear illumination estimator;no new training."""
from pathlib import Path
import shutil,time
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont
from retinexformer_reference_runtime import Reference,ROOT as TEACHER
from road_tiny_restore_common import BASE,read,write,sha
from road_local_enhance_v2 import smoothstep
from shadowlift_lab import unpack,mean_y
from road_numpy_eval import evaluate
import road_accuracy_common as ac
ROOT=BASE/'road_folded_illumination_20261031_r1'

def fold(ref):
    est=ref.net.body[0].estimator
    conv1=est.conv1;depth=est.depth_conv;head=est.conv2
    # Four channels in the folded convolution are rawRGB and a constant-one
    # plane. The one plane preserves the bias boundary correction exactly.
    a=conv1.weight.detach().cpu().numpy()[:,:,0,0].astype(np.float64)
    a3=a[:,:3]+a[:,3:4]/3
    ab=np.concatenate([a3,conv1.bias.detach().cpu().numpy()[:,None]],1)
    d=depth.weight.detach().cpu().numpy().astype(np.float64)
    h=head.weight.detach().cpu().numpy()[:,:,0,0].astype(np.float64)
    kernel=np.zeros((3,4,5,5),np.float64)
    for o in range(40):
        group=o//10
        for j in range(10):
            kernel+=h[:,o,None,None,None]*ab[group*10+j,None,:,None,None]*d[o,j,None,None,:,:]
    bias=h@depth.bias.detach().cpu().numpy().astype(np.float64)+head.bias.detach().cpu().numpy().astype(np.float64)
    return kernel.astype(np.float32),bias.astype(np.float32)

def denoise_lit(raw,lit):
    a=lit.astype(np.float32);v=raw.astype(np.float32).max(2)/255
    y=(a[:,:,0]+2*a[:,:,1]+a[:,:,2])*.25;co=(a[:,:,0]-a[:,:,2])*.5;cg=(-a[:,:,0]+2*a[:,:,1]-a[:,:,2])*.25
    planes=np.stack([y,co,cg],2);pad=np.pad(planes,((3,3),(3,3),(0,0)),mode='reflect');num=np.zeros_like(planes);den=np.zeros_like(y)
    for dy in range(7):
        for dx in range(7):
            s=pad[dy:dy+240,dx:dx+400];d=s-planes
            dist=(d[:,:,0]**2*.25+d[:,:,1]**2+d[:,:,2]**2)/2.25
            dist=cv2.boxFilter(dist,cv2.CV_32F,(3,3),normalize=True,borderType=cv2.BORDER_REFLECT_101)
            w=np.exp(-np.maximum(dist-18,0)/100);num+=s*w[:,:,None];den+=w
    filt=num/den[:,:,None];dark=1-smoothstep(.10,.65,v)
    y+=(filt[:,:,0]-y)*(.3*dark);co+=(filt[:,:,1]-co)*(.6*dark);cg+=(filt[:,:,2]-cg)*(.6*dark)
    return np.floor(np.clip(np.stack([y+co-cg,y+cg,y-co-cg],2),0,255)+.5).astype(np.uint8)

class Folded:
    def __init__(self,ref):
        self.t=ref.t;self.ref=ref;self.k,self.b=fold(ref)
        self.kt=self.t.from_numpy(self.k).cuda();self.bt=self.t.from_numpy(self.b).cuda()
    def run(self,a,guard=True):
        if guard and mean_y(a)>48:return a.copy(),0.
        t=self.t;x=t.from_numpy(np.ascontiguousarray(a.transpose(2,0,1))).cuda().float()[None]/255
        with t.inference_mode():
            _,original=self.ref.net.body[0].estimator(x)
            folded=t.nn.functional.conv2d(t.cat([x,t.ones_like(x[:,:1])],1),self.kt,self.bt,padding=2)
            err=float((original-folded).abs().max())
            assert err<.0001,err
            z=(x*(1+folded)).clamp(0,1)[0].permute(1,2,0).cpu().numpy()
        return np.floor(z*255+.5).astype(np.uint8),err

def main():
    assert not ROOT.exists();ROOT.mkdir();(ROOT/'source').mkdir();(ROOT/'known').mkdir()
    write(ROOT/'protocol.json',dict(status='FROZEN_BEFORE_FOLDED_INFERENCE',
      source='Original-author LOL_v1 Retinexformer illumination estimator only. All3layers linear. Foldgroupedconv andmeanRGB into3out x4in x5x5 convolution (RGB + validone),plus3bias. Exact boundary correction;no transformer.',
      variants='Folded neural light-up;folded neural light-up + unchanged established h10 chroma.6/luma.3 patch denoise. Meanraw>48 bypass.',
      selection='Both require paired20 PSNR/SSIM higher than current diagnostic and direct known-image visual acceptance. Detection same80/global gates as tiny restoration;failure means display-only route with unchangedRAW detection,not accuracy gain.',
      scope='All development data reused,not independent confirmation.No new training.No hardware access.',hardware_access=False,sd_written=False))
    shutil.copy2(__file__,ROOT/'source'/Path(__file__).name)
    ref=Reference();engine=Folded(ref);np.concatenate([engine.k.reshape(-1),engine.b]).astype('<f4').tofile(ROOT/'folded_weights.f32')
    sources=read(BASE/'road_paper_recheck_20261031_r1/protocol.json')['sources'];canvas=Image.new('RGB',(1600,840),(15,15,15));font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14);d=ImageDraw.Draw(canvas);errors=[]
    for i,r in enumerate(sources):
        a=unpack(np.fromfile(r['raw'],'<u4')).reshape(240,400,3);cur=unpack(np.fromfile(r['current'],'<u4')).reshape(240,400,3)
        z,err=engine.run(a);zn=denoise_lit(a,z);errors.append(err)
        for col,(name,img) in enumerate([('RAW',a),('CURRENT',cur),('FOLDED NEURAL',z),('FOLDED + NLM',zn)]):
            canvas.paste(Image.fromarray(img),(col*400,i*280+40));Image.fromarray(img).save(ROOT/'known'/f'{i}_{col}.png');d.text((col*400+5,i*280+5),r['name']+' '+name,font=font,fill='white');d.text((col*400+5,i*280+22),f'Mean Y {mean_y(img):.2f}',font=font,fill='white')
    canvas.save(ROOT/'comparison.png');print('FOLDED_ILLUM_PREVIEW_READY','maxerror',max(errors),flush=True)
    ac.WEIGHTS=BASE/'road_viewadapt_20261030_r1/export/model.pt';det=ac.Detector();rows=read(BASE/'road_paper_predenoise_20261031_r1/predictions.json')['raw'];records={m:[] for m in ['raw','folded','folded_nlm']};begin=time.monotonic()
    for i,r in enumerate(rows):
        _,a=ac.sensor400(BASE/'road_brightness_route_20261030_r1/fresh/images'/r['name']);z,err=engine.run(a);errors.append(err);zn=denoise_lit(a,z) if r['cohort']=='low' else a.copy()
        pp=det.run([a,z,zn])
        for m,p in zip(records,pp):
            p=np.asarray(p,np.float32).reshape(-1,6);p=p[p[:,5]==1]
            records[m].append(dict(name=r['name'],cohort=r['cohort'],ground_truth=r['ground_truth'],detections=p.tolist()))
        if (i+1)%16==0:print('FOLDED_ILLUM_DEV',i+1,len(rows),round(time.monotonic()-begin),flush=True)
    scores={m:evaluate([r for r in rr if r['cohort']=='low'])['classes']['car'] for m,rr in records.items()};write(ROOT/'predictions.json',records)
    from study_road_local_enhance_v2 import metric,resize400,rgb
    from shadowlift_lab import Baseline
    from shadowlift_refine import final_display
    paired=[];baseline=Baseline()
    for path in sorted((BASE/'enhancement_study_20261025/data/Low').glob('*.png')):
        a=resize400(rgb(path));g=resize400(rgb(path.parent.parent/'Normal'/path.name.replace('low','normal')));z,err=engine.run(a);errors.append(err)
        for m,img in [('current',final_display(a,baseline.run(a))[0]),('folded',z),('folded_nlm',denoise_lit(a,z))]:paired.append(dict(name=path.name,method=m,**metric(img,g)))
    summary={m:{k:float(np.mean([r[k] for r in paired if r['method']==m])) for k in ['psnr','ssim']} for m in ['current','folded','folded_nlm']}
    quality={m:all(summary[m][k]>summary['current'][k] for k in ['psnr','ssim']) for m in ['folded','folded_nlm']}
    gates={m:dict(ap=scores[m]['ap50']>=scores['raw']['ap50']+.005,precision=scores[m]['precision']>=scores['raw']['precision']-.005,recall=scores[m]['recall']>=scores['raw']['recall']+.005) for m in ['folded','folded_nlm']}
    write(ROOT/'result.json',dict(scores=scores,paired_summary=summary,paired_rows=paired,quality_gates=quality,detection_gates=gates,folded_vs_original_max_abs=max(errors),weights_sha256=sha(ROOT/'folded_weights.f32'),hardware_access=False,sd_written=False))
    print('FOLDED_ILLUM_COMPLETE',dict(scores=scores,paired=summary,quality=quality,detection_gates=gates),flush=True)
if __name__=='__main__':main()
