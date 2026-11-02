"""Check whether actual margins correspond to gray/pooling rounding variants."""
from pathlib import Path
import csv,json
import numpy as np
from PIL import Image
import torch
from train_real_digit_cnn import OUT,IntegerCNN

ROOT=Path('E:/FPGA_Enhance_Work/real_cnn_image_test_20261025')

def main():
    q=IntegerCNN(torch.load(OUT/'real_digit_cnn.pth',weights_only=True,map_location='cpu'))
    rows=list(csv.DictReader((ROOT/'baseline_controls/board_results.csv').open()))
    report=[]
    for row in rows:
        rgb=np.array(Image.open(ROOT/'inputs'/(row['id']+'.png')).convert('RGB')).astype(np.int64)[112:336,480:704]
        result=dict(id=row['id'],rgb_values_if_constant=np.unique(rgb.reshape(-1,3),axis=0).tolist()[:6],board_margin=int(row['raw_margin']),probes=[])
        for gr in (0,128):
            gray=(77*rgb[:,:,0]+150*rgb[:,:,1]+29*rgb[:,:,2]+gr)>>8
            for ar in (0,32):
                x=((gray.reshape(28,8,28,8).sum((1,3))+ar)>>6).astype(np.uint8)
                pred,logits=q.infer(x);order=np.sort(logits[0]);margin=min(int(order[-1]-order[-2]),2147483647)
                result['probes'].append(dict(gray_round=gr,average_round=ar,pred=int(pred[0]),margin=margin,gray_range=[int(x.min()),int(x.max())],exact=margin==int(row['raw_margin'])))
        report.append(result);print(json.dumps(result),flush=True)
    (ROOT/'luma_rounding_diagnostic.json').write_text(json.dumps(report,indent=2),encoding='utf-8')

if __name__=='__main__':main()
