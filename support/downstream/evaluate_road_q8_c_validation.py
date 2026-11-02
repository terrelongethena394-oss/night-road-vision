"""Actual deployed C semantics on all OLD validation images, no test selection leak."""
from pathlib import Path
import subprocess,time,concurrent.futures as cf
import cv2,numpy as np
from road_integer_common import ROOT,LIGHT,FLOAT,read,write,sha

def main():
    out=ROOT/'c_validation320';out.mkdir(exist_ok=False);folder=ROOT/'m125';exe=folder/'fast_r1/road_ap.exe';model=folder/'qmodel.bin'
    from road_light_evaluate import validation_rows
    rows=validation_rows();(out/'inputs').mkdir();(out/'outputs').mkdir();records=[];predictions={};start=time.monotonic()
    write(out/'protocol.json',dict(status='OLD_VALIDATION_ACTUAL_C_CHECK_FROZEN',images=320,model_sha256=sha(model),exe_sha256=sha(exe),confidence_floor=.001,nms_iou=.6,not_new_test=True))
    def one(r):
        stem=Path(r['name']).stem;a=cv2.imread(str(LIGHT/'raw400/val'/(stem+'.png')))[:,:,::-1]
        words=a[:,:,0].astype(np.uint32)|(a[:,:,1].astype(np.uint32)<<8)|(a[:,:,2].astype(np.uint32)<<16);ip=out/'inputs'/(stem+'.u32');words.astype('<u4').tofile(ip)
        d=out/'outputs'/stem;d.mkdir();p=subprocess.run([str(exe),str(model),str(ip),str(d)],capture_output=True,text=True,check=True)
        assert 'ROAD_FP32_HOST_DONE' in p.stdout
        assert (d/'input320.rgb').read_bytes()==cv2.imread(str(LIGHT/'dataset/images/val'/(stem+'.png')))[:,:,::-1].copy().tobytes()
        pred=np.fromfile(d/'boxes400.f32','<f4').reshape(-1,6);assert np.isfinite(pred).all()
        return r['name'],pred.tolist(),dict(name=r['name'],input_sha256=sha(ip),stdout=p.stdout.strip())
    with cf.ThreadPoolExecutor(2) as pool:
        for i,(name,pred,record) in enumerate(pool.map(one,rows),1):
            predictions[name]=pred;records.append(record)
            if i%40==0:print('ACTUAL_Q8_C_VALIDATION',i,flush=True)
    from road_adapt_eval_core import evaluate_serial_predictions
    metrics=evaluate_serial_predictions(rows,predictions,out,'q8_c');ref=read(ROOT/'validation_r1/m125/m125_metrics.json')
    write(out/'complete.json',dict(status='ACTUAL_Q8_C_ALL320_OLD_VALIDATION_COMPLETE',metrics=metrics,runs=records,seconds=time.monotonic()-start,
       reference_night_ap=ref['by_time']['night']['mAP50'],actual_c_night_ap=metrics['by_time']['night']['mAP50'],board_accessed=False,sd_written=False))
    print('ACTUAL_Q8_C_VALIDATION_COMPLETE',metrics['all']['mAP50'],metrics['by_time']['night']['mAP50'],flush=True)
if __name__=='__main__':main()
