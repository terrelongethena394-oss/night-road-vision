"""Resolution/weight-only sensitivity evaluator; same boxes and matching as round2."""
from pathlib import Path
import time
import numpy as np
from road_adapt_common import NAMES,write
from road_adapt_eval_core import (Evaluator,torch,letterbox,non_max_suppression,scale_boxes,
                                  truth,process_batch,matched_indices,metrics)

class PipelineEvaluator(Evaluator):
    @torch.inference_mode()
    def run(self,rows,rgb_loader,folder,tag,size=416):
        folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);records=[];forward=0.
        for at in range(0,len(rows),16):
            rs=rows[at:at+16];images=[rgb_loader(r) for r in rs];padded=[];transforms=[]
            for image in images:
                assert image.shape==(240,400,3)
                a,ratio,pad=letterbox(image,(size,size),auto=False,stride=32)
                padded.append(a.transpose(2,0,1));transforms.append((ratio,pad))
            x=torch.from_numpy(np.ascontiguousarray(np.stack(padded))).to(self.device).half()/255
            torch.cuda.synchronize();t=time.monotonic();output=self.model(x);torch.cuda.synchronize();forward+=time.monotonic()-t
            preds=non_max_suppression(output,.001,.6,max_det=300)
            for r,image,pred,transform in zip(rs,images,preds,transforms):
                if len(pred):scale_boxes(x.shape[2:],pred[:,:4],image.shape,ratio_pad=transform)
                labels=torch.from_numpy(truth(r,400,240)).to(self.device)
                correct=process_batch(pred,labels,self.iouv).cpu().numpy();op=pred[pred[:,4]>=.25]
                opcorrect=process_batch(op,labels,self.iouv[:1]).cpu().numpy()[:,0];matched=matched_indices(op,labels)
                assert int(opcorrect.sum())==len(matched)
                records.append(dict(name=r['name'],timeofday=r['timeofday'],pred=pred.cpu().numpy(),truth=labels.cpu().numpy(),correct=correct,
                                    op_pred=op.cpu().numpy(),op_correct=opcorrect,matched_gt=matched))
        result=dict(all=metrics(records),by_time={p:metrics([r for r in records if r['timeofday']==p]) for p in ['night','dawn/dusk','daytime']},
                    gpu_forward_ms=forward/len(rows)*1000,detector_size=size,arithmetic='GPU float16, including when weights were INT8-round/dequant simulated')
        serial=[dict(name=r['name'],timeofday=r['timeofday'],detections=r['pred'].tolist(),ground_truth=r['truth'].tolist(),correct=r['correct'].tolist(),matched_gt=sorted(r['matched_gt'])) for r in records]
        write(folder/(tag+'_metrics.json'),result);write(folder/(tag+'_predictions.json'),serial)
        print('PIPELINE_VIEW_EVALUATED',tag,'night',result['by_time']['night']['mAP50'],flush=True)
        return result

def quantize_conv_weights(evaluator,destination):
    """Per-output-channel symmetric INT8 weights only, dequantized for GPU checks."""
    tensors={};rows=[]
    for name,module in evaluator.model.model.named_modules():
        if not isinstance(module,torch.nn.Conv2d):continue
        w=module.weight.detach().float();scale=w.abs().flatten(1).amax(1).clamp(min=1e-12)/127
        q=torch.round(w/scale[:,None,None,None]).clamp(-127,127).to(torch.int8)
        restored=q.float()*scale[:,None,None,None]
        with torch.no_grad():module.weight.copy_(restored.to(module.weight.dtype))
        tensors[name+'.weight_int8']=q.cpu().numpy();tensors[name+'.scale']=scale.cpu().numpy()
        if module.bias is not None:tensors[name+'.bias_float32']=module.bias.detach().float().cpu().numpy()
        rows.append(dict(name=name,shape=list(w.shape),weight_bytes_int8=w.numel(),max_abs_error=float((w-restored).abs().max())))
    np.savez_compressed(destination,**tensors)
    return dict(status='WEIGHT_ONLY_INT8_ROUND_DEQUANT_SENSITIVITY_NOT_INTEGER_RUNTIME',convs=rows,
                activation_quantized=False,bias_dtype='float32',rounding='torch.round ties to even',
                gpu_compute_dtype='float16',board_runtime_exported=False,conv_weight_bytes=sum(r['weight_bytes_int8'] for r in rows))
