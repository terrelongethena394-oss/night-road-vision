"""One fixed detector/box evaluator for validation, new holdout and regression."""
import os,sys,time
from pathlib import Path
import cv2,numpy as np
from road_adapt_common import ROOT,NAMES,write
os.environ['YOLOv5_AUTOINSTALL']='false';os.environ['YOLOV5_CONFIG_DIR']=str(ROOT/'config')
os.chdir(ROOT/'yolov5');sys.path.insert(0,str(ROOT/'yolov5'))
import torch
from models.common import DetectMultiBackend
from utils.augmentations import letterbox
from utils.general import non_max_suppression,scale_boxes
from utils.metrics import ap_per_class,box_iou
from val import process_batch
from torchvision.ops import nms
torch.set_num_threads(4)

def truth(row,width,height):
    a=np.array([[float(v) for v in line.split()] for line in Path(row['label_path']).read_text().splitlines() if line],np.float32).reshape(-1,5)
    b=a.copy();b[:,1]=(a[:,1]-a[:,3]/2)*width;b[:,2]=(a[:,2]-a[:,4]/2)*height;b[:,3]=(a[:,1]+a[:,3]/2)*width;b[:,4]=(a[:,2]+a[:,4]/2)*height
    return b
def matched_indices(pred,labels):
    if not len(pred) or not len(labels):return set()
    iou=box_iou(labels[:,1:],pred[:,:4]);x=torch.where((iou>=.5)&(labels[:,0:1]==pred[:,5]))
    if not len(x[0]):return set()
    a=torch.cat((torch.stack(x,1),iou[x[0],x[1]][:,None]),1).cpu().numpy()
    if len(a)>1:
        a=a[a[:,2].argsort()[::-1]];a=a[np.unique(a[:,1],return_index=True)[1]];a=a[np.unique(a[:,0],return_index=True)[1]]
    return {int(v) for v in a[:,0]}
def metrics(records):
    tp=np.concatenate([r['correct'] for r in records]);conf=np.concatenate([r['pred'][:,4] for r in records]);predcls=np.concatenate([r['pred'][:,5] for r in records]);target=np.concatenate([r['truth'][:,0] for r in records])
    a=ap_per_class(tp,conf,predcls,target,plot=False,names=dict(enumerate(NAMES)));table={}
    for k,name in enumerate(NAMES):
        n=int((target==k).sum());where=np.where(a[6]==k)[0];true=sum(int(((r['op_pred'][:,5]==k)&r['op_correct']).sum()) for r in records);npred=sum(int((r['op_pred'][:,5]==k).sum()) for r in records)
        table[name]=dict(objects=n,ap50=float(a[5][where[0],0]) if len(where) else None,ap50_95=float(a[5][where[0]].mean()) if len(where) else None,
                         tp=true,fp=npred-true,fn=n-true,precision=true/npred if npred else 0.,recall=true/n if n else None)
    return dict(images=len(records),mAP50=float(a[5][:,0].mean()),mAP50_95=float(a[5].mean()),classes=table)
def supplement_predictions(raw,enhanced,policy,mean_luma):
    # Only detector boxes/scores and input brightness are inputs; no ground truth.
    a=torch.tensor(raw,dtype=torch.float32,device='cuda:0').reshape(-1,6)
    if mean_luma>=policy['gate_mean']:return a.cpu().tolist()
    b=torch.tensor(enhanced,dtype=torch.float32,device='cuda:0').reshape(-1,6);b=b[b[:,4]>=policy['min_conf']]
    strong=a[a[:,4]>=.25]
    if len(b) and len(strong):
        overlaps=box_iou(b[:,:4],strong[:,:4]);same=b[:,5:6]==strong[:,5][None,:]
        b=b[~((overlaps>=.5)&same).any(1)]
    if len(b):b[:,4]*=policy['weight']
    merged=torch.cat((a,b));boxes=merged[:,:4]+merged[:,5:6]*7680
    indices=nms(boxes,merged[:,4],.6)[:300]
    return merged[indices].cpu().tolist()
