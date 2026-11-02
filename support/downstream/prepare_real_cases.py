"""Use downloaded photographs, with fixed selections/ROIs before inference."""
from pathlib import Path
import hashlib,importlib.util,json,shutil
import numpy as np
from PIL import Image,ImageDraw
from scipy.io import loadmat
import torch
from digit_model import IntegerDigit
from prepare_digit_hls import sample
from prepare_fixed_cases import fnv1a

ROOT=Path('E:/FPGA_Enhance_Work/real_scene_test_scaled_20261025')
DATA=Path('E:/FPGA_Enhance_Work/real_scene_test_20261025')
BASE=Path('E:/FPGA_Enhance_Work/fixed_image_test_20261025')
MODELS=Path('E:/FPGA_Enhance_Work/digit_recognition_20261023')
UPGRADE=Path('E:/FPGA_Enhance_Work/model_upgrade_20261023')

def fit_roi(image):
    scale=min(224/image.width,224/image.height)
    image=image.resize((max(1,round(image.width*scale)),max(1,round(image.height*scale))),Image.Resampling.LANCZOS)
    median=tuple(np.median(np.array(image).reshape(-1,3),axis=0).astype(np.uint8))
    roi=Image.new('RGB',(224,224),median)
    roi.paste(image,((224-image.width)//2,(224-image.height)//2))
    return np.array(roi)

def main():
    ROOT.mkdir(exist_ok=True)
    assert not (ROOT/'case_manifest.json').exists(),'Preserve a prepared real-image test'
    raw=(DATA/'test_32x32.mat').read_bytes()
    assert hashlib.md5(raw).hexdigest()=='eb5a983be6a315427106f1b164d9cef3'
    data=loadmat(DATA/'test_32x32.mat')
    x=data['X'].transpose(3,0,1,2);y=data['y'].reshape(-1)%10
    assert x.shape==(26032,32,32,3)
    selected=[]
    # First three test images of each class, without looking at predictions.
    for label in range(10):
        for index in np.flatnonzero(y==label)[:3]:
            selected.append(dict(id=f'svhn_{int(index):05d}',truth=label,group='SVHN_first3_per_class',
                dataset_index=int(index),native_size=[32,32],roi=fit_roi(Image.fromarray(x[index])),
                source='http://ufldl.stanford.edu/housenumbers/',manually_cropped=False))
    sources=json.loads((DATA/'original_photos/sources.json').read_text(encoding='utf-8'))
    assert len(sources)==3
    # Approximate numeral boxes, annotated from source photos before inference.
    boxes=[(.10,.12,.95,.90),(.43,.145,.565,.285),(.43,.37,.53,.63)]
    labels=[8,5,8]
    for i,(source,box,label) in enumerate(zip(sources,boxes,labels)):
        im=Image.open(source['file']).convert('RGB');w,h=im.size
        cx=(box[0]+box[2])*w/2;cy=(box[1]+box[3])*h/2
        side=max((box[2]-box[0])*w,(box[3]-box[1])*h)*2.2
        crop=[max(0,int(cx-side/2)),max(0,int(cy-side/2)),min(w,int(cx+side/2)),min(h,int(cy+side/2))]
        selected.append(dict(id=f'commons_{i}_roi',truth=label,group='real_photo_manual_roi',
            source=source['page'],author=source['metadata'].get('Artist',{}).get('value',''),
            license=source['metadata'].get('LicenseShortName',{}).get('value','See source page'),
            original_file=source['file'],crop_xyxy=crop,native_size=list(im.size),
            roi=fit_roi(im.crop(crop)),manually_cropped=True))
    assert len(selected)==33
    spec=importlib.util.spec_from_file_location('fixed8',UPGRADE/'hls8/fixed8.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    s=torch.load(UPGRADE/'student8/best_student8.pth',map_location='cpu',weights_only=True)
    enhance=mod.FixedNanoDCE({k:v.numpy() for k,v in s.items()})
    digit=IntegerDigit(torch.load(MODELS/'digit_model.pth',map_location='cpu',weights_only=True))
    (ROOT/'inputs').mkdir(exist_ok=True);(ROOT/'pc_reference_previews').mkdir(exist_ok=True)
    sheet=Image.new('RGB',(6*144,6*170),'white');draw=ImageDraw.Draw(sheet)
    records=[]
    for i,c in enumerate(selected):
        roi=c.pop('roi');tile=np.full((480,400,3),16,np.uint8);tile[112:336,80:304]=roi
        rgb=np.concatenate([tile,tile],axis=1)
        # Format conversion only; no inversion, threshold, denoising or darkening.
        rgb[:,:,0]&=248;rgb[:,:,1]&=252;rgb[:,:,2]&=248
        file=ROOT/'inputs'/(c['id']+'.bgr888');b=np.ascontiguousarray(rgb[:,:,::-1]).tobytes();file.write_bytes(b)
        output=enhance.infer(rgb)[0];output[:,:400]=rgb[:,:400]
        record=dict(c,index=i,file=file.as_posix(),bytes=len(b),fnv=fnv1a(b),sha256=hashlib.sha256(b).hexdigest(),artificially_darkened=False)
        for key,image in [('raw',rgb),('enh',output)]:
            pred,logit=digit.infer(sample(image,480,112));order=np.sort(logit[0])
            record[key+'_expected']=int(pred[0]);record[key+'_margin']=min(int(order[-1]-order[-2]),2147483647)
        Image.fromarray(rgb).save(ROOT/'inputs'/(c['id']+'.png'))
        Image.fromarray(output).save(ROOT/'pc_reference_previews'/(c['id']+'_PC_REFERENCE.png'))
        ox=(i%6)*144;oy=(i//6)*170
        sheet.paste(Image.fromarray(roi).resize((136,136),Image.Resampling.NEAREST),(ox+4,oy+4))
        draw.text((ox+4,oy+143),c['id'],fill='black');draw.text((ox+4,oy+156),'GT: '+str(c['truth']),fill='black')
        records.append(record)
        print('REAL_CASE_READY',c['id'],'truth',c['truth'],'raw',record['raw_expected'],'enh',record['enh_expected'],flush=True)
    sheet.save(ROOT/'真实照片预览.png')
    manifest=dict(dataset='Original SVHN test photographs + 3 Wikimedia photographs',
        selection='First three SVHN test indices per digit, no performance selection. Three source-photo ROIs annotated before inference.',
        preprocessing='LANCZOS resize/letterbox, paired identical halves and RGB565 truncation only; original color/background retained. No synthetic darkening.',
        limitations='SVHN is pre-cropped 32x32; Wikimedia ROIs are manual. This does not test full-scene detection or automatic plate OCR.',cases=records)
    (ROOT/'case_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['set image_cases [list \\']
    for r in records:
        parts=[]
        for k in ['id','file','truth','fnv','raw_expected','enh_expected','raw_margin','enh_margin']:parts.extend([k,'{'+str(r[k])+'}'])
        lines.append('    [dict create '+' '.join(parts)+'] \\')
    lines.append(']');(ROOT/'cases.tcl').write_text('\n'.join(lines)+'\n',encoding='ascii')
    for name in ['image_test.elf','run_fixed_image.tcl','start_fixed_image.tcl']:shutil.copy2(BASE/name,ROOT/name)
    shutil.copytree(BASE/'board',ROOT/'board',dirs_exist_ok=True)
    print('REAL_33_CASES_PREPARED_NO_MODEL_OR_WEIGHT_CHANGE',flush=True)

if __name__=='__main__':main()
