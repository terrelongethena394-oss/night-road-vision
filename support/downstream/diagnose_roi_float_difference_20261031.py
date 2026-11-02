"""Diagnose original FP32 probe failure without changing acceptance thresholds."""
import os,copy,subprocess,sys
from pathlib import Path
import numpy as np
from car_roi_delivery_common import *
from prove_car_zoom_c import ZoomC
from shadowlift_lab import words
import road_accuracy_common as ac
def main():
    import torch
    case2='--case2' in sys.argv;out=ROOT/'c_proof'/('float_diagnostic_v2' if case2 else 'float_diagnostic');out.mkdir(exist_ok=True);name='16e496ca-96bed513.jpg' if case2 else 'a2a359fb-14f1d903.jpg';r=next(r for r in read(ROOT/'development_manifest.json') if r['name']==name);sensor,_=ac.sensor400(Path(r['data_root'])/'images'/name)
    if case2:
        base=next(r['detections'] for r in read(BASE/'road_allview_enhance_20261031_r1/predictions.json')['raw'] if r['name']==name);roi=Native().plan(base)[4];engine=Pixels(ROOT/'c_proof/roi_verify.dll');engine.begin(sensor);image=engine.image(roi);engine.end()
    else:image=ZoomC().image(sensor,520,152)
    words(image).tofile(out/'input.u32')
    if case2:assert sha(out/'input.u32')==read(ROOT/'c_proof/numeric_failure_v2.json')['input_sha256']
    env=dict(os.environ);env['PATH']='E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin;'+env['PATH'];exe=BASE/'road_local_enhance_20261029_r2/host/road_ap.exe';p=subprocess.run([str(exe),str(INITIAL.parent/'weights.f32'),str(out/'input.u32'),str(out)],capture_output=True,text=True,env=env);assert p.returncode==0 and 'ROAD_FP32_HOST_DONE' in p.stdout
    actual=np.fromfile(out/'decoded.f32',np.float32).reshape(6300,9);ac.WEIGHTS=INITIAL;det=ac.Detector();x=torch.from_numpy(ac.preprocess400(image).transpose(2,0,1).copy())[None].float()/255
    with torch.inference_mode():gpu=det.model(x.cuda())[0].cpu().numpy()[0]
    cpu_model=copy.deepcopy(det.model).cpu().eval()
    with torch.inference_mode():cpu=cpu_model(x)[0].numpy()[0]
    precise=copy.deepcopy(cpu_model).double().eval()
    with torch.inference_mode():reference=precise(x.double())[0].numpy()[0]
    gpu.tofile(out/'gpu.f32');cpu.tofile(out/'torch_cpu.f32');reference.tofile(out/'reference.f64');diff=np.abs(actual-gpu);positions=np.argwhere(diff>.001);details=[]
    for i,j in positions:
        details.append(dict(anchor=int(i),component=['cx','cy','width','height','objectness','person','car','truck','bus'][j],c=float(actual[i,j]),gpu=float(gpu[i,j]),torch_cpu=float(cpu[i,j]),reference64=float(reference[i,j]),abs_difference=float(diff[i,j]),class_scores=(gpu[i,4]*gpu[i,5:]).tolist()))
    from scipy.optimize import linear_sum_assignment
    cboxes=np.fromfile(out/'boxes400.f32',np.float32).reshape(-1,6);gboxes=np.asarray(det.run([image])[0],np.float32).reshape(-1,6);boxsummary=dict(c_boxes=len(cboxes),gpu_boxes=len(gboxes))
    if cboxes.shape==gboxes.shape and len(cboxes):
        costs=np.max(np.abs(cboxes[:,None,:4]-gboxes[None,:,:4]),2)+1000*np.abs(cboxes[:,None,4]-gboxes[None,:,4])+1000*(cboxes[:,None,5]!=gboxes[None,:,5]);i,j=linear_sum_assignment(costs);d=np.abs(cboxes[i]-gboxes[j]);boxsummary.update(max_coords_abs=float(d[:,:4].max()),max_score_abs=float(d[:,4].max()),classes_equal=bool((d[:,5]==0).all()))
    summary=dict(status='ORIGINAL_CB_BASE6_FLOAT_DIFFERENCE_DIAGNOSED_NOT_THRESHOLD_PASS',source_name=name,maximum=float(diff.max()),mean=float(diff.mean()),over_original_max_tolerance=len(details),details=details,by_component_max=diff.max(0).tolist(),c_vs_float64_max=np.abs(actual-reference).max(0).tolist(),gpu_vs_float64_max=np.abs(gpu-reference).max(0).tolist(),torch_cpu_vs_float64_max=np.abs(cpu-reference).max(0).tolist(),post_nms=boxsummary,hardware_access=False,sd_written=False)
    write(out/'diagnostic.json',summary);print(summary)
if __name__=='__main__':main()
