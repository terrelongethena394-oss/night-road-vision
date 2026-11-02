"""Bounded development screen: source-domain noise filtering before paper Retinex.

No new training, no board writes. All evaluation photos were already exposed.
The image filter never receives detector predictions or ground-truth labels.
"""
from pathlib import Path
import hashlib,json,shutil,time
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont
import road_accuracy_common as ac
from road_numpy_eval import evaluate
from road_retinex_project import illumination,paper_reference
from shadowlift_lab import read,write,sha,unpack,mean_y,smooth

BASE=Path('E:/FPGA_Enhance_Work')
ROOT=BASE/'road_paper_predenoise_20261031_r1'
AUDIT=BASE/'road_bright_detector_audit_20261030_r1'
DATA=BASE/'road_brightness_route_20261030_r1/fresh'
MODEL=BASE/'road_viewadapt_20261030_r1/export/model.pt'
VARIANTS={'pre_chroma':dict(h=3.,luma=0.,chroma=.9),
          'pre_light':dict(h=3.,luma=.2,chroma=.9)}

def enhance(a,name):
    if mean_y(a)>48:return a.copy()
    p=VARIANTS[name];r=a.astype(np.float32)
    # Estimate illumination from the unfiltered input; filtering cannot move
    # the illumination edges or depend on vehicle bounding boxes.
    f=illumination(r);g=np.divide(np.sqrt(f*(2-f)),f,out=np.ones_like(f),where=f>1e-8)
    y=(r[:,:,0]+2*r[:,:,1]+r[:,:,2])*.25
    co=(r[:,:,0]-r[:,:,2])*.5;cg=(-r[:,:,0]+2*r[:,:,1]-r[:,:,2])*.25
    planes=np.stack([y,co,cg],2);pad=np.pad(planes,((3,3),(3,3),(0,0)),mode='reflect')
    num=np.zeros_like(planes);den=np.zeros_like(y)
    for dy in range(7):
        for dx in range(7):
            shifted=pad[dy:dy+240,dx:dx+400]
            delta=shifted-planes
            dist=(delta[:,:,0]**2*.25+delta[:,:,1]**2+delta[:,:,2]**2)/2.25
            dist=cv2.boxFilter(dist,cv2.CV_32F,(3,3),normalize=True,borderType=cv2.BORDER_REFLECT_101)
            w=np.exp(-np.maximum(dist-2.,0)/(p['h']**2))
            num+=shifted*w[:,:,None];den+=w
    filt=num/den[:,:,None]
    dark=1-smooth(.10,.65,r.max(2)/255)
    y+=(filt[:,:,0]-y)*(p['luma']*dark)
    co+=(filt[:,:,1]-co)*(p['chroma']*dark)
    cg+=(filt[:,:,2]-cg)*(p['chroma']*dark)
    clean=np.stack([y+co-cg,y+cg,y-co-cg],2)
    return np.floor(np.clip(clean*g[:,:,None],0,255)+.5).astype(np.uint8)

