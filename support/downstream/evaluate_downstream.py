"""Frozen-classifier downstream test with a predeclared synthetic-light grid.

Not a real low-light camera benchmark, and alpha is NOT measured illuminance.
All methods receive the identical noisy RGB565 input. No examples are removed.
"""
from pathlib import Path
import importlib.util
import json
import sys
import time
import numpy as np
from PIL import Image,ImageDraw
import torch
from digit_model import ROOT,IntegerDigit
from prepare_digit_hls import sample

STARTER=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(STARTER/'nn'))
from nanodce_fixed import FixedNanoDCE
from nanodce_reference import load_float_state
spec=importlib.util.spec_from_file_location('fixed8_reference',Path('E:/FPGA_Enhance_Work/model_upgrade_20261023/hls8/fixed8.py'))
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)


def main():
    state=torch.load(ROOT/'digit_model.pth',map_location='cpu',weights_only=True)
    q=IntegerDigit(state)
    old=FixedNanoDCE(load_float_state(Path('E:/FPGA_Enhance_Work/github_audit_20261017/selected/NanoDCE/models/snapshots_student_enhanced_kd/Student_Epoch100.pth')))
    ns=torch.load('E:/FPGA_Enhance_Work/model_upgrade_20261023/student8/best_student8.pth',map_location='cpu',weights_only=True)
    new=mod.FixedNanoDCE({k:v.numpy() for k,v in ns.items()})
    ds=np.load(ROOT/'downstream_test_inputs.npz')
    g=np.random.default_rng(2026102304)
    images=list(ds['images']);labels=list(map(int,ds['labels']));sources=list(map(str,ds['sources']))
    for i in range(20):
        images.append(np.clip(g.normal(i%5,2,(28,28)),0,255).astype(np.uint8));labels.append(10);sources.append('blank')
    levels=[1.0,0.5,0.25,0.125,0.0625,0.03125]
    dest=ROOT/'downstream_evaluation';dest.mkdir(exist_ok=True)
    records=[];start=time.time()
    for i,(image,label,source) in enumerate(zip(images,labels,sources)):
        clean=np.array(Image.fromarray(image).resize((224,224),Image.Resampling.LANCZOS))
        for alpha in levels:
            # Identical fixed noise realization at a given sample/light condition.
            roi=np.clip(np.floor(clean[:,:,None]*alpha+g.normal(0,1,(224,224,3))+0.5),0,255).astype(np.uint8)
            roi[:,:,0]&=248;roi[:,:,1]&=252;roi[:,:,2]&=248
            x=np.full((240,256,3),16,np.uint8);x[8:232,16:240]=roi
            variants={'raw':x,'gamma05':np.floor(np.sqrt(x.astype(float)/255)*255+0.5).astype(np.uint8),
                      'old_nn':old.infer(x)[0],'new_nn':new.infer(x)[0]}
            row=dict(index=i,label=label,source=source,alpha=alpha,predictions={})
            for name,out in variants.items():
                pred,logit=q.infer(sample(out,16,8));order=np.sort(logit[0])
                row['predictions'][name]=dict(label=int(pred[0]),correct=int(pred[0])==label,top2_logit_margin_q20=int(order[-1]-order[-2]))
            records.append(row)
            # Predeclared example indices; neither successes nor failures selected post hoc.
            if i in (0,5,11,44,100) and alpha in (0.25,0.0625):
                sheet=Image.new('RGB',(4*224,256),'white');d=ImageDraw.Draw(sheet)
                for j,(name,out) in enumerate(variants.items()):
                    sheet.paste(Image.fromarray(out[8:232,16:240]),(j*224,32))
                    d.text((j*224+4,4),f'{name}: {row["predictions"][name]["label"]} / GT {label}',fill='black')
                sheet.save(dest/f'example_{i}_a{alpha}.png')
        if i%10==0:print('DOWNSTREAM_SAMPLE',i,'of',len(images),'seconds',round(time.time()-start,1),flush=True)
    summary=[]
    for alpha in levels:
        digit=[r for r in records if r['alpha']==alpha and r['label']<10]
        blank=[r for r in records if r['alpha']==alpha and r['label']==10]
        entry=dict(alpha=alpha,n_digits=len(digit),n_blank=len(blank),methods={})
        for method in ('raw','gamma05','old_nn','new_nn'):
            entry['methods'][method]=dict(correct=sum(r['predictions'][method]['correct'] for r in digit),
                accuracy=float(np.mean([r['predictions'][method]['correct'] for r in digit])),
                blank_false_positive_rate=float(np.mean([r['predictions'][method]['label']<10 for r in blank])))
        summary.append(entry)
    report=dict(status='COMPLETE',recognizer_sha256=__import__('hashlib').sha256((ROOT/'digit_model.pth').read_bytes()).hexdigest(),
        protocol='160 fixed clean digit examples (120 unseen-font + 40 MNIST-test) plus 20 blank controls; alpha grid predefined; additive Gaussian 1 RGB count; RGB565 truncation before all variants; same frozen Q12 classifier; 224x224 ROI with 8x8 luma pooling to28x28',
        limitations=['Synthetic multiplicative darkening in encoded RGB is not calibrated physical exposure or lux.',
                     'This tests single centered digits, not license-plate detection or full text.',
                     'Confidence margin is not probability or accuracy.',
                     'Gamma is an explicit baseline; enhancement benefit is not guaranteed and all failures are retained.',
                     'Real OV5640 fixed-exposure scenes, end-to-end timing, and hardware validation remain pending.'],
        summary=summary,records=records)
    (dest/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('DOWNSTREAM_EVALUATION_COMPLETE',json.dumps(summary),flush=True)


if __name__=='__main__':main()
