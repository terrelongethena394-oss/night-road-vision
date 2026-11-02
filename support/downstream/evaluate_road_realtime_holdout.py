"""One-shot final comparison after QAT checkpoint choice is frozen on old validation."""
from pathlib import Path
import hashlib,json,os,sys,time
ROOT=Path('E:/FPGA_Enhance_Work/road_realtime_20261027')
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    started=time.monotonic()
    while not ((ROOT/'selection_complete.json').exists() and (ROOT/'fresh/complete.json').exists()):
        if time.monotonic()-started>3600:raise TimeoutError('Selection or frozen data not ready')
        time.sleep(2)
    selection=json.loads((ROOT/'selection_complete.json').read_text());epoch=selection['selected_epoch']
    if epoch is None:print('NO_QAT_CANDIDATE_PASSED_OLD_GATES_NO_FRESH_INFERENCE');return
    folder=ROOT/'exports'/f'epoch{epoch}';assert sha(folder/'qmodel.bin')==selection['selected_qmodel_sha256']
    # This freezes checkpoint selection before either model sees fresh results.
    freeze=dict(status='CANDIDATE_FROZEN_BEFORE_NEW_HOLDOUT_INFERENCE',selected_epoch=epoch,qmodel_sha256=sha(folder/'qmodel.bin'),selection_sha256=sha(ROOT/'selection_complete.json'),data_sha256=sha(ROOT/'fresh/manifest.json'),protocol_sha256=sha(ROOT/'fresh_protocol.json'))
    (ROOT/'final_candidate_frozen.json').write_text(json.dumps(freeze,indent=2),encoding='utf-8')
    import cv2,numpy as np,torch
    from prepare_road_light import sensor_proxy
    from road_arm_common import preprocess400
    from road_integer_reference import evaluate
    from road_adapt_eval_core import evaluate_serial_predictions
    from utils.general import non_max_suppression,scale_boxes
    rows=[{**r,'label_path':str(ROOT/'fresh/labels'/(Path(r['name']).stem+'.txt'))} for r in json.loads((ROOT/'fresh/manifest.json').read_text())]
    def loader(r):return preprocess400(sensor_proxy(cv2.imread(str(ROOT/'fresh/images'/r['name']))[:,:,::-1].copy()))
    out=ROOT/'final_holdout_r1';out.mkdir(exist_ok=False);(out/'teacher').mkdir();(out/'qat').mkdir()
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.set_num_threads(4)
    teacher_path=Path('E:/FPGA_Enhance_Work/road_detection_20261026/frozen/road4_best.pt')
    teacher=torch.load(teacher_path,map_location='cpu',weights_only=False)['model'].float().fuse().cuda().eval();predictions={}
    with torch.inference_mode():
        for at in range(0,len(rows),8):
            batch=rows[at:at+8];x=torch.from_numpy(np.stack([loader(r).transpose(2,0,1) for r in batch])).cuda().float()/255
            pred=non_max_suppression(teacher(x),.001,.6,max_det=300)
            for r,p in zip(batch,pred):
                if len(p):scale_boxes((320,320),p[:,:4],(240,400),ratio_pad=((.8,.8),(0.,64.)))
                predictions[r['name']]=p.cpu().float().tolist()
            if (at+8)%80==0:print('REALTIME_FRESH_TEACHER_PROGRESS',at+8,flush=True)
    baseline=evaluate_serial_predictions(rows,predictions,out/'teacher','teacher');del teacher;torch.cuda.empty_cache()
    quant=evaluate(folder,rows,loader,out/'qat','qat')
    a=quant['by_time']['night'];b=baseline['by_time']['night'];pa=a['classes']['person'];pb=b['classes']['person']
    tests=dict(night_ap=a['mAP50']>=.95*b['mAP50'],all_ap=quant['all']['mAP50']>=.97*baseline['all']['mAP50'],person_recall=pa['recall']>=.9*pb['recall'],night_fp=sum(v['fp'] for v in a['classes'].values())<=1.1*sum(v['fp'] for v in b['classes'].values())+2,person_fp=pa['fp']<=1.1*pb['fp']+2)
    result=dict(status='NEW480_HOLDOUT_EVALUATED_AFTER_CHECKPOINT_FREEZE',teacher=baseline,qat=quant,gates=tests,passed=all(tests.values()),frozen_candidate=freeze,baseline_precision='FP32 fused teacher CUDA TF32 disabled; QAT exact integer convolution reference with FP32 final heads',hardware_access=False,sd_written=False,board_fps_measured=False,current_deployed_model_replaced=False)
    (ROOT/'final_holdout_complete.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('ROAD_REALTIME_FRESH_HOLDOUT_COMPLETE',tests,'passed',all(tests.values()),flush=True)
if __name__=='__main__':main()
