"""Collect actual camera, photo-regression and installed-interface evidence."""
from pathlib import Path
import json,struct
from photo_station_core import STAGING,DELIVERY,RESULT_ROOT,verify_return
from camera_station_core import CAMERA
from car_roi_delivery_common import read,write,sha

def main():
    results=[]
    for job in sorted((STAGING/'jobs').glob('camera_*')):
        if not (job/'complete.json').exists():continue
        r=read(job/'complete.json');v=verify_return(Path(r['packet_evidence']),kind=4)
        assert v['camera_bank_byte_exact'] and v['frame_byte_exact'] and r['source_kind']=='camera'
        assert Path(r['output']).resolve().is_relative_to(RESULT_ROOT.resolve())
        results.append(dict(job=str(job),output=r['output'],car_count=r['car_count'],board_processing_seconds=r['board_processing_seconds'],wall_seconds=r['wall_seconds'],validation=v))
    assert len(results)>=2,'Need both CLI and actual GUI camera captures'
    frames=[]
    for p in sorted((STAGING/'jobs').glob('preview_*/preview_complete.json')):
        r=read(p);frames.append(dict(job=str(p.parent),frames=r['frames'],last=r['last']))
    assert frames and all(r['frames']>0 for r in frames)
    regression=read(CAMERA/'photo_regression_verified.json');assert regression['status']=='ABI31_PHOTO_REGRESSION_PASS'
    hashes={}
    for name in ['camera_station_core.py','camera_preview_stream.py','photo_station_core.py','photo_station_gui.py','roi_delivery_board_tools.py']:
        assert sha(Path(__file__).with_name(name))==sha(DELIVERY/'程序'/name)
        hashes[name]=sha(DELIVERY/'程序'/name)
    assert not (STAGING/'jtag.lock').exists(),'Leave no hardware task running at handoff'
    record=dict(status='CAMERA_WORKBENCH_ACTUAL_HARDWARE_ROUNDTRIP_VERIFIED',camera_captures=results,previews=frames,
        photo_regression=regression,source_sha256=hashes,models_changed=False,sd_written=False,
        visual_checks=['Photo/camera selector switches correctly','OV5640 actual image appears on left without boxes',
            'Enhanced card clears when new preview begins','Grab automatically stops preview before capture',
            'Completed capture returns both images and car count','Camera result restores in camera mode after restarting GUI'],
        physical_screen_confirmation='User confirmed same captured image on LCD, normal text and colors on 2026-10-31',
        accuracy_claim='Interface validation only; no new accuracy improvement claimed; detection uses raw input',
        known_observation='Indoor clothes-rack captures returned counts 1, 0, 1 across three tests; these include false positives. Camera interface tests are not accuracy validation on road scenes.')
    write(CAMERA/'camera_workbench_verified.json',record);write(DELIVERY/'资料/camera_workbench_verified.json',record)
    print('CAMERA_WORKBENCH_VERIFIED',len(results),'CAPTURES',flush=True)
    print(json.dumps([dict(board_seconds=r['board_processing_seconds'],wall_seconds=r['wall_seconds'],car_count=r['car_count']) for r in results]),flush=True)

if __name__=='__main__':main()
