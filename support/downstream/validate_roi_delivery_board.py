"""Independent actual ABI30 pixel, network, ROI and framebuffer validation."""
from pathlib import Path
import ctypes as ct,struct,os,subprocess,concurrent.futures as cf
import numpy as np
from PIL import Image
from scipy.optimize import linear_sum_assignment
from car_roi_delivery_common import *
from roi_delivery_board_tools import BOARD,APP
from camera_snapshot_tools import fnv,words,rgb
from road_classwise_native import Box
from prove_car_zoom_c import ZoomC
from prove_balanced_car_c import RefinerC
from confirm_car_zoom_native import BaseFusion
from evaluate_car_boxrefine import eligible
from study_car_zoom_20261030 import XS,map_zoom
from prove_student_fusion_20261031 import Engine as Enhancer
def decode_boxes(decoded):
    assert ct.sizeof(Box)==28
    lib=ct.CDLL(str(APP/'host/post.dll'));fp=ct.POINTER(ct.c_float);lib.road_nms.argtypes=[fp,ct.POINTER(Box),ct.POINTER(Box),ct.c_int,ct.c_float,ct.c_float];lib.road_nms.restype=ct.c_int;lib.road_boxes_to400.argtypes=[ct.POINTER(Box),ct.c_int]
    a=np.ascontiguousarray(decoded,np.float32);assert a.size==56700 and np.isfinite(a).all();c=(Box*6300)();b=(Box*300)();n=lib.road_nms(a.ctypes.data_as(fp),c,b,300,.001,.6);assert 0<=n<=300;lib.road_boxes_to400(b,n)
    return np.array([[b[i].x1,b[i].y1,b[i].x2,b[i].y2,b[i].score,b[i].cls] for i in range(n)],np.float32).reshape(-1,6)
def close_boxes(a,b,coords=.005,score=.00002,permutation=False):
    a=np.asarray(a,np.float32).reshape(-1,6);b=np.asarray(b,np.float32).reshape(-1,6);assert a.shape==b.shape,(a.shape,b.shape)
    if not len(a):return dict(max_coords=0.,max_score=0.)
    if permutation:
        cost=np.max(np.abs(a[:,None,:4]-b[None,:,:4]),2)+1000*np.abs(a[:,None,4]-b[None,:,4])+1000*(a[:,None,5]!=b[None,:,5]);i,j=linear_sum_assignment(cost);a=a[i];b=b[j]
    d=np.abs(a-b);assert d[:,:4].max()<=coords and d[:,4].max()<=score and np.all(d[:,5]==0),(d.max(0),coords,score)
    return dict(max_coords=float(d[:,:4].max()),max_score=float(d[:,4].max()))
