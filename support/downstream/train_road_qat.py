"""Train fixed 8-epoch QAT recovery; only training data may affect gradients."""
from pathlib import Path
import hashlib,json,os,random,shutil,sys,time
ROOT=Path('E:/FPGA_Enhance_Work/road_realtime_20261027')
LIGHT=Path('E:/FPGA_Enhance_Work/road_light_20261027')
BASE=Path('E:/FPGA_Enhance_Work/road_detection_20261026')
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):Path(p).write_text(json.dumps(d,indent=2,ensure_ascii=False),encoding='utf-8')
def main():
    ROOT.mkdir(exist_ok=False);source=ROOT/'source';source.mkdir()
    for n in ['train_road_qat.py','road_qat_graph.py']:shutil.copy2(HERE/n,source/n)
    os.environ.update(YOLOv5_AUTOINSTALL='false',WANDB_DISABLED='true',COMET_MODE='DISABLED',YOLOV5_CONFIG_DIR=str(ROOT/'config'))
    (ROOT/'config').mkdir();shutil.copy2('C:/Windows/Fonts/arial.ttf',ROOT/'config/Arial.ttf')
    sys.path.insert(0,str(LIGHT/'yolov5'))
    import numpy as np,torch,yaml
    from road_qat_graph import QATGraph
    from utils.dataloaders import create_dataloader
    from utils.loss import ComputeLoss
    seed=2026102731;random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed);torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cudnn.benchmark=False
    manifest=json.loads((LIGHT/'dataset/manifest.json').read_text());groups={s:{r['group'] for r in manifest if r['split']==s} for s in ['train','val']}
    assert len([r for r in manifest if r['split']=='train'])==2400 and len([r for r in manifest if r['split']=='val'])==320
    assert not groups['train']&groups['val']
    # Hardlinks on E: keep source images untouched and do not duplicate their payload.
    for r in manifest:
        split=r['split'];stem=Path(r['name']).stem
        for kind,ext in [('images','.png'),('labels','.txt')]:
            old=LIGHT/'dataset'/kind/split/(stem+ext);new=ROOT/'dataset'/kind/split/old.name;new.parent.mkdir(parents=True,exist_ok=True);os.link(old,new)
    teacher_path=BASE/'frozen/road4_best.pt';assert sha(teacher_path)=='98f46429cd431d735e276d7735f50f61811a70cbb5feb2a0475fba562449a46f'
    teacher=torch.load(teacher_path,map_location='cpu',weights_only=False)['model'].float().eval()
    hyp=yaml.safe_load((BASE/'road_hyp.yaml').read_text());hyp.update(mosaic=.1,hsv_v=.08,scale=.15,translate=.03)
    loss_hyp=dict(hyp);loss_hyp['cls']*=4/80;loss_hyp['obj']*=.25;loss_hyp['label_smoothing']=0.0
    model=QATGraph(teacher,loss_hyp).cuda();loss_fn=ComputeLoss(model)
    protocol=dict(status='FROZEN_BEFORE_QAT_GRADIENTS',seed=seed,epochs=8,checkpoint_epochs=[4,8],batch=8,input=320,learning_rate=1e-5,optimizer='AdamW betas(.9,.999), weight_decay1e-5',amp=False,tf32=False,
        training=2400,old_validation=320,validation_optimizer_access=False,source_manifest_sha256=sha(LIGHT/'dataset/manifest.json'),teacher_sha256=sha(teacher_path),quant_scales_source='m125 train-only calibrated perchannel activation/weight scales, frozen throughout QAT',
        surrogate='STE away-from-zero rounding; signed W8/A8, RGB U8; float32 Conv/SiLU training surrogate. Exact integer exported evaluation required; surrogate is not deployed arithmetic.',
        acceptance='Select only epochs4/8 on OLD validation: nightAP>=.95*teacher, person-night recall>=.9*teacher, allAP>=.97*teacher, nightFP<=1.1*teacher+2, personFP<=1.1*teacher+2. Highest nightAP among passing; otherwise preserve currentFP32. No claim of realtime until full on-board timing.',
        holdout='Previously used480 is not fresh and cannot choose weights. Final independent groups needed after candidate freeze.',hardware_access=False,sd_written=False,source_sha256={p.name:sha(p) for p in source.iterdir()},hyp=hyp,loss_hyp=loss_hyp)
    write(ROOT/'protocol.json',protocol)
    # Inspect construction and gradients before the long training run.
    loader,dataset=create_dataloader(str(ROOT/'dataset/images/train'),320,8,32,hyp=hyp,augment=True,cache=False,workers=0,shuffle=True)
    optimizer=torch.optim.AdamW(model.convs.parameters(),lr=1e-5,betas=(.9,.999),weight_decay=1e-5)
    records=[];steps=0;began=time.monotonic()
    for epoch in range(1,9):
        model.train();sums=np.zeros(3);batches=0
        for images,targets,paths,shapes in loader:
            assert all('/train/' in str(p).replace('\\','/') for p in paths)
            x=images.cuda().float()/255;targets=targets.cuda();optimizer.zero_grad(set_to_none=True)
            output=model(x);loss,items=loss_fn(output,targets)
            assert torch.isfinite(loss);loss.backward();norm=torch.nn.utils.clip_grad_norm_(model.convs.parameters(),10.0);assert torch.isfinite(norm)
            optimizer.step();sums+=items.detach().cpu().numpy();batches+=1;steps+=1
            if steps==1:
                write(ROOT/'gradient_smoke.json',dict(status='INITIAL_WEIGHT_CODES_ALL60_EXACT_AND_FIRST_SUPERVISED_GRADIENT_FINITE',loss=float(loss.detach()),grad_norm=float(norm),raw_shapes=[list(v.shape) for v in output],train_only=True,hardware_access=False))
            if steps%50==0:print('ROAD_QAT_PROGRESS',epoch,steps,round(float(loss.detach()),5),round(time.monotonic()-began,1),flush=True)
        records.append(dict(epoch=epoch,mean_supervised_components=(sums/batches).tolist(),steps=steps,seconds=time.monotonic()-began));write(ROOT/'training_history.json',records)
        if epoch in [4,8]:
            folder=ROOT/f'epoch{epoch}';folder.mkdir();torch.save(dict(state_dict=model.state_dict(),epoch=epoch,steps=steps,protocol_sha256=sha(ROOT/'protocol.json')),folder/'qat_checkpoint.pt');model.fused_weights().astype('<f4').tofile(folder/'qat_fused_weights.f32')
            write(folder/'frozen.json',dict(status='QAT_CHECKPOINT_FROZEN_BEFORE_OLD_VALIDATION',epoch=epoch,checkpoint_sha256=sha(folder/'qat_checkpoint.pt'),weights_sha256=sha(folder/'qat_fused_weights.f32'),hardware_access=False));print('ROAD_QAT_CHECKPOINT_FROZEN',epoch,flush=True)
    write(ROOT/'training_complete.json',dict(status='QAT_8_EPOCHS_COMPLETE_NOT_EVALUATED_NOT_DEPLOYED',history=records,hardware_access=False,sd_written=False));print('ROAD_QAT_TRAINING_COMPLETE',flush=True)
if __name__=='__main__':main()
