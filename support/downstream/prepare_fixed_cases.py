"""Predeclare fixed hardware inputs and independent integer-reference results."""
from pathlib import Path
import hashlib,importlib.util,json,sys,time
import numpy as np
from PIL import Image
import torch
from digit_model import IntegerDigit
from prepare_digit_hls import sample

ROOT=Path('E:/FPGA_Enhance_Work/fixed_image_test_20261025')
MODELS=Path('E:/FPGA_Enhance_Work/digit_recognition_20261023')
UPGRADE=Path('E:/FPGA_Enhance_Work/model_upgrade_20261023')

def fnv1a(data):
    value=2166136261
    for b in data:value=((value^b)*16777619)&0xffffffff
    return value

def main():
    spec=importlib.util.spec_from_file_location('fixed8_reference',UPGRADE/'hls8/fixed8.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    state=torch.load(UPGRADE/'student8/best_student8.pth',map_location='cpu',weights_only=True)
    enhance=mod.FixedNanoDCE({k:v.numpy() for k,v in state.items()})
    digit=IntegerDigit(torch.load(MODELS/'digit_model.pth',map_location='cpu',weights_only=True))
    ds=np.load(MODELS/'downstream_test_inputs.npz')
    cases=[]
    color=np.zeros((480,400,3),np.uint8)
    for i,c in enumerate([(255,0,0),(0,255,0),(0,0,255),(255,255,255),(32,32,32)]):color[:,i*80:(i+1)*80]=c
    cases.append(dict(id='color_order_control',tile=color,truth=-1,group='color_control',alpha=1.0))
    def digit_case(name,image,truth,alpha,group,seed):
        gray=np.array(Image.fromarray(image).resize((224,224),Image.Resampling.LANCZOS))
        noise=np.random.default_rng(seed).normal(0,1,(224,224,3))
        roi=np.clip(np.floor(gray[:,:,None]*alpha+noise+0.5),0,255).astype(np.uint8)
        tile=np.full((480,400,3),16,np.uint8);tile[112:336,80:304]=roi
        cases.append(dict(id=name,tile=tile,truth=truth,alpha=alpha,group=group))
    demo=np.array(Image.open(MODELS/'demo_targets/digit_8.png').convert('L'))
    digit_case('demo8_normal',demo,8,1.0,'demo_control',2026102500)
    digit_case('demo8_dim',demo,8,0.125,'demo_control',2026102501)
    for level,alpha in [('normal',1.0),('dim1_8',0.125),('dim1_16',0.0625)]:
        for label in range(10):
            idx=int(np.flatnonzero(ds['labels']==label)[0])
            digit_case(f'digit{label}_{level}',ds['images'][idx],label,alpha,'heldout_font_digits',2026102510+label)
        digit_case('blank_'+level,np.zeros((28,28),np.uint8),10,alpha,'blank_control',2026102599)
    # Existing LOL exploration inputs; not independent generalization data.
    photos=sorted((UPGRADE/'dataset/eval15/low').glob('*.png'))[:2]
    assert len(photos)==2
    for photo in photos:
        im=Image.open(photo).convert('RGB');im.thumbnail((400,480),Image.Resampling.LANCZOS)
        tile=np.full((480,400,3),16,np.uint8)
        tile[(480-im.height)//2:(480-im.height)//2+im.height,(400-im.width)//2:(400-im.width)//2+im.width]=np.array(im)
        cases.append(dict(id='natural_'+photo.stem,tile=tile,truth=-1,alpha=None,group='natural_visual_only',source=str(photo)))
    assert len(cases)==38
    inputs=ROOT/'inputs';inputs.mkdir(exist_ok=True)
    previews=ROOT/'pc_reference_previews';previews.mkdir(exist_ok=True)
    records=[];start=time.time()
    for index,case in enumerate(cases):
        tile=case.pop('tile')
        rgb=np.concatenate([tile,tile],axis=1)
        # Match RGB565 camera precision; low bits stay zero, as in original RTL.
        rgb[:,:,0]&=248;rgb[:,:,1]&=252;rgb[:,:,2]&=248
        bgr=np.ascontiguousarray(rgb[:,:,::-1]).tobytes()
        path=inputs/(case['id']+'.bgr888');path.write_bytes(bgr)
        output=enhance.infer(rgb)[0]
        # Existing mode 1 passes the left half through and enhances the right half.
        output[:,:400]=rgb[:,:400]
        result=dict(case,index=index,file=path.as_posix(),bytes=len(bgr),fnv=fnv1a(bgr),sha256=hashlib.sha256(bgr).hexdigest())
        for key,image in [('raw',rgb),('enh',output)]:
            prediction,logit=digit.infer(sample(image,480,112));scores=np.sort(logit[0])
            result[key+'_expected']=int(prediction[0])
            result[key+'_margin']=min(int(scores[-1]-scores[-2]),2147483647)
        Image.fromarray(rgb).save(inputs/(case['id']+'.png'))
        Image.fromarray(output).save(previews/(case['id']+'_PC_REFERENCE.png'))
        records.append(result)
        print('FIXED_CASE_READY',case['id'],'raw',result['raw_expected'],'enh',result['enh_expected'],'seconds',round(time.time()-start,1),flush=True)
    (ROOT/'case_manifest.json').write_text(json.dumps(dict(protocol='Same frozen FPGA weights; two identical image halves; right ROI x480 y112 224x224; synthetic alpha not lux; RGB565 precision; no cherry-picking.',
        enhancer_checkpoint_sha256=hashlib.sha256((UPGRADE/'student8/best_student8.pth').read_bytes()).hexdigest(),
        digit_checkpoint_sha256=hashlib.sha256((MODELS/'digit_model.pth').read_bytes()).hexdigest(),cases=records),indent=2),encoding='utf-8')
    lines=['set image_cases [list \\']
    for row in records:
        fields=[]
        for name in ['id','file','truth','fnv','raw_expected','enh_expected','raw_margin','enh_margin']:
            fields.extend([name,'{'+str(row[name])+'}'])
        lines.append('    [dict create '+' '.join(fields)+'] \\')
    lines.append(']')
    (ROOT/'cases.tcl').write_text('\n'.join(lines)+'\n',encoding='ascii')
    print('FIXED_IMAGE_38_CASES_READY',flush=True)

if __name__=='__main__':main()