def main():
    assert not ROOT.exists()
    ROOT.mkdir();(ROOT/'source').mkdir();(ROOT/'previews').mkdir()
    manifest=read(DATA/'manifest.json')
    key=lambda r:hashlib.sha256(('paper-prenoise-dev-20261031:'+r['name']).encode()).hexdigest()
    low=sorted([r for r in manifest if r['cohort']=='low'],key=key)[:64]
    bright=sorted([r for r in manifest if r['cohort']=='brighter'],key=key)[:16]
    chosen=low+bright;assert len(chosen)==80
    protocol=dict(status='EXPOSED_DEVELOPMENT_SCREEN_NOT_BLIND',hypothesis='Raw-domain chroma/weak-luma patch denoising before paper reflectance gain may avoid amplified chroma noise without removing car edges.',
      variants=VARIANTS,methods=['raw','paper_reference','current_display',*VARIANTS],
      model=str(MODEL),model_sha256=sha(MODEL),
      fixed_detector='Same FP32 checkpoint, same one global400x240 view/preprocess320x320, confidence floor.001,NMS.6,operating confidence.25,IoU.5. No extra crops/refiner, no model training.',
      selection_rule='A candidate passes low64 development only if AP50>=raw+.005,precision>=raw-.005,recall>=raw+.005; brighter16 must exactly bypass to raw predictions. A pass still needs fresh preregistered confirmation and C/board validation.',
      data_scope='All80 taken from previously exposed audit416. No independence or statistical accuracy-gain claim. Existing audit enhancement PNG is the current-display control.',
      manifest_sha256=sha(DATA/'manifest.json'),sources=[r['name'] for r in chosen],
      reference='Independent floating equations2-12, not authors fixed-point RTL.',hardware_access=False,sd_written=False)
    write(ROOT/'protocol.json',protocol)
    for p in [Path(__file__),Path(__file__).with_name('road_retinex_project.py'),Path(__file__).with_name('road_numpy_eval.py')]:shutil.copy2(p,ROOT/'source'/p.name)
    shutil.copy2(BASE/'road_detection_20261026/yolov5/LICENSE',ROOT/'source/YOLOv5_LICENSE')
    # Formula/invariant checks are numerical smoke checks, not quality evidence.
    for value in [0,64,255]:
        a=np.full((240,400,3),value,np.uint8)
        for name in VARIANTS:
            assert np.array_equal(enhance(a,name),a)
    ac.WEIGHTS=MODEL;det=ac.Detector();records={m:[] for m in protocol['methods']};begin=time.monotonic()
    for i,r in enumerate(chosen):
        _,a=ac.sensor400(DATA/'images'/r['name'])
        current=np.asarray(Image.open(AUDIT/'enhanced'/r['name']).convert('RGB'))
        ims={'raw':a,'paper_reference':paper_reference(a)[0],'current_display':current,
             **{name:enhance(a,name) for name in VARIANTS}}
        predictions=det.run(list(ims.values()));gt=ac.truth(DATA/'labels'/(Path(r['name']).stem+'.txt'))
        gt=gt[gt[:,0]==1]
        for (m,_),p in zip(ims.items(),predictions):
            p=np.asarray(p,np.float32).reshape(-1,6);p=p[p[:,5]==1]
            records[m].append(dict(name=r['name'],cohort=r['cohort'],ground_truth=gt.tolist(),detections=p.tolist()))
        if (i+1)%16==0:
            write(ROOT/'progress.json',dict(done=i+1,total=len(chosen),seconds=time.monotonic()-begin))
            print('PAPER_PREDENOISE_DEV',i+1,len(chosen),round(time.monotonic()-begin,1),flush=True)
    scores={cohort:{m:evaluate([r for r in rows if r['cohort']==cohort])['classes']['car'] for m,rows in records.items()} for cohort in ['low','brighter']}
    raw=scores['low']['raw'];gates={}
    for m in VARIANTS:
        s=scores['low'][m]
        same=all(r['detections']==b['detections'] for r,b in zip(records[m],records['raw']) if r['cohort']=='brighter')
        gates[m]=dict(ap=s['ap50']>=raw['ap50']+.005,precision=s['precision']>=raw['precision']-.005,
                      recall=s['recall']>=raw['recall']+.005,bright_exact_bypass=same)
    good=[m for m,g in gates.items() if all(g.values())]
    write(ROOT/'predictions.json',records)
    write(ROOT/'result.json',dict(status='DEVELOPMENT_PASS_REQUIRES_FRESH_CONFIRMATION' if good else 'NO_PREDENOISE_CANDIDATE_PASSED_KEEP_ABI28',
      qualified=good,scores=scores,gates=gates,protocol_sha256=sha(ROOT/'protocol.json'),seconds=time.monotonic()-begin,
      accuracy_scope='Development screen only, no independent improvement evidence',hardware_access=False,sd_written=False))
    # Same three known images as the previous paper comparison. No scene was
    # chosen based on today's detection result.
    prior=BASE/'road_paper_recheck_20261031_r1';meta=read(prior/'protocol.json')
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14);canvas=Image.new('RGB',(1600,840),(18,18,18));d=ImageDraw.Draw(canvas)
    for row,s in enumerate(meta['sources']):
        a=unpack(np.fromfile(s['raw'],'<u4')).reshape(240,400,3)
        current=unpack(np.fromfile(s['current'],'<u4')).reshape(240,400,3)
        panel=[('PAPER REFERENCE',paper_reference(a)[0]),('CURRENT BOARD',current),('PRE CHROMA',enhance(a,'pre_chroma')),('PRE LIGHT',enhance(a,'pre_light'))]
        for col,(label,img) in enumerate(panel):
            Image.fromarray(img).save(ROOT/'previews'/f'{row}_{col}.png')
            canvas.paste(Image.fromarray(img),(col*400,row*280+40))
            d.text((col*400+4,row*280+3),s['name']+' / '+label,font=font,fill='white')
            d.text((col*400+4,row*280+21),f'Mean Y {mean_y(img):.2f}; brightness only',font=font,fill='white')
    canvas.save(ROOT/'comparison.png')
    print('PAPER_PREDENOISE_DONE',json.dumps(dict(scores=scores['low'],gates=gates,qualified=good)),flush=True)

if __name__=='__main__':main()