def validate(out,kind,expected_source=None):
    out=Path(out);assert (out/'packet_origin.txt').read_text().strip()=='actual_hardware_jtag_readback' and 'ROI_BOARD_PACKET_READY' in (out/'request.log').read_text(encoding='utf-8',errors='replace')
    m=struct.unpack('<320I',(out/'mail.bin').read_bytes());proof=read(APP/'arm_complete.json');policy=read(BOARD/'physical_acceptance_policy.json');assert sha(APP/'road_detail.elf')==policy['candidate_elf_sha256'];assert sha(APP/'host/post.dll')==policy['post_dll_sha256'] and sha(APP/'host/render.exe')==policy['render_exe_sha256']
    assert m[0]==0x524f4144 and m[1]==30 and m[2]==3 and m[57]==1 and m[155]==kind and m[156]==m[158]==1
    assert m[6]==m[35]==m[41]==m[74]==0 and m[30]==0x7084 and m[40]==0x5640 and m[72]==m[132]==2
    assert m[17]==m[161]==proof['weight_fnv']['detector'] and m[162]==m[192]==m[193]==proof['weight_fnv']['refiner'] and m[210]==proof['roi_weight_fnv']
    assert m[208]==0x524f4931 and m[211]==0x1B000000 and m[260:265]==(0x1D510000,0x1D520000,0x1D500000,0x1D530000,0x1D540000)
    assert m[200:208]==(0x53544631,411,1005712079,3137536,0x19000000,0x3f000000,9,1)
    source=(out/'source800.bgr').read_bytes();assert len(source)==1152000 and fnv(source)==m[145]==m[148]
    if expected_source is not None:assert source==Path(expected_source).read_bytes()
    assert m[56]==(kind==5);sensor=np.frombuffer(source,np.uint8).reshape(480,800,3)[:,:,::-1].copy();full=((sensor.astype(np.uint16).reshape(240,2,400,2,3).sum(axis=(1,3))+2)//4).astype(np.uint8)
    rawviews=[full]+[sensor[120:360,x:x+400] for x in [0,200,400]];files=['raw.u32']+[f'raw_tile{i}.u32' for i in range(3)];tasks=[]
    for i,(im,name) in enumerate(zip(rawviews,files)):
        data=words(im).tobytes();assert data==(out/name).read_bytes() and fnv(data)==(m[16] if i==0 else m[132+i]);tasks.append((name,f'decoded_base{i}.f32','weights.f32'))
    z=full.astype(np.uint64);dark=int((54*z[:,:,0]+183*z[:,:,1]+19*z[:,:,2]).sum())<=48*256*96000;assert m[189]==int(dark)
    pix=ZoomC()
    if dark:
        for i,x in enumerate(XS):
            expected=words(pix.image(sensor,x,152)).tobytes();assert expected==(out/f'zoom{i}.u32').read_bytes() and fnv(expected)==m[180+i];tasks.append((f'zoom{i}.u32',f'decoded_zoom{i}.f32','weights.f32'))
    baseviews=[decode_boxes(np.fromfile(out/f'decoded_base{i}.f32','<f4')) for i in range(4)];common=BaseFusion().run(baseviews[0],baseviews[1:],.75);common=common[common[:,5]==1];strong=common[common[:,4]>=.25]
    arm_ref=np.fromfile(out/'refiner_outputs.f32','<f4').reshape(900,5);assert np.isfinite(arm_ref).all();wanted=np.zeros((900,5),np.float32);ref=RefinerC();ref.begin(sensor);ref_count=0
    if dark:
        local=[decode_boxes(np.fromfile(out/f'decoded_zoom{i}.f32','<f4')) for i in range(3)];assert [len(v) for v in local]==list(m[183:186]);mapped_outputs=[]
        for j,pp in enumerate(local):
            q=[]
            for i,p in enumerate(pp):
                if int(p[5])!=1 or not(p[0]>1 and p[1]>1 and p[2]<399 and p[3]<239):continue
                b=map_zoom(np.asarray([p]),XS[j],152)[0];q.append(arm_ref[j*300+i])
                if eligible(b,strong):
                    im,meta=ref.crop(b);wanted[j*300+i]=ref.predict(im,meta);ref_count+=1
            mapped_outputs.append(np.asarray(q,np.float32).reshape(-1,5))
        params=read(BASE/'road_car_balanced_20261030_r1/selected.json')['chosen']['source'];common=ref.fuse(common,local,mapped_outputs,params)
    ref.end();delta=np.abs(wanted-arm_ref);assert delta.max()<=.001 and delta.mean()<=.00002 and m[194]==ref_count
    actual_common=np.fromfile(out/'common_all.f32','<f4').reshape(-1,6);assert len(common)==m[212];common_delta=close_boxes(common,actual_common)
    visible_common=actual_common[actual_common[:,4]>=.25];baseline=np.fromfile(out/'baseline.f32','<f4').reshape(-1,6);close_boxes(visible_common,baseline);assert len(baseline)==m[142]==m[171]==m[213]
    native=Native();plan=native.plan(actual_common) if dark else [];assert len(plan)==m[209];plan_words=np.fromfile(out/'roi_plan.i32','<i4');assert len(plan_words)==32
    engine=Pixels(ROOT/'c_proof/roi_verify.dll');engine.begin(sensor);roi_local=[];arm_local=np.fromfile(out/'roi_local.f32','<f4').reshape(8,300,6)
    for i,r in enumerate(plan):
        assert r['index']==m[252+i]==plan_words[i] and r['x']==m[228+i]==plan_words[8+2*i] and r['y']==m[236+i]==plan_words[9+2*i]
        data=words(engine.image(r)).tobytes();assert data==(out/f'roi{i}.u32').read_bytes() and fnv(data)==m[220+i]
        boxes=decode_boxes(np.fromfile(out/f'decoded_roi{i}.f32','<f4'));assert len(boxes)==m[244+i]==plan_words[24+i];close_boxes(boxes,arm_local[i,:len(boxes)]);roi_local.append(boxes);tasks.append((f'roi{i}.u32',f'decoded_roi{i}.f32','roi_weights.f32'))
    engine.end();expected_final=native.refine(actual_common,plan,roi_local) if dark else actual_common.copy();actual_final=np.fromfile(out/'final_all.f32','<f4').reshape(-1,6);assert len(actual_final)==m[214];final_delta=close_boxes(expected_final,actual_final);visible=actual_final[actual_final[:,4]>=.25];actual=np.fromfile(out/'boxes.f32','<f4').reshape(-1,6);close_boxes(visible,actual);assert len(actual)==m[52]==m[172]
    assert m[169]==204 and m[170]==(153 if dark else 0) and m[215]==51*len(plan) and m[104]==(357 if dark else 204)+51*len(plan)
    env=dict(os.environ);env['PATH']='E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin;'+env['PATH'];exe=BASE/'road_local_enhance_20261029_r2/host/road_ap.exe'
    def cpu_one(item):
        i,(input_name,decode_name,weight)=item;folder=out/'cpu'/str(i);folder.mkdir(parents=True);p=subprocess.run([str(exe),str(APP/'runtime'/weight),str(out/input_name),str(folder)],capture_output=True,text=True,env=env,timeout=90);assert p.returncode==0 and 'ROAD_FP32_HOST_DONE' in p.stdout
        a=np.fromfile(out/decode_name,'<f4').reshape(6300,9);b=np.fromfile(folder/'decoded.f32','<f4').reshape(6300,9);assert np.isfinite(a).all();d=np.abs(a-b);assert d.mean()<=.00002 and d[:,4:].max()<=.00002,(input_name,d.max(),d.mean(),d[:,4:].max())
        pa=decode_boxes(a);pb=np.fromfile(folder/'boxes400.f32','<f4').reshape(-1,6);box_error=close_boxes(pa[pa[:,4]>=.01],pb[pb[:,4]>=.01],permutation=True)
        return dict(input=input_name,model=weight,decoded_max_abs=float(d.max()),decoded_mean_abs=float(d.mean()),decoded_prob_max_abs=float(d[:,4:].max()),original_absolute_decode_rule_passed=bool(d.max()<=.001),post_boxes=box_error)
    with cf.ThreadPoolExecutor(4) as pool:neural=list(pool.map(cpu_one,enumerate(tasks)))
    expected=Enhancer().run(full);actual_enh=rgb(out/'enhanced.u32');ed=np.abs(expected.astype(np.int16)-actual_enh.astype(np.int16));assert ed.max()<=1 and ed.mean()<=.01
    p=subprocess.run([str(APP/'host/render.exe'),str(out/'raw.u32'),str(out/'enhanced.u32'),str(out/'boxes.f32'),str(out/'baseline.f32'),str(out/'ui.u32'),str(out/'expected_frame.bgr')],capture_output=True,text=True,env=env,timeout=30);assert p.returncode==0 and 'GUARDS_PASS' in p.stdout and (out/'expected_frame.bgr').read_bytes()==(out/'frame.bgr').read_bytes()
    Image.fromarray(np.fromfile(out/'frame.bgr',np.uint8).reshape(480,800,3)[:,:,::-1]).save(out/'lcd_readback.png')
    result=dict(status='ABI30_RAW_ROI_ENGINEERING_PACKET_PASS',physical_readback=True,joint_model_superiority_study_accepted=False,kind=kind,source_sha256=sha(out/'source800.bgr'),source_immutable=True,all_pixel_views_byte_exact=True,roi_count=len(plan),pl_conv_calls=m[104],networks=len(neural),network_comparisons=neural,common_post=common_delta,roi_post=final_delta,refiner_calls=ref_count,refiner_max_abs=float(delta.max()),enhancement_max_abs=int(ed.max()),frame_byte_exact=True,baseline_visible_cars=len(baseline),candidate_visible_cars=len(actual),processing_seconds=(m[19]+(m[20]<<32))/m[18],sd_written=False)
    write(out/'verified.json',result);print('ROI_BOARD_PACKET_VERIFIED',dict(case=out.name,networks=len(neural),rois=len(plan),cars=len(actual),seconds=result['processing_seconds']),flush=True);return result
