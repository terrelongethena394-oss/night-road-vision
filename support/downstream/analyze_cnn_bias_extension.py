"""Test inferred 21-bit bias zero-extension against ALL recorded board results."""
from pathlib import Path
import csv,json
import numpy as np
from PIL import Image
import torch
from train_real_digit_cnn import OUT,IntegerCNN
from prepare_real_cnn_images import pooled
from prepare_digit_hls import sample

ROOT=Path('E:/FPGA_Enhance_Work/real_cnn_image_test_20261025')

def main():
    q=IntegerCNN(torch.load(OUT/'real_digit_cnn.pth',weights_only=True,map_location='cpu'))
    original=q.s['fc2.bias'].copy()
    q.s['fc2.bias']=original&((1<<21)-1)
    rows=list(csv.DictReader((ROOT/'baseline_66/board_results.csv').open()))
    failures=[];total=0
    for row in rows:
        rgb=np.array(Image.open(ROOT/'inputs'/(row['id']+'.png')).convert('RGB'))
        eroi=np.array(Image.open(ROOT/'pc_roi_references'/(row['id']+'_PC_ENH_ROI.png')).convert('RGB'))
        for kind,gray,boardpred,boardmargin in [('raw',sample(rgb,480,112),int(row['raw_board']),int(row['raw_margin'])),('enh',pooled(eroi),int(row['enh_board']),int(row['enh_margin']))]:
            p,logits=q.infer(gray);order=np.sort(logits[0]);margin=min(int(order[-1]-order[-2]),2147483647);total+=1
            if int(p[0])!=boardpred or margin!=boardmargin:
                failures.append(dict(id=row['id'],route=kind,hypothesis_prediction=int(p[0]),actual_prediction=boardpred,hypothesis_margin=margin,actual_margin=boardmargin))
    report=dict(hypothesis='Final classifier negative biases erroneously zero-extended from21bits, adding2097152 to each negative bias.',
        comparisons=total,exact_matches=total-len(failures),failures=failures,
        original_biases=original.tolist(),hypothesis_biases=q.s['fc2.bias'].tolist(),
        caveat='Diagnostic only. Wrong-sign biases are not new trained weights and must never be exported as a model.')
    (ROOT/'bias_sign_extension_diagnostic.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('ALL_BOARD_BIAS_HYPOTHESIS',total-len(failures),'/',total,'failures',failures[:3],flush=True)

if __name__=='__main__':main()
