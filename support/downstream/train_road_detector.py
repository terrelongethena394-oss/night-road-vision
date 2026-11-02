"""Train only after data audit; freeze validation-selected weights before test."""
from pathlib import Path
import csv,hashlib,json,os,shutil,sys,time
ROOT=Path('E:/FPGA_Enhance_Work/road_detection_20261026')
SEED=2026102621
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    start=time.monotonic()
    print('WAITING_FOR_AUDITED_REAL_BDD_DATA',flush=True)
    while not (ROOT/'dataset/complete.json').exists():
        if time.monotonic()-start>2400:raise TimeoutError('Dataset preparation not complete; no training performed')
        time.sleep(3)
    data=json.loads((ROOT/'dataset/complete.json').read_text())
    assert data['status']=='REAL_BDD_FOUR_CLASS_DATASET_READY' and not data['group_overlap'] and not data['exact_image_overlap']
    transfer=json.loads((ROOT/'initialization/transfer_proof.json').read_text())
    weights=ROOT/'initialization/yolov5n_road4.pt'
    assert sha(weights)==transfer['four_class_weight_sha256']
    assert not (ROOT/'runs/road4_v1').exists(), 'Preserve prior training runs'
    os.environ['YOLOv5_AUTOINSTALL']='false';os.environ['WANDB_DISABLED']='true';os.environ['COMET_MODE']='DISABLED'
    os.environ['YOLOV5_CONFIG_DIR']=str(ROOT/'config')
    os.environ['CUBLAS_WORKSPACE_CONFIG']=':4096:8'
    config=ROOT/'config';config.mkdir(exist_ok=True)
    # Use the installed local font; no online font dependency during validation.
    shutil.copy2('C:/Windows/Fonts/arial.ttf',config/'Arial.ttf')
    os.chdir(ROOT/'yolov5')  # Upstream train.py uses relpath and cannot import across Windows drives.
    sys.path.insert(0,str(ROOT/'yolov5'))
    import torch,yaml
    import train,val
    torch.set_num_threads(4)
    assert torch.cuda.is_available()
    hyp=yaml.safe_load((ROOT/'yolov5/data/hyps/hyp.scratch-low.yaml').read_text())
    hyp.update(lr0=.0005,lrf=.1,momentum=.9,weight_decay=.0005,warmup_epochs=1.,warmup_bias_lr=.0005,hsv_h=.01,hsv_s=.3,hsv_v=.15,translate=.05,scale=.3,mosaic=.5,mixup=0.,copy_paste=0.)
    (ROOT/'road_hyp.yaml').write_text(yaml.safe_dump(hyp),encoding='ascii')
    protocol=dict(status='FROZEN_BEFORE_GRADIENT_TRAINING',architecture='YOLOv5n v7.0, four transferred COCO heads',
                  classes=['person','car','truck','bus'],seed=SEED,epochs_max=24,early_stopping_patience=12,batch_size=16,imgsz=416,optimizer='AdamW',
                  hyperparameters=hyp,dataloader_workers=0,initial_weights_sha256=sha(weights),source_zip_sha256=sha(ROOT/'assets/yolov5_v7.zip'),
                  dataset_manifest_sha256=sha(ROOT/'dataset/manifest.json'),dataset=data,
                  checkpoint_selection='Validation only, upstream fitness=.1*mAP50+.9*mAP50:95. Freeze candidate before first test inference.',
                  validation_acceptance='Candidate validation mAP50:95 at least initialization validation mAP50:95; all classes and failure results reported. No acceptance threshold chosen after test.',
                  evaluation='Same detector size416, NMSIoU.6 and confidence.001 for AP; fixed operating confidence.25, IoU.5; report real night, dawn/dusk and daytime separately.',
                  pretraining='Official COCO pretrained YOLOv5n; no training on test split. Test selection frozen before inference.',
                  augmentation='Real day/night/dawn-dusk training plus mild color/geometry augmentation; no synthetic darkening is labelled as real night.',
                  enhancement_weights_changed=False,processor='RTX4060 laptop GPU for training/inference in this phase',board_deployed=False,sd_written=False)
    write(ROOT/'training_protocol.json',protocol)
    baseline=val.run(data=str(ROOT/'dataset/road4.yaml'),weights=str(weights),batch_size=16,imgsz=416,conf_thres=.001,iou_thres=.6,device='0',workers=0,plots=False,half=True,project=str(ROOT/'baseline'),name='validation_ready',exist_ok=False,verbose=True)
    write(ROOT/'baseline_validation.json',dict(metrics=list(map(float,baseline[0])),per_class_map=list(map(float,baseline[1])),speed_ms=list(map(float,baseline[2]))))
    print('ROAD_GRADIENT_TRAINING_STARTED',json.dumps(dict(device=torch.cuda.get_device_name(),images=data['splits']['train']['images'],epochs=24)),flush=True)
    t0=time.monotonic()
    train.run(weights=str(weights),data=str(ROOT/'dataset/road4.yaml'),hyp=str(ROOT/'road_hyp.yaml'),epochs=24,batch_size=16,imgsz=416,
              optimizer='AdamW',workers=0,project=str(ROOT/'runs'),name='road4_v1',exist_ok=False,noplots=True,patience=12,seed=SEED,
              image_weights=True,device='0',cos_lr=True,save_period=6)
    run=ROOT/'runs/road4_v1'
    with (run/'results.csv').open() as f:raw=list(csv.DictReader(f))
    rows=[{k.strip():float(v) for k,v in r.items()} for r in raw]
    assert rows and all(all(__import__('math').isfinite(v) for v in r.values()) for r in rows)
    best=max(rows,key=lambda r:.1*r['metrics/mAP_0.5']+.9*r['metrics/mAP_0.5:0.95'])
    frozen=ROOT/'frozen';frozen.mkdir(exist_ok=False);shutil.copy2(run/'weights/best.pt',frozen/'road4_best.pt')
    accepted=best['metrics/mAP_0.5:0.95']>=baseline[0][3]
    result=dict(status='TRAINING_FINISHED_AND_VALIDATION_CANDIDATE_FROZEN_BEFORE_TEST',epochs_completed=len(rows),training_seconds=time.monotonic()-t0,
                initial_validation=baseline[0][:4],selected_validation_row=best,validation_acceptance=bool(accepted),
                model_sha256=sha(frozen/'road4_best.pt'),weights=str(frozen/'road4_best.pt'),test_inference_performed=False,board_deployed=False,sd_written=False)
    write(frozen/'frozen_candidate.json',result);write(ROOT/'training_complete.json',result)
    print('ROAD_TRAINING_COMPLETE',json.dumps(result),flush=True)
if __name__=='__main__':main()
