"""Matched-budget raw vs paired-view adaptation, no fresh-test access."""
from pathlib import Path
import csv,json,math,os,random,shutil,sys,time
from road_adapt_common import BASE,ROOT,SEED,NAMES,read,write,sha,frame_path
def main():
    mode=sys.argv[1];assert mode in ['raw_control','mixed']
    t=time.monotonic()
    while not (ROOT/'prepare_complete.json').exists():
        if time.monotonic()-t>1800:raise TimeoutError('Paired inputs not ready')
        time.sleep(2)
    protocol=read(ROOT/'protocol.json');assert sha(protocol['initialization'])==protocol['initialization_sha256']
    assert not (ROOT/'runs'/mode).exists()
    os.environ['YOLOv5_AUTOINSTALL']='false';os.environ['WANDB_DISABLED']='true';os.environ['COMET_MODE']='DISABLED'
    os.environ['YOLOV5_CONFIG_DIR']=str(ROOT/'config');os.environ['CUBLAS_WORKSPACE_CONFIG']=':4096:8'
    (ROOT/'config').mkdir(exist_ok=True);shutil.copy2('C:/Windows/Fonts/arial.ttf',ROOT/'config/Arial.ttf')
    os.chdir(ROOT/'yolov5');sys.path.insert(0,str(ROOT/'yolov5'))
    import cv2,torch,yaml
    from utils.dataloaders import LoadImagesAndLabels
    import train
    torch.set_num_threads(4)
    original=LoadImagesAndLabels.load_image
    selection_counts={'raw':0,'mild':0,'net':0}
    def paired_load(self,i):
        if not self.augment:return original(self,i)
        u=random.random()  # Consumed in both modes to match augmentation RNG sequences.
        kind='raw' if mode=='raw_control' or u<.5 else ('mild' if u<.8 else 'net')
        p=Path(self.im_files[i]);assert p.parent.name=='train'
        path=frame_path('train',kind,p.name);image=cv2.imread(str(path));assert image.shape==(240,400,3)
        selection_counts[kind]+=1;r=self.img_size/400
        if r!=1:image=cv2.resize(image,(int(400*r),int(240*r)),interpolation=cv2.INTER_LINEAR)
        return image,(240,400),image.shape[:2]
    LoadImagesAndLabels.load_image=paired_load
    hyp=yaml.safe_load((BASE/'road_hyp.yaml').read_text());hyp.update(lr0=.00015,lrf=.2,warmup_epochs=1.,warmup_bias_lr=.00015,mosaic=.25,hsv_v=.10)
    hyp_path=ROOT/(mode+'_hyp.yaml');hyp_path.write_text(yaml.safe_dump(hyp),encoding='ascii')
    write(ROOT/(mode+'_training_protocol.json'),dict(status='FROZEN_BEFORE_MATCHED_ADAPTATION_GRADIENTS',mode=mode,epochs=12,batch=16,imgsz=416,seed=SEED,
          initialization_sha256=protocol['initialization_sha256'],paired_manifest_sha256=sha(ROOT/'paired_manifest.json'),hyp=hyp,
          variant_probabilities={'raw':1.} if mode=='raw_control' else {'raw':.5,'mild':.3,'net':.2},
          labels='Same boxes for same image across all variants. No fresh holdout reads in training.',selection='Raw320 validation fitness only, same selection rule for both candidates.',
          modified_loader='Runtime paired load_image only; exact upstream resize. Same RNG draw count for both modes; no global source edit.',board_deployed=False,sd_written=False))
    print('MATCHED_ADAPTATION_TRAINING_STARTED',mode,flush=True);start=time.monotonic()
    train.run(weights=protocol['initialization'],data=str(ROOT/'dataset/road4.yaml'),hyp=str(hyp_path),epochs=12,batch_size=16,imgsz=416,
              optimizer='AdamW',workers=0,project=str(ROOT/'runs'),name=mode,exist_ok=False,noplots=True,patience=12,seed=SEED,image_weights=True,
              device='0',cos_lr=True,save_period=6)
    run=ROOT/'runs'/mode
    with (run/'results.csv').open() as f:rows=[{k.strip():float(v) for k,v in r.items()} for r in csv.DictReader(f)]
    assert len(rows)==12 and all(all(math.isfinite(v) for v in r.values()) for r in rows)
    frozen=ROOT/'frozen'/mode;frozen.mkdir(parents=True,exist_ok=False);shutil.copy2(run/'weights/best.pt',frozen/'best.pt')
    best=max(rows,key=lambda r:.1*r['metrics/mAP_0.5']+.9*r['metrics/mAP_0.5:0.95'])
    summary=dict(status='MATCHED_CANDIDATE_FROZEN_BEFORE_POLICY_SELECTION_AND_FRESH_TEST',mode=mode,epochs=12,seconds=time.monotonic()-start,
                 weight_sha256=sha(frozen/'best.pt'),best_raw_validation=best,view_load_counts=selection_counts,fresh_test_inference_performed=False,board_deployed=False,sd_written=False)
    write(frozen/'complete.json',summary);print('MATCHED_ADAPTATION_CANDIDATE_FROZEN',json.dumps(summary),flush=True)
if __name__=='__main__':main()