def evaluate_serial_predictions(rows,predictions,folder,tag):
    device=torch.device('cuda:0');iouv=torch.linspace(.5,.95,10,device=device);records=[]
    for row in rows:
        p=torch.tensor(predictions[row['name']],dtype=torch.float32,device=device).reshape(-1,6)
        labels=torch.from_numpy(truth(row,400,240)).to(device);correct=process_batch(p,labels,iouv).cpu().numpy()
        op=p[p[:,4]>=.25];opcorrect=process_batch(op,labels,iouv[:1]).cpu().numpy()[:,0];matched=matched_indices(op,labels)
        assert int(opcorrect.sum())==len(matched)
        records.append(dict(name=row['name'],timeofday=row['timeofday'],pred=p.cpu().numpy(),truth=labels.cpu().numpy(),correct=correct,op_pred=op.cpu().numpy(),op_correct=opcorrect,matched_gt=matched))
    result=dict(all=metrics(records),by_time={t:metrics([r for r in records if r['timeofday']==t]) for t in ['night','dawn/dusk','daytime']},gpu_forward_ms=None)
    serial=[dict(name=r['name'],timeofday=r['timeofday'],detections=r['pred'].tolist(),ground_truth=r['truth'].tolist(),correct=r['correct'].tolist(),matched_gt=sorted(r['matched_gt'])) for r in records]
    write(Path(folder)/(tag+'_metrics.json'),result);write(Path(folder)/(tag+'_predictions.json'),serial)
    print('DUAL_RESULT_POLICY_EVALUATED',tag,result['by_time']['night']['mAP50'],flush=True);return result
class Evaluator:
    def __init__(self,weights):
        self.device=torch.device('cuda:0');self.iouv=torch.linspace(.5,.95,10,device=self.device)
        self.model=DetectMultiBackend(str(weights),device=self.device,data=str(ROOT/'dataset/road4.yaml'),fp16=True)
    @torch.inference_mode()
    def run(self,rows,rgb_loader,folder,tag):
        folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);records=[];forward=0.;batchsize=16
        for at in range(0,len(rows),batchsize):
            rs=rows[at:at+batchsize];images=[rgb_loader(r) for r in rs];padded=[];transforms=[]
            for image in images:
                assert image.shape==(240,400,3)
                a,ratio,pad=letterbox(image,(416,416),auto=False,stride=32);padded.append(a.transpose(2,0,1));transforms.append((ratio,pad))
            x=torch.from_numpy(np.ascontiguousarray(np.stack(padded))).to(self.device).half()/255
            torch.cuda.synchronize();t=time.monotonic();output=self.model(x);torch.cuda.synchronize();forward+=time.monotonic()-t
            preds=non_max_suppression(output,.001,.6,max_det=300)
            for r,image,pred,transform in zip(rs,images,preds,transforms):
                if len(pred):scale_boxes(x.shape[2:],pred[:,:4],image.shape,ratio_pad=transform)
                labels=torch.from_numpy(truth(r,400,240)).to(self.device);correct=process_batch(pred,labels,self.iouv).cpu().numpy()
                op=pred[pred[:,4]>=.25];opcorrect=process_batch(op,labels,self.iouv[:1]).cpu().numpy()[:,0];matched=matched_indices(op,labels)
                assert int(opcorrect.sum())==len(matched)
                records.append(dict(name=r['name'],timeofday=r['timeofday'],pred=pred.cpu().numpy(),truth=labels.cpu().numpy(),correct=correct,
                                    op_pred=op.cpu().numpy(),op_correct=opcorrect,matched_gt=matched))
        result=dict(all=metrics(records),by_time={p:metrics([r for r in records if r['timeofday']==p]) for p in ['night','dawn/dusk','daytime']},gpu_forward_ms=forward/len(rows)*1000)
        serial=[dict(name=r['name'],timeofday=r['timeofday'],detections=r['pred'].tolist(),ground_truth=r['truth'].tolist(),correct=r['correct'].tolist(),matched_gt=sorted(r['matched_gt'])) for r in records]
        write(folder/(tag+'_metrics.json'),result);write(folder/(tag+'_predictions.json'),serial)
        print('ROAD_ADAPT_VIEW_EVALUATED',tag,'all',result['all']['mAP50'],'night',result['by_time']['night']['mAP50'],flush=True)
        return result
    def close(self):
        del self.model;torch.cuda.empty_cache()
