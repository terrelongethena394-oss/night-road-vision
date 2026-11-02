"""Transfer exact COCO head rows to four BDD classes and audit a forward pass."""
from pathlib import Path
import copy,hashlib,json,sys
ROOT=Path('E:/FPGA_Enhance_Work/road_detection_20261026')
SOURCE=ROOT/'yolov5'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    patches=[]
    for name in ['train.py','models/experimental.py','utils/general.py']:
        p=SOURCE/name;s=p.read_text(encoding='utf-8');old=sha(p)
        s=s.replace("torch.load(weights, map_location='cpu')","torch.load(weights, map_location='cpu', weights_only=False)")
        s=s.replace("torch.load(last, map_location='cpu')","torch.load(last, map_location='cpu', weights_only=False)")
        s=s.replace("torch.load(attempt_download(w), map_location='cpu')","torch.load(attempt_download(w), map_location='cpu', weights_only=False)")
        s=s.replace("torch.load(f, map_location=torch.device('cpu'))","torch.load(f, map_location=torch.device('cpu'), weights_only=False)")
        p.write_text(s,encoding='utf-8');patches.append(dict(file=name,before=old,after=sha(p)))
    sys.path.insert(0,str(SOURCE))
    import torch
    from models.yolo import Model
    torch.set_num_threads(4);torch.manual_seed(2026102621)
    records=json.loads((ROOT/'assets.json').read_text())['assets'];record=next(r for r in records if r['file']=='yolov5n.pt')
    assert sha(ROOT/'assets/yolov5n.pt')==record['sha256']
    pretrained=torch.load(ROOT/'assets/yolov5n.pt',map_location='cpu',weights_only=False)['model'].float().eval()
    config=copy.deepcopy(pretrained.yaml);config['nc']=4
    model=Model(config,ch=3,nc=4).float().eval()
    original=pretrained.state_dict();target=model.state_dict()
    inherited={k:v for k,v in original.items() if k in target and v.shape==target[k].shape}
    model.load_state_dict(inherited,strict=False)
    # YOLO anchor rows contain [box4,objectness,classes]. Preserve matching COCO classes.
    indices=[0,1,2,3,4,5+0,5+2,5+7,5+5]  # person, car, truck, bus
    with torch.no_grad():
        for old,new in zip(pretrained.model[-1].m,model.model[-1].m):
            new.weight.copy_(old.weight.reshape(3,85,*old.weight.shape[1:])[:,indices].reshape_as(new.weight))
            new.bias.copy_(old.bias.reshape(3,85)[:,indices].reshape_as(new.bias))
    model.names=['person','car','truck','bus'];model.nc=4
    x=torch.rand(1,3,416,416)
    with torch.inference_mode():
        y0=pretrained(x)[0][:,:,indices];y1=model(x)[0]
    assert y0.shape==y1.shape
    error=(y0-y1).abs().max().item();assert torch.allclose(y0,y1,atol=.005,rtol=.0001),error
    init=ROOT/'initialization';init.mkdir(exist_ok=True)
    output=init/'yolov5n_road4.pt';assert not output.exists()
    torch.save(dict(epoch=-1,best_fitness=0.,model=model.half(),ema=None,updates=0,optimizer=None,opt={},git={},date='2026-10-26'),output)
    proof=dict(status='FOUR_CLASS_INITIALIZATION_TRANSFER_AND_FORWARD_VERIFIED',architecture='YOLOv5n v7.0',parameters=sum(p.numel() for p in model.parameters()),
               source_weight_sha256=record['sha256'],source_url=record['url'],four_class_weight_sha256=sha(output),class_names=model.names,
               coco_class_ids=[0,2,7,5],head_transfer_indices=indices,input_shape=list(x.shape),output_shape=list(y1.shape),max_absolute_forward_difference=error,
               source_compatibility_patches=patches,patch_reason='Explicit weights_only=False only for pinned official and own YOLOv5 checkpoints under PyTorch2.7; no architecture/loss changes.',
               training_started=False,sd_written=False,board_modified=False)
    (init/'transfer_proof.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    print('FOUR_CLASS_DETECTOR_INITIALIZED',json.dumps(proof),flush=True)
if __name__=='__main__':main()
