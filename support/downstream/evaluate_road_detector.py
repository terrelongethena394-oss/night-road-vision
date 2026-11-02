"""Frozen test: detector transfer, actual-night strata and fixed enhancement controls."""
from pathlib import Path
import concurrent.futures as cf,hashlib,json,os,subprocess,sys,time
import cv2,numpy as np
ROOT=Path('E:/FPGA_Enhance_Work/road_detection_20261026')
NAMES=['person','car','truck','bus']
REFERENCE=Path('E:/FPGA_Enhance_Work/multinex_fixed_w18_20261025/cpp_reference/multinex_reference.exe')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def original(r):
    a=cv2.imread(str(ROOT/'dataset/images/test'/r['name']));assert a is not None
    return a
def ground_truth(r,width,height):
    p=ROOT/'dataset/labels/test'/(Path(r['name']).stem+'.txt')
    a=np.array([[float(v) for v in s.split()] for s in p.read_text().splitlines() if s],np.float32).reshape(-1,5)
    b=a.copy();b[:,1]=(a[:,1]-a[:,3]/2)*width;b[:,2]=(a[:,2]-a[:,4]/2)*height;b[:,3]=(a[:,1]+a[:,3]/2)*width;b[:,4]=(a[:,2]+a[:,4]/2)*height
    return b

