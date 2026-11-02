"""Compare fixed320 input students with the teacher in original400x240 coordinates."""
from pathlib import Path
import cv2,numpy as np
from road_light_common import ROOT,BASE,read,write
from road_adapt_eval_core import Evaluator,torch,non_max_suppression,scale_boxes,evaluate_serial_predictions
def run(weights,rows,loader,folder,tag):
    ev=Evaluator(weights);predictions={}
    with torch.inference_mode():
        for at in range(0,len(rows),16):
            rs=rows[at:at+16];images=[loader(r) for r in rs]
            assert all(a.shape==(320,320,3) and a.dtype==np.uint8 for a in images)
            data=np.stack([a.transpose(2,0,1) for a in images]);x=torch.from_numpy(np.ascontiguousarray(data)).cuda().half()/255
            pred=non_max_suppression(ev.model(x),.001,.6,max_det=300)
            for row,p in zip(rs,pred):
                if len(p):scale_boxes((320,320),p[:,:4],(240,400),ratio_pad=((.8,.8),(0.,64.)))
                predictions[row['name']]=p.cpu().float().tolist()
    ev.close();return evaluate_serial_predictions(rows,predictions,folder,tag)
def validation_rows():
    return [{**r,'label_path':str(BASE/'dataset/labels/val'/(Path(r['name']).stem+'.txt'))} for r in read(ROOT/'dataset/manifest.json') if r['split']=='val']
def validation_loader(row):return cv2.imread(str(ROOT/'dataset/images/val'/(Path(row['name']).stem+'.png')))[:,:,::-1].copy()
if __name__=='__main__':
    import sys
    from road_light_common import TEACHER
    out=ROOT/'baseline';out.mkdir(exist_ok=False);rows=validation_rows()
    m=run(TEACHER,rows,validation_loader,out,'teacher');write(out/'complete.json',dict(status='FROZEN_TEACHER_ON_EXACT_NEW_INPUTS_EVALUATED',metrics=m,no_fresh_test=True))
    print('EXACT_INPUT_TEACHER_BASELINE',m['all']['mAP50'],m['by_time']['night']['mAP50'],flush=True)
