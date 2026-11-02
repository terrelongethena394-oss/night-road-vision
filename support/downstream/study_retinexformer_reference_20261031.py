"""PC quality reference, fixed known-data detection screen, no GT mean adjustment."""
from pathlib import Path
import shutil,time,json
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from retinexformer_reference_runtime import ROOT,Reference
from shadowlift_lab import read,write,unpack,mean_y,Baseline
from shadowlift_refine import final_display
from road_retinex_project import paper_reference
from road_numpy_eval import evaluate
import road_accuracy_common as ac

def main():
    out=ROOT/'evaluation';assert not out.exists();out.mkdir();(out/'source').mkdir();(out/'enhanced80').mkdir();(out/'known_photos').mkdir()
    prior=Path('E:/FPGA_Enhance_Work/road_paper_predenoise_20261031_r1')
    p=read(prior/'protocol.json');images=ac.BASE/'road_brightness_route_20261030_r1/fresh/images'
    write(out/'protocol.json',dict(status='EXPOSED_DEVELOPMENT_PC_REFERENCE',model='Original LOL_v1 pretrained Retinexformer,stage1,n_feat40,num_blocks1,2,2;FP32.',
      inference='400x240 RGB/255,no augmentation,no GT mean,no reference-exposure information,no self ensemble.',
      detection='Exactly same80 exposed images/model/global view/thresholds as paper predenoise screen;low64 screen only,not independent confirmation.',
      paired='Existing20 low/normal pairs,previously exposed and only8 unique reference groups;diagnostic quality regression,not paper benchmark reproduction or blind evidence.',
      deployability='PC-only reference,not FPGA or ARM implementation.',hardware_access=False,sd_written=False))
    for name in ['retinexformer_reference_runtime.py','study_retinexformer_reference_20261031.py']:
        shutil.copy2(Path(__file__).with_name(name),out/'source'/name)
    ref=Reference();font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14)
    sources=read(ac.BASE/'road_paper_recheck_20261031_r1/protocol.json')['sources']
    canvas=Image.new('RGB',(1600,840),(15,15,15));d=ImageDraw.Draw(canvas);known=[]
    for row,s in enumerate(sources):
        raw=unpack(np.fromfile(s['raw'],'<u4')).reshape(240,400,3);cur=unpack(np.fromfile(s['current'],'<u4')).reshape(240,400,3)
        z=ref.run(raw);Image.fromarray(z).save(out/'known_photos'/f'{row}.png')
        for col,(tag,img) in enumerate([('RAW',raw),('PAPER FLOAT',paper_reference(raw)[0]),('CURRENT BOARD',cur),('RETINEXFORMER PC',z)]):
            canvas.paste(Image.fromarray(img),(col*400,row*280+40));d.text((col*400+4,row*280+4),s['name']+' '+tag,font=font,fill='white')
        known.append(dict(name=s['name'],raw_mean=mean_y(raw),current_mean=mean_y(cur),reference_mean=mean_y(z)))
    canvas.save(out/'quality_comparison.png');write(out/'known_photos.json',known)
    print('RETINEXFORMER_KNOWN_PREVIEW_READY',known,flush=True)
    rows=read(prior/'predictions.json')['raw'];ac.WEIGHTS=ac.BASE/'road_viewadapt_20261030_r1/export/model.pt';det=ac.Detector();pred=[];begin=time.monotonic()
    for at,r in enumerate(rows):
        _,a=ac.sensor400(images/r['name']);z=ref.run(a)
        Image.fromarray(z).save(out/'enhanced80'/r['name'].replace('.jpg','.png'))
        pp=np.asarray(det.run([z])[0],np.float32).reshape(-1,6);pp=pp[pp[:,5]==1]
        pred.append(dict(name=r['name'],cohort=r['cohort'],ground_truth=r['ground_truth'],detections=pp.tolist()))
        if (at+1)%16==0:print('RETINEXFORMER_DEV',at+1,len(rows),round(time.monotonic()-begin,1),flush=True)
    write(out/'predictions.json',pred)
    scores={c:evaluate([r for r in pred if r['cohort']==c])['classes']['car'] for c in ['low','brighter']}
    write(out/'detection_result.json',dict(scores=scores,known_photos=known,parameters=ref.parameters,hardware_access=False,sd_written=False,scope='PC reference,exposed80/global-only,not board accuracy or new independent proof'))
    print('RETINEXFORMER_DEV_RESULT',scores,flush=True)
    # Paired data are read only after outputs are generated, never to adjust
    # the reference brightness or network output.
    from study_road_local_enhance_v2 import metric,resize400,rgb
    paired=[];engine=Baseline()
    for path in sorted((ac.BASE/'enhancement_study_20261025/data/Low').glob('*.png')):
        target=path.parent.parent/'Normal'/path.name.replace('low','normal')
        raw=resize400(rgb(path));normal=resize400(rgb(target));z=ref.run(raw);current=final_display(raw,engine.run(raw))[0]
        for method,img in [('raw',raw),('paper',paper_reference(raw)[0]),('current',current),('retinexformer',z)]:
            paired.append(dict(name=path.name,method=method,**metric(img,normal)))
    summary={m:{k:float(np.mean([r[k] for r in paired if r['method']==m])) for k in ['psnr','ssim']} for m in ['raw','paper','current','retinexformer']}
    write(out/'paired_diagnostic.json',dict(images=20,summary=summary,rows=paired,not_blind=True,normal_reference_mean_used_for_inference=False))
    print('RETINEXFORMER_PAIRED_DIAGNOSTIC',summary,flush=True)
    write(out/'complete.json',dict(status='PC_REFERENCE_COMPLETE',hardware_access=False,sd_written=False))
if __name__=='__main__':main()
