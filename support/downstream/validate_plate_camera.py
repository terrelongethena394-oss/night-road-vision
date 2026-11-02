"""Independent audit of actual ARM gray/Q10 tensors, all CTC scores and glyphs."""
from pathlib import Path
import json,sys,subprocess
import numpy as np
import torch
SOURCE=Path('C:/Users/曹/Documents/ChatGPT/FPGA创新设计大赛/starter/downstream')
sys.path.insert(0,str(SOURCE))
from plate_common import CHARS,sha,write,decode
from tiny_plate_integer import IntegerPlate,normalized_np
from train_tiny_plate import valid_word
HERE=Path(__file__).resolve().parent
def pooled(image,x,y,width,height):
    a=image[y:y+height,x:x+width,:3].astype(np.uint32);g=(77*a[:,:,0]+150*a[:,:,1]+29*a[:,:,2]+128)>>8
    cw,ch=width//96,height//32;count=cw*ch
    return ((g.reshape(32,ch,96,cw).sum((1,3))+count//2)//count).astype(np.uint8)
def validate(folder,root=None,q=None):
    root=root or HERE
    r=subprocess.run([sys.executable,str(root/'validate_multinex_camera.py'),str(folder)],capture_output=True,text=True)
    (folder/'enhancement_validator.log').write_text(r.stdout+r.stderr,encoding='utf-8');assert r.returncode==0,r.stderr
    proof=json.loads((root/'plate_numeric_proof.json').read_text(encoding='utf-8'));assert sha(root/'plate_model.pth')==proof['model_sha256']
    compiled=json.loads((root/'offline_camera.json').read_text(encoding='utf-8'));assert sha(root/'camera.elf')==compiled['elf_sha256']
    if compiled.get('arm_optimized_header_sha256'):assert sha(root/'app_src/plate_arm_kernel.h')==compiled['arm_optimized_header_sha256']
    assert sha(root/'app_src/plate_weights.h')==proof['weights_header_sha256'] and sha(root/'app_src/plate_native_kernel.h')==proof['kernel_sha256']
    m=[int(v,0) for v in (folder/'mailbox.txt').read_text().split()];t=[int(v,0) for v in (folder/'plate_telemetry.txt').read_text().split()]
    guarded=bool(compiled.get('consistency_guard'));nviews=4 if guarded else 3
    assert m[1]==(8 if guarded else 7) and len(t)==(22 if guarded else 20) and t[13]==(4 if guarded else 3) and t[14]==m[5]
    assert t[11:13]==[0x04e00000,0x04e10000] and t[17]==0x04e20000 and t[19]==0x04e30000 and t[18]==proof['head_score_fraction']
    x,y,width=t[8:11];height=t[16];assert t[15]==width
    images=[np.fromfile(folder/name,np.uint8).reshape(240,400,4) for name in ['input32.bin','output32.bin','protected32.bin']]
    if guarded:
        before=np.zeros_like(images[0]);before[:,:,:3]=((images[0][:,:,:3].astype(np.uint32)*(256-t[21])+images[1][:,:,:3].astype(np.uint32)*t[21]+128)>>8).astype(np.uint8);images.append(before)
    expected_gray=np.stack([pooled(image,x,y,width,height) for image in images]);actual_gray=np.fromfile(folder/'plate_gray.bin',np.uint8).reshape(nviews,32,96)
    assert np.array_equal(expected_gray,actual_gray),'Plate input pooling differs'
    expected_normalized=normalized_np(expected_gray);actual_normalized=np.fromfile(folder/'plate_normalized.i16',dtype='<i2').reshape(nviews,1,32,96)
    assert np.array_equal(expected_normalized,actual_normalized),'Plate histogram/Q10 normalization differs'
    if q is None:q=IntegerPlate(torch.load(root/'plate_model.pth',weights_only=True,map_location='cpu'))
    scores=q.infer(expected_gray);actual=np.fromfile(folder/'plate_scores.i32',dtype='<i4').reshape(nviews,68,24);assert np.array_equal(scores,actual),'ARM CTC logits differ'
    words=decode(scores);actual_tokens=np.fromfile(folder/'plate_tokens.bin',np.uint8).reshape(nviews,32);expected_tokens=np.zeros((nviews,32),np.uint8)
    valid=[]
    for i,word in enumerate(words):
        expected_tokens[i,0]=len(word);expected_tokens[i,1]=valid_word(word);expected_tokens[i,2:2+len(word)]=[CHARS.index(c) for c in word];valid.append(valid_word(word))
    assert np.array_equal(expected_tokens,actual_tokens) and t[:3]==list(map(int,valid[:3]))
    fallback=False
    if guarded:
        fallback=bool(valid[0] and (not valid[3] or words[0]!=words[3]));assert int(fallback)==t[20],'Consistency decision differs'
        assert np.array_equal(images[2],images[0] if fallback else images[3]),'Final image does not follow verified recognition decision'
        if fallback:assert words[2]==words[0] and valid[2] and t[21]>0
    glyph=np.load(root/'plate_glyphs.npz');assert glyph['chars'].tolist()==CHARS
    font=json.loads((root/'font_source.json').read_text());assert sha(root/'app_src/plate_glyphs.h')==font['bitmap_header_sha256']
    lcd=np.fromfile(folder/'display.bgr24',np.uint8).reshape(480,800,3)[:,:,::-1]
    for i,word in enumerate(words[:3]):
        labels=[CHARS.index(c) for c in word] if valid[i] else [67,67];want=np.zeros((24,140,3),np.uint8)
        for j,label in enumerate(labels):
            rows=glyph['glyphs'][label];bits=((rows[:,None]>>np.arange(19,-1,-1)[None,:])&1).astype(np.uint8)*255
            want[:,j*20:(j+1)*20]=bits[:,:,None]
        start=8+i*260+82;assert np.array_equal(lcd[387:411,start:start+140],want),'Actual displayed plate glyphs differ from CTC output'
    candidate=3 if guarded else 2
    reuse=np.array_equal(actual_normalized[candidate],actual_normalized[0]) or np.array_equal(actual_normalized[candidate],actual_normalized[1]);assert t[7]==(2 if reuse else 3)
    result=dict(status='ACTUAL_ARM_PLATE_ALL_TENSORS_SCORES_AND_GLYPHS_EXACT',words=words[:3],accepted=valid[:3],displayed=[w if ok else '--' for w,ok in zip(words[:3],valid[:3])],candidate_word=words[3] if guarded else words[2],candidate_accepted=valid[candidate],consistency_fallback=fallback,decision_exact=True,gray_bytes=nviews*3072,normalized_bytes=nviews*6144,scores=nviews*1632,gray_exact=True,normalized_exact=True,scores_exact=True,ctc_tokens_exact=True,display_glyphs_exact=True,roi=[x,y,width,height],physical_inferences=t[7],raw_ocr_seconds=(t[3]+(t[4]<<32))/m[8],other_ocr_seconds=(t[5]+(t[6]<<32))/m[8],sequence=m[5],model_sha256=proof['model_sha256'],note='Numeric correctness is separate from full-string OCR accuracy. Ground truth never sent to firmware. Specified plate ROI only, no automatic localization.')
    write(folder/'plate_validation.json',result);return result
if __name__=='__main__':print(json.dumps(validate(Path(sys.argv[1])),ensure_ascii=False),flush=True)
