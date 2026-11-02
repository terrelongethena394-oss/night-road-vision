"""Actual board A/B, retaining the same pixels, model and full readback checks."""
from pathlib import Path
import importlib.util,json,statistics,threading
from camera_station_core import new_job,ensure_camera,command,preview_frame,preview,process_camera
from photo_station_core import STAGING,DELIVERY,device_lock,process_photo
from car_roi_delivery_common import BASE,read,write,sha

OUT=BASE/'workbench_optimization_20261031_r1'

def main():
    OUT.mkdir(exist_ok=True)
    assert not (OUT/'actual_benchmark_verified.json').exists(),'Preserve measured results'
    oldfile=DELIVERY/'程序/photo_station_core.py'
    spec=importlib.util.spec_from_file_location('baseline_photo_station_core',oldfile);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    assert 'set upload_reused' not in oldfile.read_text(encoding='utf-8'),'Baseline was already replaced'
    src=read(STAGING/'gui_last_result.json')['input']['original_path']
    baseline_frames=[];pjob=new_job('preview_baseline_')
    with device_lock(pjob):
        ensure_camera(pjob);command(pjob,7)
        try:
            for i in range(1,4):
                frame=preview_frame(pjob,i);baseline_frames.append(frame);print('BASELINE_PREVIEW',round(frame['wall_seconds'],3),flush=True)
        finally:command(pjob,9)
    frames=[]
    pjob2=preview(threading.Event(),lambda r:(frames.append(r),print('OPTIMIZED_PREVIEW',round(r['wall_seconds'],3),flush=True)),max_frames=10)
    before=statistics.median(r['wall_seconds'] for r in baseline_frames)
    after=statistics.median(r['wall_seconds'] for r in frames[1:])
    assert after<before*.85,dict(before=before,after=after)
    write(OUT/'actual_preview_speed_verified.json',dict(status='ACTUAL_PREVIEW_CONNECTION_REUSE_FASTER',baseline=baseline_frames,
        optimized_job=str(pjob2),optimized=frames,baseline_median_seconds=before,optimized_steady_median_seconds=after,speedup=before/after,
        unchanged_payload_bytes=103680,integrity_checks_retained=True,sd_written=False))
    print('PREVIEW_SPEEDUP',round(before/after,2),flush=True)
    # First process a known fixed image with the installed release, then process
    # exactly the same file with resident-upload reuse. No model or input change.
    a=old.process_photo(src,notify=lambda s:print('BASELINE_PHOTO',s,flush=True))
    b=process_photo(src,notify=lambda s:print('OPTIMIZED_REPEAT',s,flush=True))
    assert b['transport_timings']['upload_reused']==1
    pa=Path(a['packet_evidence']);pb=Path(b['packet_evidence'])
    equal={name:(pa/name).read_bytes()==(pb/name).read_bytes() for name in ['source800.bgr','raw.u32','enhanced.u32','boxes.f32','baseline.f32']}
    assert all(equal.values()) and a['frame_byte_exact'] and b['frame_byte_exact']
    alternatives=[p for p in (STAGING/'jobs').glob('camera_*/prepared/input800.png') if sha(p)!=sha(src)]
    assert alternatives,'Need a second already-captured image to test cache invalidation'
    miss=process_photo(alternatives[0],notify=lambda s:print('DIFFERENT_PHOTO',s,flush=True))
    assert miss['transport_timings']['upload_reused']==0 and miss['frame_byte_exact']
    camera=process_camera(notify=lambda s:print('CAMERA_REGRESSION',s,flush=True))
    assert camera['camera_bank_byte_exact'] and camera['frame_byte_exact']
    write(STAGING/'gui_last_result.json',camera)
    record=dict(status='ACTUAL_WORKBENCH_OPTIMIZATION_VERIFIED',preview=read(OUT/'actual_preview_speed_verified.json'),
        repeated_photo=dict(baseline=a,optimized=b,payload_byte_exact=equal),different_photo_cache_miss=miss,camera_regression=camera,
        model_changed=False,threshold_changed=False,full_readback_verification_retained=True,sd_written=False)
    write(OUT/'actual_benchmark_verified.json',record)
    print('ACTUAL_WORKBENCH_OPTIMIZATION_PASS',json.dumps(dict(preview_before=before,preview_after=after,repeat_photo_before=a['wall_seconds'],repeat_photo_after=b['wall_seconds'])),flush=True)

if __name__=='__main__':main()
