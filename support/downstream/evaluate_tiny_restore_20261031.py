"""Four frozen students;development screen and declared quality fallback."""
import shutil,time
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from road_tiny_restore_common import *
from road_retinex_project import illumination
from shadowlift_lab import unpack,mean_y,Baseline
from shadowlift_refine import final_display
import road_accuracy_common as ac
from road_numpy_eval import evaluate

def infer(net,a,torch):
    x=torch.from_numpy(np.ascontiguousarray(a.transpose(2,0,1))).cuda().float().unsqueeze(0)/255
    f=torch.from_numpy(illumination(a)).cuda()[None,None]
    with torch.inference_mode():z=net(x,f)[0].permute(1,2,0).cpu().numpy()
    return np.floor(z*255+.5).astype(np.uint8)

def main():
    import torch
    assert (ROOT/'training_complete.json').exists() and not (ROOT/'selected.json').exists()
    out=ROOT/'development';out.mkdir();shutil.copy2(__file__,ROOT/'source'/Path(__file__).name)
    ac.WEIGHTS=DETECTOR;det=ac.Detector()
    names=['distill4','distill8','joint4','joint8'];nets={};frozen={}
    for name in names:
        folder=ROOT/'frozen'/name;meta=read(folder/'frozen.json');assert sha(folder/'model.pt')==meta['sha256']
        net=make_model().cuda().eval();net.load_state_dict(torch.load(folder/'model.pt',map_location='cpu',weights_only=True));nets[name]=net;frozen[name]=meta
    old=read(BASE/'road_paper_predenoise_20261031_r1/predictions.json')['raw'];data=BASE/'road_brightness_route_20261030_r1/fresh'
    records={m:[] for m in ['raw',*names]};begin=time.monotonic()
    for i,r in enumerate(old):
        _,a=ac.sensor400(data/'images'/r['name']);ims={'raw':a,**{m:infer(net,a,torch) for m,net in nets.items()}}
        pp=det.run(list(ims.values()))
        for (m,img),pred in zip(ims.items(),pp):
            p=np.asarray(pred,np.float32).reshape(-1,6);p=p[p[:,5]==1]
            records[m].append(dict(name=r['name'],cohort=r['cohort'],ground_truth=r['ground_truth'],detections=p.tolist()))
            if r['cohort']=='brighter':
                assert np.array_equal(a,img)
                assert records[m][-1]['detections']==records['raw'][-1]['detections']
        assert np.allclose(np.asarray(records['raw'][-1]['detections']).reshape(-1,6),np.asarray(r['detections']).reshape(-1,6),rtol=0,atol=.001)
        if (i+1)%16==0:print('TINY_RESTORE_DEV',i+1,len(old),round(time.monotonic()-begin,1),flush=True)
    scores={m:evaluate([r for r in rows if r['cohort']=='low'])['classes']['car'] for m,rows in records.items()}
    baseline=scores['raw'];gates={m:dict(ap=scores[m]['ap50']>=baseline['ap50']+.005,precision=scores[m]['precision']>=baseline['precision']-.005,recall=scores[m]['recall']>=baseline['recall']+.005,bright_bypass=True) for m in names}
    good=[m for m in names if all(gates[m].values())]
    chosen=max(good,key=lambda m:scores[m]['ap50']) if good else min(names,key=lambda m:frozen[m]['internal_val_l1'])
    selection=dict(status='DETECTION_DEVELOPMENT_PASS_NEEDS_UNUSED_CONFIRMATION' if good else 'DISPLAY_ONLY_FALLBACK_RAW_DETECTION_UNCHANGED',chosen=chosen,detection_qualified=bool(good),
      selection_rule='Highest developmentAP among all-gates pass;else minimum internal_val teacherL1 as preregistered,not selection by developmentAP.',
      frozen=frozen[chosen],scores=scores,gates=gates,protocol_sha256=sha(ROOT/'protocol.json'),hardware_access=False,sd_written=False)
    write(out/'predictions.json',records);write(ROOT/'selected.json',selection)
    print('TINY_RESTORE_SELECTED',chosen,'detection_qualified',bool(good),'scores',scores,flush=True)
    sources=read(BASE/'road_paper_recheck_20261031_r1/protocol.json')['sources']
    canvas=Image.new('RGB',(1600,840),(15,15,15));font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14);d=ImageDraw.Draw(canvas);(out/'known').mkdir()
    for row,s in enumerate(sources):
        a=unpack(np.fromfile(s['raw'],'<u4')).reshape(240,400,3);cur=unpack(np.fromfile(s['current'],'<u4')).reshape(240,400,3);z=infer(nets[chosen],a,torch)
        teacher=np.asarray(Image.open(BASE/f'retinexformer_reference_20261031_r1/evaluation/known_photos/{row}.png'))
        Image.fromarray(z).save(out/'known'/f'{row}.png')
        for col,(tag,img) in enumerate([('RAW',a),('CURRENT BOARD',cur),('TINY RESTORE '+chosen,z),('PC TEACHER',teacher)]):
            canvas.paste(Image.fromarray(img),(col*400,row*280+40));d.text((col*400+4,row*280+3),s['name']+' / '+tag,font=font,fill='white');d.text((col*400+4,row*280+21),f'MeanY {mean_y(img):.1f}; brightness only',font=font,fill='white')
    canvas.save(out/'quality_comparison.png')
    from study_road_local_enhance_v2 import metric,resize400,rgb
    paired=[];engine=Baseline()
    for path in sorted((BASE/'enhancement_study_20261025/data/Low').glob('*.png')):
        raw=resize400(rgb(path));normal=resize400(rgb(path.parent.parent/'Normal'/path.name.replace('low','normal')))
        z=infer(nets[chosen],raw,torch);cur=final_display(raw,engine.run(raw))[0]
        for method,img in [('raw',raw),('current',cur),('tiny',z)]:paired.append(dict(name=path.name,method=method,**metric(img,normal)))
    summary={m:{k:float(np.mean([r[k] for r in paired if r['method']==m])) for k in ['psnr','ssim']} for m in ['raw','current','tiny']}
    quality_ok=summary['tiny']['psnr']>summary['current']['psnr'] and summary['tiny']['ssim']>summary['current']['ssim']
    write(out/'paired_diagnostic.json',dict(images=20,unique_reference_groups=8,not_blind=True,summary=summary,rows=paired,improves_both_diagnostic_metrics=quality_ok))
    print('TINY_RESTORE_PAIRED',summary,'quality_pass',quality_ok,flush=True)
    write(out/'complete.json',dict(status='DEVELOPMENT_SCREEN_COMPLETE',quality_pass=quality_ok,detection_qualified=bool(good),chosen=chosen,hardware_access=False,sd_written=False))
if __name__=='__main__':main()
