"""Frozen external OCR on actual board-returned images; PC, not onboard OCR."""
from pathlib import Path
import json
import numpy as np
import cv2,torch
from plate_common import ROOT,BASE,SOURCE,build_model,forward_per_image,decode,sha,write
BOARD=BASE/'camera_plate_neon_20261026'
def main():
    out=BOARD/'external_ocr';out.mkdir(exist_ok=True);assert not (out/'results.json').exists()
    cases=json.loads((BOARD/'plate_cases.json').read_text(encoding='utf-8'));images=[]
    for c in cases:
        folder=BOARD/'board_plate'/c['id'];v=json.loads((folder/'plate_validation.json').read_text(encoding='utf-8'));assert v['scores_exact']
        x,y,w,h=c['roi'];cw,ch=w//96,h//32
        for name in ['input32.bin','output32.bin','protected32.bin']:
            rgb=np.fromfile(folder/name,np.uint8).reshape(240,400,4)[y:y+h,x:x+w,:3].astype(np.uint32)
            small=((rgb.reshape(32,ch,96,cw,3).sum((1,3))+cw*ch//2)//(cw*ch)).astype(np.uint8)
            images.append(cv2.resize(small[:,:,::-1],(94,24)))
    device='cuda' if torch.cuda.is_available() else 'cpu';torch.set_num_threads(4);model=build_model().to(device).eval();pred=[]
    with torch.inference_mode():
        for i in range(0,len(images),16):
            x=np.stack(images[i:i+16]).astype(np.float32);x=((x-127.5)/128).transpose(0,3,1,2).copy()
            pred.extend(decode(forward_per_image(model,torch.from_numpy(x).to(device))))
    rows=[]
    for i,c in enumerate(cases):rows.append(dict(id=c['id'],truth=c['truth'],gain=c['gain'],predictions=pred[i*3:i*3+3]))
    summary=[]
    for gain in [1.,.25]:
        rs=[r for r in rows if r['gain']==gain];summary.append(dict(gain=gain,n=len(rs),correct=[sum(r['predictions'][k]==r['truth'] for r in rs) for k in range(3)]))
    photos=[r for r in rows if r['truth'] is not None];changes={name:dict(wins=sum(r['predictions'][0]!=r['truth'] and r['predictions'][k]==r['truth'] for r in photos),losses=sum(r['predictions'][0]==r['truth'] and r['predictions'][k]!=r['truth'] for r in photos)) for k,name in [(1,'NET'),(2,'AUTO')]}
    result=dict(status='FROZEN_PC_OCR_ON_ACTUAL_BOARD_IMAGE_BUFFERS',processor='PC; the actual on-board recognizer is TinyPlate, not this external LPRNet.',recognizer='Unmodified pretrained sirius-ai/LPRNet_Pytorch, per-image normalization equivalent to upstream batch1',weights_sha256=sha(SOURCE/'weights/Final_LPRNet_model.pth'),views=['RAW','NET','AUTO'],summary=summary,changes=changes,cases=rows,limitations=['Six metadata-selected original plate crops and synthetic gain. Not population accuracy or real night.','Given manually annotated region, no detection; framing and RGB565 quantization explicitly applied.','Unknown upstream pretraining overlap. No fitting or model/threshold selection on these cases.','Only changes to input images between views; all external OCR weights/preprocessing/decoder fixed.'])
    write(out/'results.json',result);print(json.dumps(dict(summary=summary,changes=changes)),flush=True)
if __name__=='__main__':main()