def main():
    started=time.monotonic();print('WAITING_FOR_FROZEN_ROAD_MODEL',flush=True)
    frozen=None
    while frozen is None:
        if time.monotonic()-started>10800:raise TimeoutError('Training has not produced a frozen candidate')
        try:frozen=json.loads((ROOT/'frozen/frozen_candidate.json').read_text())
        except (FileNotFoundError,json.JSONDecodeError):time.sleep(5)
    candidate=Path(frozen['weights']);assert sha(candidate)==frozen['model_sha256']
    protocol=json.loads((ROOT/'training_protocol.json').read_text())
    assert sha(ROOT/'dataset/manifest.json')==protocol['dataset_manifest_sha256']
    assert sha(ROOT/'initialization/yolov5n_road4.pt')==protocol['initial_weights_sha256']
    OUT=ROOT/'test';OUT.mkdir(exist_ok=False)
    rows=[r for r in json.loads((ROOT/'dataset/manifest.json').read_text()) if r['split']=='test' and r['status']=='READY']
    assert rows and not frozen['test_inference_performed']
    # Fix display examples by metadata order, before all test inference.
    display=[]
    for period,n in [('night',3),('dawn/dusk',2),('daytime',1)]:display.extend([r['name'] for r in rows if r['timeofday']==period][:n])
    write(OUT/'evaluation_protocol.json',dict(status='FROZEN_BEFORE_FIRST_TEST_INFERENCE',names=NAMES,candidate_sha256=sha(candidate),
          initial_sha256=protocol['initial_weights_sha256'],input416=True,letterbox='All inputs padded to416x416 consistently',ap_confidence=.001,nms_iou=.6,max_det=300,operating_confidence=.25,match_iou=.5,
          board_input='Same400x240 resize and RGB565 zero-extension for all enhancement controls; a simulation of limited input bandwidth, not an actual OV5640 capture.',
          views=['original_initial','original_finetuned','raw400','multinex400','protected400','gamma400'],
          display_examples=display,reference_exe_sha256=sha(REFERENCE),reference_expected_sha256='2eb7289db70c9f5f305cc2b0c84187653b312c03409247db82ecc005aded622d',
          note='No ground truth enters image enhancement or detector inference. No test fitting/threshold search. No real-time board detector or safety claim.'))
    assert sha(REFERENCE)=='2eb7289db70c9f5f305cc2b0c84187653b312c03409247db82ecc005aded622d'
    os.environ['YOLOv5_AUTOINSTALL']='false';os.environ['YOLOV5_CONFIG_DIR']=str(ROOT/'config')
    os.chdir(ROOT/'yolov5')
    sys.path.insert(0,str(ROOT/'yolov5'))
    import torch
    from models.common import DetectMultiBackend
    from utils.augmentations import letterbox
    from utils.general import non_max_suppression,scale_boxes
    from utils.metrics import ap_per_class,box_iou
    from val import process_batch
    torch.set_num_threads(4);device=torch.device('cuda:0');iouv=torch.linspace(.5,.95,10,device=device)
    def matched(pred,labels):
        if len(pred)==0 or len(labels)==0:return set()
        iou=box_iou(labels[:,1:],pred[:,:4]);x=torch.where((iou>=.5)&(labels[:,0:1]==pred[:,5]))
        if not len(x[0]):return set()
        a=torch.cat((torch.stack(x,1),iou[x[0],x[1]][:,None]),1).cpu().numpy()
        if len(a)>1:
            a=a[a[:,2].argsort()[::-1]];a=a[np.unique(a[:,1],return_index=True)[1]];a=a[np.unique(a[:,0],return_index=True)[1]]
        return {int(v) for v in a[:,0]}
    def metrics(records):
        tp=np.concatenate([r['correct'] for r in records]);conf=np.concatenate([r['pred'][:,4] for r in records]);predcls=np.concatenate([r['pred'][:,5] for r in records]);truth=np.concatenate([r['truth'][:,0] for r in records])
        ap=ap_per_class(tp,conf,predcls,truth,plot=False,names=dict(enumerate(NAMES)))
        table={}
        for k,name in enumerate(NAMES):
            n=int((truth==k).sum());j=np.where(ap[6]==k)[0]
            true=sum(int(((r['op_pred'][:,5]==k)&r['op_correct']).sum()) for r in records)
            predictions=sum(int((r['op_pred'][:,5]==k).sum()) for r in records)
            table[name]=dict(objects=n,ap50=float(ap[5][j[0],0]) if len(j) else None,ap50_95=float(ap[5][j[0]].mean()) if len(j) else None,
                             tp_at_conf025=true,fp_at_conf025=predictions-true,fn_at_conf025=n-true,
                             precision_at_conf025=true/predictions if predictions else 0.,recall_at_conf025=true/n if n else None)
        return dict(images=len(records),mAP50=float(ap[5][:,0].mean()),mAP50_95=float(ap[5].mean()),classes=table)
    @torch.inference_mode()
    def evaluate(weights,view,loader):
        model=DetectMultiBackend(str(weights),device=device,data=str(ROOT/'dataset/road4.yaml'),fp16=True)
        records=[];infer_seconds=0.;nms_seconds=0.;batchsize=16
        for at in range(0,len(rows),batchsize):
            batch=rows[at:at+batchsize];images=[loader(r) for r in batch];ratios=[];padded=[]
            for image in images:
                b,ratio,pad=letterbox(image,(416,416),auto=False,stride=32);padded.append(b[:,:,::-1].transpose(2,0,1));ratios.append((ratio,pad))
            x=torch.from_numpy(np.ascontiguousarray(np.stack(padded))).to(device).half()/255
            torch.cuda.synchronize();t=time.monotonic()
            with torch.inference_mode():output=model(x)
            torch.cuda.synchronize();infer_seconds+=time.monotonic()-t;t=time.monotonic()
            predictions=non_max_suppression(output,.001,.6,max_det=300)
            torch.cuda.synchronize();nms_seconds+=time.monotonic()-t
            for r,image,pred,ratio in zip(batch,images,predictions,ratios):
                if len(pred):scale_boxes(x.shape[2:],pred[:,:4],image.shape,ratio_pad=ratio)
                labels=torch.from_numpy(ground_truth(r,image.shape[1],image.shape[0])).to(device)
                correct=process_batch(pred,labels,iouv).cpu().numpy()
                op=pred[pred[:,4]>=.25];opcorrect=process_batch(op,labels,iouv[:1]).cpu().numpy()[:,0];matched_gt=matched(op,labels)
                assert int(opcorrect.sum())==len(matched_gt)
                records.append(dict(name=r['name'],timeofday=r['timeofday'],pred=pred.cpu().numpy(),truth=labels.cpu().numpy(),correct=correct,op_pred=op.cpu().numpy(),op_correct=opcorrect,matched_gt=matched_gt))
            if at%160==0:print('ROAD_TEST_INFERENCE',view,min(at+batchsize,len(rows)),len(rows),flush=True)
        summary=dict(all=metrics(records),by_time={p:metrics([r for r in records if r['timeofday']==p]) for p in ['night','dawn/dusk','daytime']},gpu_forward_ms_per_image=infer_seconds/len(rows)*1000,nms_ms_per_image=nms_seconds/len(rows)*1000)
        serial=[dict(name=r['name'],timeofday=r['timeofday'],detections=r['pred'].tolist(),ground_truth=r['truth'].tolist(),correct=r['correct'].tolist(),matched_gt=sorted(r['matched_gt'])) for r in records]
        write(OUT/(view+'_predictions.json'),serial);write(OUT/(view+'_metrics.json'),summary)
        del model;torch.cuda.empty_cache();print('ROAD_TEST_VIEW_COMPLETE',view,json.dumps(summary['all']),flush=True)
        return records,summary
    results={};recordsets={}
    for label,weights in [('original_initial',ROOT/'initialization/yolov5n_road4.pt'),('original_finetuned',candidate)]:
        recordsets[label],results[label]=evaluate(weights,label,original)
    frames=OUT/'enhancement_inputs';frames.mkdir()
    enhancement_rows=[]
    def enhance(r):
        stem=Path(r['name']).stem;rgb=cv2.resize(original(r),(400,240),interpolation=cv2.INTER_LINEAR)[:,:,::-1].copy()
        rgb[:,:,0]&=248;rgb[:,:,1]&=252;rgb[:,:,2]&=248
        ip=frames/(stem+'.rgb');op=frames/(stem+'.net.rgb');ip.write_bytes(rgb.tobytes())
        p=subprocess.run([str(REFERENCE),str(ip),'240','400',str(op)],capture_output=True,text=True)
        assert p.returncode==0 and 'MULTINEX_CPP_DONE' in p.stdout,p.stderr
        net=np.fromfile(op,np.uint8).reshape(240,400,3)
        y=(rgb.astype(np.uint32)*np.array([54,183,19],np.uint32)).sum(2);mean=int((((y+128)>>8).sum()+48000)//96000)
        alpha=256 if mean<=32 else (0 if mean>=48 else ((48-mean)*256+8)//16)
        protected=((rgb.astype(np.uint32)*(256-alpha)+net.astype(np.uint32)*alpha+128)>>8).astype(np.uint8)
        gamma=np.clip(np.floor(np.sqrt(rgb.astype(np.float32)/255)*255+.5),0,255).astype(np.uint8)
        for kind,a in [('raw400',rgb),('multinex400',net),('protected400',protected),('gamma400',gamma)]:
            assert cv2.imwrite(str(frames/(stem+'.'+kind+'.png')),a[:,:,::-1])
        return dict(name=r['name'],mean_luma=mean,alpha=alpha,input_sha256=sha(ip),network_output_sha256=sha(op))
    with cf.ThreadPoolExecutor(4) as pool:
        for i,d in enumerate(pool.map(enhance,rows),1):
            enhancement_rows.append(d)
            if i%50==0:print('FROZEN_ENHANCER_REFERENCES_PREPARED',i,len(rows),flush=True)
    write(OUT/'enhancement_manifest.json',enhancement_rows)
    for view in ['raw400','multinex400','protected400','gamma400']:
        recordsets[view],results[view]=evaluate(candidate,view,lambda r,v=view:cv2.imread(str(frames/(Path(r['name']).stem+'.'+v+'.png'))))
    changes={}
    for view in ['multinex400','protected400','gamma400']:
        table={}
        for period in ['all','night','dawn/dusk','daytime']:
            recovered=[0]*4;lost=[0]*4
            for a,b in zip(recordsets['raw400'],recordsets[view]):
                assert a['name']==b['name']
                if period!='all' and a['timeofday']!=period:continue
                for k in b['matched_gt']-a['matched_gt']:recovered[int(a['truth'][k,0])]+=1
                for k in a['matched_gt']-b['matched_gt']:lost[int(a['truth'][k,0])]+=1
            table[period]=dict(recovered=dict(zip(NAMES,recovered)),lost=dict(zip(NAMES,lost)))
        changes[view]=table
    result=dict(status='FROZEN_ROAD_MODEL_EVALUATED_ON_REAL_BDD_TEST_AND_ENHANCEMENT_CONTROLS',candidate_sha256=sha(candidate),
                validation_accepted=frozen['validation_acceptance'],test_images=len(rows),results=results,enhancement_recovered_lost=changes,
                tests_are_real_low_light=True,synthetic_darkening_used_in_test=False,board_deployed=False,sd_written=False,
                processing='Detector on PC RTX4060. Enhancement on frozen bit-equivalent C++ CPU reference; not actual road-image board capture.',
                note='Tiny400 views compared only to raw400. Original1280x720 views separately compare transfer vs fine-tuning. Speed is PC GPU forward only, not board FPS or end-to-end latency.')
    write(OUT/'results.json',result);print('ROAD_FROZEN_EVALUATION_COMPLETE',str(OUT/'results.json'),flush=True)
if __name__=='__main__':main()
