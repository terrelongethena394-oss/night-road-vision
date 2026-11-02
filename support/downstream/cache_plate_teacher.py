"""Compute teacher on TRAIN only; validation separately for an honest baseline."""
import json,time
import numpy as np
import torch
from plate_common import ROOT,SOURCE,SEED,sha,write,build_model,forward_per_image,decode
def main():
    out=ROOT/'teacher_cache';out.mkdir(exist_ok=True);torch.set_num_threads(4)
    model=build_model().eval();device='cuda' if torch.cuda.is_available() else 'cpu';model.to(device)
    if device=='cuda':torch.backends.cudnn.benchmark=True
    start=time.monotonic()
    for split in ['validation','train']:
        target=out/(split+'.npz')
        if target.exists():continue
        d=np.load(ROOT/f'data/{split}.npz');images=d['teacher'];truth=d['texts'].tolist();scores=[];pred=[]
        with torch.inference_mode():
            for i in range(0,len(images),16):
                a=torch.from_numpy(((images[i:i+16].astype(np.float32)-127.5)/128).transpose(0,3,1,2).copy()).to(device)
                z=forward_per_image(model,a);scores.append(z.cpu().numpy());pred.extend(decode(z))
                if i%512==0:print('TEACHER_CACHE',split,i,len(images),device,round(time.monotonic()-start,1),flush=True)
        z=np.concatenate(scores);correct=np.array([a==b for a,b in zip(pred,truth)])
        np.savez_compressed(target,logits=z,correct=correct,predictions=np.array(pred),texts=np.array(truth))
        write(out/(split+'_summary.json'),dict(n=len(truth),correct=int(correct.sum()),full_plate_accuracy=float(correct.mean()),device=device,teacher_weights_sha256=sha(SOURCE/'weights/Final_LPRNet_model.pth'),data_cache_sha256=sha(ROOT/f'data/{split}.npz'),cache_sha256=sha(target)))
        print('TEACHER_GROUP_COMPLETE',split,int(correct.sum()),len(correct),flush=True)
    write(out/'complete.json',dict(status='TRAIN_TEACHER_AND_VALIDATION_BASELINE_READY',test_images_opened=False,board_written=False))
if __name__=='__main__':main()
