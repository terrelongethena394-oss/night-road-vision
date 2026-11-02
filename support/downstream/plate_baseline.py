"""Full-string OCR baseline and batch-contract audit on upstream sample crops."""
import json,time
import numpy as np
import torch,cv2
from PIL import Image
from plate_common import ROOT,SOURCE,SEED,CHARS,build_model,forward_per_image,decode,edit_distance,sha,write
def bgr_image(path):return np.array(Image.open(path).convert('RGB'))[:,:,::-1].copy()
def tensor(x):return torch.from_numpy(((x.astype(np.float32)-127.5)/128).transpose(0,3,1,2).copy())
@torch.inference_mode()
def evaluate(model,images,texts):
    pred=[];start=time.monotonic()
    for i in range(0,len(images),16):pred.extend(decode(forward_per_image(model,tensor(images[i:i+16]))))
    return dict(n=len(texts),full_plate_correct=sum(a==b for a,b in zip(pred,texts)),full_plate_accuracy=float(np.mean([a==b for a,b in zip(pred,texts)])),character_error_rate=sum(edit_distance(a,b) for a,b in zip(pred,texts))/sum(map(len,texts)),seconds=time.monotonic()-start),pred
def main():
    out=ROOT/'upstream_baseline';out.mkdir(exist_ok=True);assert not (out/'results.json').exists()
    torch.set_num_threads(4);model=build_model();model.eval()
    paths=sorted((SOURCE/'data/test').glob('*.jpg'));texts=[p.stem.split('-')[0].split('_')[0] for p in paths]
    assert all(len(t) in [7,8] and all(c in CHARS for c in t) for t in texts)
    images=np.stack([cv2.resize(bgr_image(p),(94,24)) for p in paths]);z=tensor(images[:4])
    with torch.inference_mode():
        expected=torch.cat([model(q[None]) for q in z]);batched=forward_per_image(model,z)
        delta=float((expected-batched).abs().max());assert torch.allclose(expected,batched,atol=2e-4,rtol=1e-4),delta
    write(out/'batch_contract.json',dict(status='PER_IMAGE_BATCHING_MATCHES_UPSTREAM_BATCH1',max_absolute_logit_difference=delta,upstream_issue='Original global energy normalization shares a scalar across images in a batch. Evaluation here normalizes each image independently, matching batch1 deployment.',upstream_commit='7c976664b3f3879efabeaff59c7a117e49d5f29e',weights_sha256=sha(SOURCE/'weights/Final_LPRNet_model.pth')))
    results={};predictions={};rng=np.random.default_rng(SEED)
    for gain in [1.,.25,.125]:
        v=np.clip(np.floor(images.astype(np.float32)*gain+.5),0,255).astype(np.uint8)
        report,pred=evaluate(model,v,texts);key='gain'+str(gain);results[key]=report;predictions[key]=pred;print('PLATE_BASELINE',key,json.dumps(report),flush=True)
    records=[dict(file=str(p),truth=t,**{k:v[i] for k,v in predictions.items()}) for i,(p,t) in enumerate(zip(paths,texts))]
    # MAC count from actual layer shapes, not an assumed hardware frame rate.
    macs=[];hooks=[]
    for name,layer in model.named_modules():
        if isinstance(layer,torch.nn.Conv2d):
            def hook(module,args,output,name=name):macs.append(dict(layer=name,output_shape=list(output.shape),macs=output.numel()*(module.in_channels//module.groups)*module.kernel_size[0]*module.kernel_size[1]))
            hooks.append(layer.register_forward_hook(hook))
    with torch.inference_mode():model(z[:1])
    for hook in hooks:hook.remove()
    write(out/'results.json',dict(status='PC_PRETRAINED_CROP_OCR_BASELINE_NOT_BOARD_VERIFIED',results=results,cases=records,parameters=sum(p.numel() for p in model.parameters()),conv_macs=sum(r['macs'] for r in macs),layers=macs,source='https://github.com/sirius-ai/LPRNet_Pytorch',limitations=['Upstream demonstration crops may overlap upstream pretraining; this is regression, not blind accuracy.','Given cropped plate, not automatic full-scene detection.','Artificial RGB gain is not real night illumination.','No new training or board deployment in this baseline.','No assertion that enhancement improves OCR.']))
    print('PLATE_BASELINE_COMPLETE',len(paths),sum(r['macs'] for r in macs),flush=True)
if __name__=='__main__':main()
