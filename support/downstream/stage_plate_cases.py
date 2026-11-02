"""Metadata-selected real heldout crops, not selected using OCR outcomes."""
import json
import numpy as np
from PIL import Image
from plate_common import ROOT,BASE,SEED,write,sha
OUT=BASE/'camera_plate_20261026'
def fnv(data):
    h=2166136261
    for b in data:h=((h^b)*16777619)&0xffffffff
    return h
def main():
    assert (OUT/'camera.elf').exists();assert not (OUT/'plate_cases.json').exists()
    data=np.load(ROOT/'data/test.npz');texts=data['texts'].tolist();chosen=[]
    for province,n in [('苏',2),('皖',2),('沪',1),('京',1)]:chosen.extend([i for i,t in enumerate(texts) if t.startswith(province)][:n])
    assert len(chosen)==6
    write(OUT/'plate_case_selection.json',dict(status='FIXED_BEFORE_ANY_BOARD_IMAGE_OR_SCORE_CAPTURE',selection='First two Su, first two Wan, first Hu, first Jing in fixed heldout cache order; province chosen for display coverage, no OCR-outcome selection. Two synthetic gains1/.25. Two nonplate controls.',indices=chosen,scope='Real plate CROP replay:96x32 RGB565 pixels expanded4x3 to384x96, border replicated to400x240. No whole-car context or automatic localization; not actual night. Truth stays on PC.'))
    inputs=OUT/'plate_inputs';inputs.mkdir(exist_ok=True);cases=[]
    for j,i in enumerate(chosen):
        for gain in [1.,.25]:
            bgr=np.clip(np.floor(data['x'][i].astype(np.float32)*gain+.5),0,255).astype(np.uint8);rgb=bgr[:,:,::-1].copy()
            rgb[:,:,0]&=248;rgb[:,:,1]&=252;rgb[:,:,2]&=248
            large=np.repeat(np.repeat(rgb,3,axis=0),4,axis=1);frame=np.pad(large,((72,72),(8,8),(0,0)),mode='edge')
            packed=np.zeros((240,400,4),np.uint8);packed[:,:,:3]=frame
            name=f'plate_{j:02d}_gain{int(gain*1000)}';path=inputs/(name+'.rgba32');path.write_bytes(packed.tobytes());Image.fromarray(frame).save(inputs/(name+'.png'))
            cases.append(dict(id=name,file=path.as_posix(),truth=texts[i],source_index=i,gain=gain,kind='real_annotated_plate_crop',roi=[8,72,384,96],input_sha256=sha(path),fnv=fnv(packed.tobytes())))
    neg=np.load(ROOT/'negatives/test.npz')['x']
    for name,i in [('nonplate_clothing',0),('nonplate_scene',1000)]:
        rgb=np.repeat(neg[i,:,:,None],3,axis=2);rgb[:,:,0]&=248;rgb[:,:,1]&=252;rgb[:,:,2]&=248
        frame=np.pad(np.repeat(np.repeat(rgb,3,axis=0),4,axis=1),((72,72),(8,8),(0,0)),mode='edge');packed=np.zeros((240,400,4),np.uint8);packed[:,:,:3]=frame
        path=inputs/(name+'.rgba32');path.write_bytes(packed.tobytes());Image.fromarray(frame).save(inputs/(name+'.png'))
        cases.append(dict(id=name,file=path.as_posix(),truth=None,source_index=i,gain=None,kind='nonplate_control',roi=[8,72,384,96],input_sha256=sha(path),fnv=fnv(packed.tobytes())))
    write(OUT/'plate_cases.json',cases)
    lines=['set cases [list]']
    for c in cases:lines.append(f'lappend cases [dict create id {c["id"]} file {{{c["file"]}}} fnv {c["fnv"]}]')
    (OUT/'plate_cases.tcl').write_text('\n'.join(lines)+'\n',encoding='ascii');print('REAL_PLATE_CASES_STAGED',len(cases),flush=True)
if __name__=='__main__':main()
