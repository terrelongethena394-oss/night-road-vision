"""Final intermediate-resolution candidate, old-validation selection only."""
from pathlib import Path
import cv2,numpy as np
from road_light_common import ROOT as LIGHT,TEACHER,read,write,sha
ROOT=Path('E:/FPGA_Enhance_Work/road_288_20261027')

def preprocess288(im):
    assert im.shape==(240,400,3) and im.dtype==np.uint8
    xx=50*np.arange(288)+7;yy=480*np.arange(173)+67
    x,fx=xx//36,xx%36;y,fy=yy//346,yy%346;z=im.astype(np.int32)
    v=(z[y[:,None],x[None,:]]*((346-fy)[:,None]*(36-fx)[None,:])[:,:,None]+
       z[y[:,None],x[None,:]+1]*((346-fy)[:,None]*fx[None,:])[:,:,None]+
       z[y[:,None]+1,x[None,:]]*(fy[:,None]*(36-fx)[None,:])[:,:,None]+
       z[y[:,None]+1,x[None,:]+1]*(fy[:,None]*fx[None,:])[:,:,None])
    out=np.full((288,288,3),114,np.uint8);out[57:230]=((v+6228)//12456).astype(np.uint8);return out

def evaluate(rows,loader,out,tag):
    from road_adapt_eval_core import Evaluator,torch,non_max_suppression,scale_boxes,evaluate_serial_predictions
    ev=Evaluator(TEACHER);predictions={}
    with torch.inference_mode():
        for at in range(0,len(rows),16):
            rs=rows[at:at+16];data=np.stack([loader(r).transpose(2,0,1) for r in rs]);x=torch.from_numpy(data.copy()).cuda().half()/255
            pred=non_max_suppression(ev.model(x),.001,.6,max_det=300)
            for r,p in zip(rs,pred):
                if len(p):scale_boxes((288,288),p[:,:4],(240,400),ratio_pad=((.72,.72),(0.,57.)))
                predictions[r['name']]=p.cpu().float().tolist()
    ev.close();return evaluate_serial_predictions(rows,predictions,out,tag)

def main():
    ROOT.mkdir(exist_ok=False)
    write(ROOT/'protocol.json',dict(status='FROZEN_BEFORE_288_VALIDATION_AND_ALL_UNSEEN_INFERENCE',teacher_sha256=sha(TEACHER),
       reason='256 all-AP gate failed; final intermediate288 candidate on OLD validation. No further input sizes searched this round.',
       preprocess='Explicit integerbilinear288x173, xnum50x+7 /36, ynum480y+67 /346, half-up /12456. Pad57top58bottom gray114.',
       inverse='scale.72 and actualtop57, used identically in GPU/C.',selection='Same quality gates. Freeze288 result before shared new480test. No test-driven retuning.',
       macs=419302656,original320_macs=517657600,no_hardware=True))
    from road_light_evaluate import validation_rows
    from select_road_light_candidates import gates
    out=ROOT/'validation';out.mkdir();m=evaluate(validation_rows(),lambda r:preprocess288(cv2.imread(str(LIGHT/'raw400/val'/(Path(r['name']).stem+'.png')))[:,:,::-1].copy()),out,'input288')
    gate=gates(m,read(LIGHT/'baseline/teacher_metrics.json'))
    freeze=dict(status='288_SELECTION_FROZEN_BEFORE_SHARED_NEW_TEST',metrics=m,gates=gate,passes=all(gate.values()),teacher_sha256=sha(TEACHER),no_new_test=True)
    write(ROOT/'validation_complete.json',freeze);write(LIGHT/'frozen_288_addendum.json',freeze)
    print('INPUT288_VALIDATION',m['all']['mAP50'],m['by_time']['night']['mAP50'],gate,flush=True)
if __name__=='__main__':main()
