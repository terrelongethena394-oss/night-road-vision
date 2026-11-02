"""Train three narrower students with supervised GT plus modest teacher guidance.
All teacher inference for distillation is on augmented TRAIN batches only.
"""
import csv,json,math,os,shutil,sys,time
from pathlib import Path
from road_light_common import ROOT,BASE,TEACHER,TEACHER_SHA,NAMES,SEED,VARIANTS,EPOCHS,read,write,sha
def main():
    t=time.monotonic()
    while not (ROOT/'prepare_complete.json').exists():
        if time.monotonic()-t>1800:raise TimeoutError('Light preparation not ready')
        time.sleep(2)
    assert sha(TEACHER)==TEACHER_SHA
    os.environ['YOLOv5_AUTOINSTALL']='false';os.environ['WANDB_DISABLED']='true';os.environ['COMET_MODE']='DISABLED';os.environ['YOLOV5_CONFIG_DIR']=str(ROOT/'config')
    (ROOT/'config').mkdir(exist_ok=True);shutil.copy2('C:/Windows/Fonts/arial.ttf',ROOT/'config/Arial.ttf')
    os.chdir(ROOT/'yolov5');sys.path.insert(0,str(ROOT/'yolov5'))
    import torch,yaml
    import torch.nn.functional as F
    import train
    from utils.loss import ComputeLoss
    torch.set_num_threads(4)
    teacher=torch.load(TEACHER,map_location='cpu',weights_only=False)['model'].float().cuda().eval().requires_grad_(False)
    for tag in VARIANTS:
        initial=ROOT/'initialization'/tag/'initial.pt';proof=read(initial.parent/'proof.json');assert sha(initial)==proof['initial_sha256']
        assert not (ROOT/'runs'/tag).exists();history=[];count={'calls':0,'positive_anchors':0}
        class StudentLoss(ComputeLoss):
            def __call__(self,p,targets,images=None):
                base,items=super().__call__(p,targets)
                if images is None or not any(v.requires_grad for v in p):return base,items
                with torch.no_grad():raw=teacher(images)[1]
                assert len(raw)==len(p)==3
                kd=base.new_zeros((),dtype=torch.float32);positive=0
                for student,guide in zip(p,raw):
                    assert student.shape==guide.shape
                    s=student.float();g=guide.detach().float();prob=g.sigmoid();mask=(prob[...,4]>.3)&(prob[...,5:].amax(-1)>.5)
                    n=int(mask.sum());positive+=n
                    if n:
                        kd=kd+(.5*F.binary_cross_entropy_with_logits(s[...,4][mask],prob[...,4][mask])+
                               .5*F.binary_cross_entropy_with_logits(s[...,5:][mask],prob[...,5:][mask])+
                               .25*F.smooth_l1_loss(s[...,:4][mask].sigmoid(),prob[...,:4][mask]))/3
                progress=min(1.,count['calls']/(150*EPOCHS));weight=.02+.10*(1-progress)
                loss=base+weight*kd*images.shape[0]
                assert torch.isfinite(loss)
                count['calls']+=1;count['positive_anchors']+=positive
                if count['calls']%600==0:
                    history.append(dict(step=count['calls'],lambda_kd=weight,kd_loss_unscaled=float(kd.detach()),supervised_loss=float(base.detach()),positive_anchors_this_batch=positive))
                    write(ROOT/(tag+'_kd_history.json'),history);print('LIGHT_KD_PROGRESS',tag,history[-1],flush=True)
                return loss,items
        train.ComputeLoss=StudentLoss
        hyp=yaml.safe_load((BASE/'road_hyp.yaml').read_text());hyp.update(lr0=.001,lrf=.1,warmup_epochs=1.,warmup_bias_lr=.001,mosaic=.25,hsv_v=.10)
        hp=ROOT/(tag+'_hyp.yaml');hp.write_text(yaml.safe_dump(hyp),encoding='ascii')
        write(ROOT/(tag+'_training_protocol.json'),dict(status='FROZEN_BEFORE_STUDENT_GRADIENTS',variant=tag,width=VARIANTS[tag],epochs=EPOCHS,batch=16,imgsz=320,
          seed=SEED,initial_sha256=sha(initial),teacher_sha256=TEACHER_SHA,hyp=hyp,anchors='Copied teacher anchors, autoanchor disabled for matched head guidance',
          distillation='Teacher eval no-grad on current TRAIN augmented images only. Select teacher sigmoid(obj)>.3 and max(sigmoid(class))>.5. Mean across heads of .5objBCE+.5classBCE+.25sigmoid(box)SmoothL1. Lambda .12 linearly to.02 over6000steps. Scale bybatch like YOLO supervised loss.',
          csv_loss_note='YOLO three logged training loss components are supervised only; distillation recorded separately. No ablation claim attributing all differences to KD.',
          validation='Precomputed square320 images, exact same camera-order and explicit C resize. Default upstream validation checkpoint fitness; periodic checkpoints also searched later on old validation.',
          no_fresh_test_access=True,no_hardware_access=True))
        print('LIGHT_STUDENT_TRAINING_STARTED',tag,flush=True);start=time.monotonic()
        train.run(weights=str(initial),data=str(ROOT/'dataset/road4.yaml'),hyp=str(hp),epochs=EPOCHS,batch_size=16,imgsz=320,
                  optimizer='AdamW',workers=0,project=str(ROOT/'runs'),name=tag,exist_ok=False,noplots=True,patience=EPOCHS,
                  seed=SEED,image_weights=True,noautoanchor=True,device='0',cos_lr=True,save_period=10)
        run=ROOT/'runs'/tag
        with (run/'results.csv').open() as f:rows=[{k.strip():float(v) for k,v in r.items()} for r in csv.DictReader(f)]
        assert len(rows)==EPOCHS and all(all(math.isfinite(v) for v in r.values()) for r in rows)
        dest=ROOT/'frozen'/tag;dest.mkdir(parents=True,exist_ok=False)
        for p in sorted((run/'weights').glob('*.pt')):shutil.copy2(p,dest/p.name)
        write(dest/'complete.json',dict(status='ALL_STUDENT_CHECKPOINTS_FROZEN_BEFORE_POLICY_SELECTION_AND_FRESH_TEST',variant=tag,epochs=EPOCHS,
              seconds=time.monotonic()-start,weights={p.name:sha(p) for p in dest.glob('*.pt')},kd_count=count,kd_history=history,
              initialization=proof,no_fresh_test_inference=True,no_board_write=True))
        print('LIGHT_STUDENT_COMPLETE',tag,time.monotonic()-start,flush=True)
    write(ROOT/'training_complete.json',dict(status='ALL_THREE_STUDENTS_40_EPOCHS_COMPLETE',variants=list(VARIANTS),no_fresh_test_inference=True,no_board_write=True))
    print('ALL_LIGHT_STUDENTS_TRAINED',flush=True)
if __name__=='__main__':main()
