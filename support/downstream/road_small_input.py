"""Frozen teacher at256, exact integer-resize specification and validation."""
from pathlib import Path
import cv2,numpy as np
from road_light_common import ROOT as LIGHT,TEACHER,read,write,sha
ROOT=Path('E:/FPGA_Enhance_Work/road_256_20261027')

def preprocess256(im):
    assert im.shape==(240,400,3) and im.dtype==np.uint8
    xx=50*np.arange(256)+9;yy=240*np.arange(154)+43
    x,fx=xx//32,xx%32;y,fy=yy//154,yy%154;z=im.astype(np.int32)
    v=(z[y[:,None],x[None,:]]*((154-fy)[:,None]*(32-fx)[None,:])[:,:,None]+
       z[y[:,None],x[None,:]+1]*((154-fy)[:,None]*fx[None,:])[:,:,None]+
       z[y[:,None]+1,x[None,:]]*(fy[:,None]*(32-fx)[None,:])[:,:,None]+
       z[y[:,None]+1,x[None,:]+1]*(fy[:,None]*fx[None,:])[:,:,None])
    out=np.full((256,256,3),114,np.uint8);out[51:205]=((v+2464)//4928).astype(np.uint8);return out

def evaluate(rows,loader,out,tag):
    from road_adapt_eval_core import Evaluator,torch,non_max_suppression,scale_boxes,evaluate_serial_predictions
    ev=Evaluator(TEACHER);predictions={}
    with torch.inference_mode():
        for at in range(0,len(rows),16):
            rs=rows[at:at+16];data=np.stack([loader(r).transpose(2,0,1) for r in rs]);x=torch.from_numpy(data.copy()).cuda().half()/255
            pred=non_max_suppression(ev.model(x),.001,.6,max_det=300)
            for r,p in zip(rs,pred):
                if len(p):scale_boxes((256,256),p[:,:4],(240,400),ratio_pad=((.64,.64),(0.,51.)))
                predictions[r['name']]=p.cpu().float().tolist()
    ev.close();return evaluate_serial_predictions(rows,predictions,out,tag)

def main():
    ROOT.mkdir(exist_ok=False)
    write(ROOT/'protocol.json',dict(status='FROZEN_BEFORE_256_CANDIDATE_VALIDATION_AND_ALL_NEW_HOLDOUTS',teacher_sha256=sha(TEACHER),
        input='Camera-order raw400 RGB, exact bilinear256x154 paddedtop/bottom51 gray114. Denominators32x154, half-upinteger rounding.',
        labels='Standard letterbox inverse withscale.64,pad(0,51); resizing actualheight154 rounds153.6 like upstream YOLO.',
        gates='Same light and integer no-regression gates; additional256candidate. No retraining, no holdout tuning.',
        macs=331300864,original320_macs=517657600,no_hardware=True))
    write(LIGHT/'protocol_256_addendum.json',read(ROOT/'protocol.json'))
    from road_light_evaluate import validation_rows
    out=ROOT/'validation';out.mkdir();m=evaluate(validation_rows(),lambda r:preprocess256(cv2.imread(str(LIGHT/'raw400/val'/(Path(r['name']).stem+'.png')))[:,:,::-1].copy()),out,'input256')
    write(ROOT/'validation_complete.json',dict(status='256_INPUT_OLD_VALIDATION_COMPLETE',metrics=m,no_new_test=True));print('INPUT256_VALIDATION',m['all']['mAP50'],m['by_time']['night']['mAP50'],flush=True)
if __name__=='__main__':main()
