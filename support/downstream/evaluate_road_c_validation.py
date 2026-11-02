"""Run the actual C FP32 kernel over all320 old validation images, not a new test."""
from pathlib import Path
import concurrent.futures as cf,subprocess,time,os
import cv2,numpy as np
from road_arm_common import ROOT,DIAG,BASE,read,write,sha
HERE=Path(__file__).resolve().parent
def main():
    proof=read(ROOT/'host_complete_r1.json');source=ROOT/'source_r1';out=ROOT/'validation320';out.mkdir(exist_ok=False)
    rows=[{**r,'label_path':str(BASE/'dataset/labels/val'/(Path(r['name']).stem+'.txt'))} for r in read(Path('E:/FPGA_Enhance_Work/road_joint_adapt_20261026/paired_manifest.json')) if r['split']=='val']
    write(out/'protocol.json',dict(status='FROZEN_BEFORE_C_FULL_VALIDATION',images=320,split='Existing validation only',model_weights_sha256=sha(ROOT/'weights.f32'),
          preprocessing='Current camera-order proxy images, then explicit fixed-coefficient bilinear and padding114',compute='Host SSE2 FP32 C',
          ap_confidence_floor=.001,operation_confidence=.25,nms_iou=.6,maxdet=300,board_run=False,new_independent_test=False))
    assert sha(source/'road_fp32.c')==proof['source_sha256']['road_fp32.c']
    gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=os.environ.copy();env['PATH']=str(gcc.parent)+os.pathsep+env.get('PATH','')
    exe=out/'road_ap.exe';cmd=[str(gcc),'-O3','-std=c99','-msse2','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror','-DROAD_HOST_CONFIDENCE=0.001f','-I'+str(source),str(source/'road_fp32.c'),str(HERE/'road_fp32_host.c'),'-o',str(exe),'-lm']
    p=subprocess.run(cmd,env=env,capture_output=True,text=True);(out/'build.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
    inputs=out/'inputs';inputs.mkdir();outputs=out/'outputs';outputs.mkdir();t=time.monotonic();records=[];predictions={}
    def one(r):
        stem=Path(r['name']).stem;a=cv2.imread(str(DIAG/'camera_order/frames'/(stem+'.sim565.png')))[:,:,::-1]
        words=a[:,:,0].astype(np.uint32)|(a[:,:,1].astype(np.uint32)<<8)|(a[:,:,2].astype(np.uint32)<<16);ip=inputs/(stem+'.u32');words.astype('<u4').tofile(ip)
        folder=outputs/stem;folder.mkdir();start=time.monotonic()
        p=subprocess.run([str(exe),str(ROOT/'weights.f32'),str(ip),str(folder)],capture_output=True,text=True)
        assert p.returncode==0 and 'ROAD_FP32_HOST_DONE' in p.stdout,(r['name'],p.stdout,p.stderr)
        preds=np.fromfile(folder/'boxes400.f32','<f4').reshape(-1,6);assert np.isfinite(preds).all()
        return r['name'],preds.tolist(),dict(name=r['name'],wall_seconds=time.monotonic()-start,input_sha256=sha(ip),stdout=p.stdout.strip())
    with cf.ThreadPoolExecutor(2) as pool:
        for i,(name,preds,record) in enumerate(pool.map(one,rows),1):
            predictions[name]=preds;records.append(record)
            if i%40==0:print('REAL_C_VALIDATION_DONE',i,flush=True)
    from road_adapt_eval_core import evaluate_serial_predictions
    metrics=evaluate_serial_predictions(rows,predictions,out,'c_fp32_320')
    write(out/'complete.json',dict(status='ACTUAL_HOST_C_FP32_ALL320_VALIDATION_IMAGES_EVALUATED',metrics=metrics,seconds=time.monotonic()-t,
          runs=records,compiler_command=cmd,kernel_sha256=sha(source/'road_fp32.c'),weights_sha256=sha(ROOT/'weights.f32'),
          comparison_caveat='Compared with earlier FP16/OpenCV results, both arithmetic precision and resize tie rounding differ. This is not a new model or an independent new test.',
          arm_run=False,board_deployed=False,sd_written=False))
    print('ACTUAL_C_VALIDATION_COMPLETE',metrics['by_time']['night']['mAP50'],flush=True)
if __name__=='__main__':main()
