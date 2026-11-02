"""Matched resolution/weight-only study of the camera-order simulation, val only."""
from pathlib import Path
import cv2
from road_adapt_common import BASE,ROOT as ROUND2,read,write,sha
from road_pipeline_diagnose import ROOT
def main():
    camera=ROOT/'camera_order';assert read(camera/'complete.json')['no_new_test']
    out=camera/'resolution';out.mkdir(exist_ok=False)
    write(out/'protocol.json',dict(status='FROZEN_BEFORE_CAMERA_ORDER_RESOLUTION_SENSITIVITY',split='Existing320validation',input='sim565, actual quantize-then-average order simulation',
          sizes=[320,256],weight_experiments=['unchanged_GPU_float16','per-output-channel_INT8_weight_round_dequant_GPU_float16'],
          original416_metrics_sha256=sha(camera/'sim565_metrics.json'),no_test_used=True,no_board_runtime=True))
    rows=[{**r,'label_path':str(BASE/'dataset/labels/val'/(Path(r['name']).stem+'.txt'))} for r in read(ROUND2/'paired_manifest.json') if r['split']=='val']
    from road_pipeline_eval import PipelineEvaluator,quantize_conv_weights
    ev=PipelineEvaluator(BASE/'frozen/road4_best.pt');scores={}
    loader=lambda r:cv2.imread(str(camera/'frames'/(Path(r['name']).stem+'.sim565.png')))[:,:,::-1].copy()
    for size in [320,256]:scores['sim565_'+str(size)]=ev.run(rows,loader,out,'sim565_'+str(size),size)
    proof=quantize_conv_weights(ev,out/'weight8sim.npz');write(out/'weight8sim_proof.json',proof)
    for size in [320,256]:scores['sim565_weight8sim_'+str(size)]=ev.run(rows,loader,out,'sim565_weight8sim_'+str(size),size)
    ev.close();write(out/'complete.json',dict(status='CAMERA_ORDER_RESOLUTION_WEIGHT_SENSITIVITY_COMPLETE',scores=scores,no_test_used=True,activation_quantized=False,no_board_run=True))
    print('CAMERA_ORDER_RESOLUTION_SENSITIVITY_COMPLETE',flush=True)
if __name__=='__main__':main()
