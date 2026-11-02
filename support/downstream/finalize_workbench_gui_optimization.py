"""Accept only a new completed capture from the installed GUI after streaming."""
from pathlib import Path
import time
from car_roi_delivery_common import BASE,read,write,sha
from photo_station_core import STAGING,DELIVERY,verify_return

def main():
    root=BASE/'workbench_optimization_20261031_r1';benchmark=read(root/'actual_benchmark_verified.json')
    old=benchmark['camera_regression']['output'];begin=time.monotonic()
    while True:
        r=read(STAGING/'gui_last_result.json')
        if r['output']!=old and r.get('source_kind')=='camera' and not (STAGING/'jtag.lock').exists():break
        if time.monotonic()-begin>60:raise TimeoutError('Installed GUI has not completed its new camera capture')
        time.sleep(.1)
    verify=verify_return(Path(r['packet_evidence']),kind=4)
    assert verify['frame_byte_exact'] and verify['camera_bank_byte_exact']
    assert 'Traceback' not in (STAGING/'camera_gui.log').read_text(encoding='utf-8',errors='replace')
    previews=[]
    for p in (STAGING/'jobs').glob('preview_*/preview_complete.json'):
        v=read(p)
        if v.get('connection_reused'):previews.append((p.stat().st_mtime,p,v))
    _,path,last=max(previews,key=lambda v:v[0]);assert last['frames']>=3 and last['last']['connection_reused']
    hashes={}
    for name in ['photo_station_core.py','camera_station_core.py','camera_preview_stream.py','photo_station_gui.py']:
        assert sha(Path(__file__).with_name(name))==sha(DELIVERY/'程序'/name)
        hashes[name]=sha(DELIVERY/'程序'/name)
    record=dict(status='INSTALLED_GUI_FAST_PREVIEW_TO_CAMERA_CAPTURE_PASS',camera=r,
        preview_job=str(path.parent),preview_frames=last['frames'],source_sha256=hashes,
        actual_camera_bank_and_lcd_byte_exact=True,gui_error_log_clean=True,sd_written=False,model_changed=False,threshold_changed=False)
    write(root/'installed_gui_verified.json',record);write(DELIVERY/'资料/workbench_optimization_gui_verified.json',record)
    print('INSTALLED_GUI_OPTIMIZATION_PASS','PREVIEW_FRAMES',last['frames'],'CAMERA_CARS',r['car_count'],'SECONDS',round(r['wall_seconds'],2),flush=True)

if __name__=='__main__':main()
