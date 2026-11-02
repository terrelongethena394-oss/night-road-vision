"""New immutable-input regression for new classifier; normal and synthetic dim."""
from pathlib import Path
import hashlib,importlib.util,json,shutil
import numpy as np
from PIL import Image
import torch
from train_real_digit_cnn import OUT,REAL,IntegerCNN
from prepare_digit_hls import sample
from prepare_fixed_cases import fnv1a

ROOT=Path('E:/FPGA_Enhance_Work/real_cnn_image_test_20261025')
FIXED=Path('E:/FPGA_Enhance_Work/fixed_image_test_20261025')
UPGRADE=Path('E:/FPGA_Enhance_Work/model_upgrade_20261023')

def pooled(roi):
    v=roi.astype(np.int64);gray=(77*v[:,:,0]+150*v[:,:,1]+29*v[:,:,2]+128)>>8
    return ((gray.reshape(28,8,28,8).sum((1,3))+32)>>6).astype(np.uint8)

def main():
    ROOT.mkdir(exist_ok=True)
    assert not (ROOT/'case_manifest.json').exists(),'Preserve already prepared inputs'
    for folder in ('inputs','pc_roi_references','board'): (ROOT/folder).mkdir(exist_ok=True)
    q=IntegerCNN(torch.load(OUT/'real_digit_cnn.pth',weights_only=True,map_location='cpu'))
    spec=importlib.util.spec_from_file_location('fixed8',UPGRADE/'hls8/fixed8.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    s=torch.load(UPGRADE/'student8/best_student8.pth',weights_only=True,map_location='cpu')
    enhance=mod.FixedNanoDCE({k:v.numpy() for k,v in s.items()})
    real=json.loads((REAL/'case_manifest.json').read_text(encoding='utf-8'))['cases']
    controls=json.loads((FIXED/'case_manifest.json').read_text())['cases'][:3]
    jobs=[(FIXED,c,False) for c in controls]+[(REAL,c,False) for c in real]+[(REAL,c,True) for c in real if c['id'].startswith('svhn_')]
    records=[]
    for i,(base,c,dim) in enumerate(jobs):
        rgb=np.array(Image.open(base/'inputs'/(c['id']+'.png')).convert('RGB'))
        name=c['id']+('_dim8' if dim else '')
        if dim:rgb=np.floor(rgb.astype(np.float64)*.125+.5).astype(np.uint8)
        # Radius three: sufficient context for the three local conv blocks.
        surround=rgb[109:339,477:707]
        eroi=enhance.infer(surround)[0][3:227,3:227]
        if not dim:
            original=np.array(Image.open(base/'pc_reference_previews'/(c['id']+'_PC_REFERENCE.png')).convert('RGB'))[112:336,480:704]
            assert np.array_equal(eroi,original),(name,'local/full-frame NN8 mismatch')
        payload=np.ascontiguousarray(rgb[:,:,::-1]).tobytes()
        path=ROOT/'inputs'/(name+'.bgr888');path.write_bytes(payload)
        Image.fromarray(rgb).save(ROOT/'inputs'/(name+'.png'))
        Image.fromarray(eroi).save(ROOT/'pc_roi_references'/(name+'_PC_ENH_ROI.png'))
        row=dict(id=name,truth=c['truth'],group='synthetic_dim_from_SVHN' if dim else c['group'],
            alpha=.125 if dim else c.get('alpha',1.0),artificially_darkened=dim or c.get('alpha',1.)<1,
            file=path.as_posix(),fnv=fnv1a(payload),sha256=hashlib.sha256(payload).hexdigest(),bytes=len(payload))
        for key,gray in [('raw',sample(rgb,480,112)),('enh',pooled(eroi))]:
            p,logits=q.infer(gray);ordered=np.sort(logits[0]);row[key+'_expected']=int(p[0]);row[key+'_margin']=min(int(ordered[-1]-ordered[-2]),2147483647)
        records.append(row)
        if (i+1)%10==0:print('REAL_CNN_TEST_INPUTS',i+1,len(jobs),flush=True)
    assert len(records)==66
    manifest=dict(status='PREPARED_NO_HARDWARE_WRITE',selection='Original first-three-per-class 30 SVHN + 3 original manually cropped photos; same 30 SVHN at RGB*1/8; 3 diagnostics. No outcome selection.',
        digit_sha256=hashlib.sha256((OUT/'real_digit_cnn.pth').read_bytes()).hexdigest(),
        enhancer_sha256=hashlib.sha256((UPGRADE/'student8/best_student8.pth').read_bytes()).hexdigest(),
        limitations='Given digit ROI; dim data are synthetic, not measured lux/night capture. PC ROI previews are not FPGA readback.',cases=records)
    (ROOT/'case_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['set image_cases [list \\']
    for r in records:
        parts=[]
        for k in ['id','file','truth','fnv','raw_expected','enh_expected','raw_margin','enh_margin']:parts.extend([k,'{'+str(r[k])+'}'])
        lines.append('    [dict create '+' '.join(parts)+'] \\')
    lines.append(']');(ROOT/'cases.tcl').write_text('\n'.join(lines)+'\n',encoding='ascii')
    for file in ('image_test.elf','run_fixed_image.tcl','start_fixed_image.tcl'):shutil.copy2(FIXED/file,ROOT/file)
    shutil.copy2(REAL/'original_photos/sources.json',ROOT/'photo_sources_and_attribution.json')
    print('REAL_CNN_66_TEST_INPUTS_READY_NO_DOWNLOAD',flush=True)

if __name__=='__main__':main()
