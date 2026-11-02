"""Freeze full-context source-photo tests, no outcome-based scene selection."""
from pathlib import Path
import json,hashlib,math,shutil
import numpy as np
from PIL import Image,ImageOps
ROOT=Path('E:/FPGA_Enhance_Work/multinex_camera_digit_20261026')
BASE=ROOT.parent
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def fnv(b):
    h=2166136261
    for c in b:h=((h^c)*16777619)&0xffffffff
    return h
def main():
    assert not (ROOT/'digit_cases.json').exists()
    manifest=json.loads((BASE/'real_scene_test_20261025/case_manifest.json').read_text(encoding='utf-8'))
    photos=[c for c in manifest['cases'] if c['id'].startswith('commons')]
    assert len(photos)==3
    protocol=dict(status='FROZEN_BEFORE_NEW_CLASSIFICATION_INFERENCE',sources=photos,
        scales=[1.0,.25,.125],controls=['black','white','gray40','seeded_random'],
        preprocessing='Entire original photo letterboxed to800x480, RGB565 zero expansion,2x2 mean400x240. Existing manual numeral ROI mapped to canvas and rounded to28-multiple square. No digit pasted on a new background; black letterbox may be present.',
        caveats='Three previously seen source photos, nine brightness variants are not9independent scenes. Artificial brightness multipliers are not physical low light. Manual ROI, no automatic detection or plate OCR. Functional/regression tests; not unbiased generalization evidence.',
        model_sha256='07478560652fdd4c73e6347f8494cdceecd90cda3f62d8705cbb229babc32493')
    (ROOT/'digit_photo_protocol.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2),encoding='utf-8')
    inputs=ROOT/'digit_inputs';inputs.mkdir(exist_ok=True);cases=[]
    def save(id,a,roi,truth,group,source=None,scale=1.):
        packed=np.zeros((240,400,4),np.uint8);packed[:,:,:3]=a;p=inputs/(id+'.rgba32');p.write_bytes(packed.tobytes())
        Image.fromarray(a).save(inputs/(id+'.png'))
        cases.append(dict(id=id,file=p.as_posix(),roi=roi,truth=truth,group=group,source=source,scale=scale,
            input_fnv=fnv(p.read_bytes()),input_sha256=sha(p)))
    for c in photos:
        image=Image.open(c['original_file']).convert('RGB');fit=ImageOps.contain(image,(800,480),Image.Resampling.LANCZOS)
        canvas=Image.new('RGB',(800,480),'black');ox=(800-fit.width)//2;oy=(480-fit.height)//2;canvas.paste(fit,(ox,oy))
        sx=fit.width/image.width;sy=fit.height/image.height;box=c['crop_xyxy']
        cx=(ox+(box[0]+box[2])*sx/2)/2;cy=(oy+(box[1]+box[3])*sy/2)/2
        side=min(224,max(28,int(math.ceil(max((box[2]-box[0])*sx,(box[3]-box[1])*sy)/2/28))*28))
        x=min(399-side,max(1,int(cx-side/2)));y=min(239-side,max(1,int(cy-side/2)))
        for scale in (1.,.25,.125):
            a=np.floor(np.array(canvas).astype(np.float64)*scale+.5).astype(np.uint8)
            a[:,:,0]&=248;a[:,:,1]&=252;a[:,:,2]&=248;a=a.astype(np.uint16)
            a=((a[::2,::2]+a[1::2,::2]+a[::2,1::2]+a[1::2,1::2]+2)//4).astype(np.uint8)
            save(c['id']+f'_gain{int(scale*1000)}',a,[x,y,side],c['truth'],'existing_source_photo',c['original_file'],scale)
    rng=np.random.default_rng(20261026)
    for name,a in [('black',np.zeros((240,400,3),np.uint8)),('white',np.full((240,400,3),255,np.uint8)),
        ('gray40',np.full((240,400,3),40,np.uint8)),('seeded_random',rng.integers(0,256,(240,400,3),dtype=np.uint8))]:
        save(name,a,[144,64,112],None,'numerical_control')
    (ROOT/'digit_cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['set cases [list]']
    for c in cases:
        x,y,s=c['roi'];lines.append(f'lappend cases [dict create id {c["id"]} file {{{c["file"]}}} fnv {c["input_fnv"]} x {x} y {y} size {s}]')
    (ROOT/'digit_cases.tcl').write_text('\n'.join(lines)+'\n',encoding='ascii')
    shutil.copy2(BASE/'real_cnn_image_test_20261025/photo_sources_and_attribution.json',ROOT/'photo_sources_and_attribution.json')
    print('DIGIT_PHOTO_TESTS_PREPARED',len(cases),flush=True)
if __name__=='__main__':main()
