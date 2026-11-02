"""Run actual engineering cases; preserve rejected joint training claim."""
from datetime import datetime
from pathlib import Path
import traceback
from car_roi_delivery_common import ROOT,read,write,sha
from roi_delivery_board_tools import BOARD,APP,start,capture,restore
def main():
    assert read(BOARD/'probe_result.json')['available'];assert read(BOARD/'host_preflight/complete.json')['physical_readback'] is False
    out=BOARD/datetime.now().strftime('board_%Y%m%d_%H%M%S');out.mkdir();write(BOARD/'board_running.json',dict(status='STARTING_RAM_ENGINEERING_TEST',evidence=str(out),sd_written=False));started=False;results={}
    try:
        start(out);started=True
        cases=[('road0',5,BOARD/'fixtures/road0.bgr',1),('road1',5,BOARD/'fixtures/road1.bgr',2),('gray96',5,BOARD/'fixtures/gray96.bgr',3),('black',5,BOARD/'fixtures/black.bgr',4),('camera',4,None,5),('road0_repeat',5,BOARD/'fixtures/road0.bgr',6)]
        for name,kind,source,photo in cases:
            write(BOARD/'board_running.json',dict(status='ACTUAL_CASE_RUNNING',case=name,evidence=str(out),sd_written=False));print('ROI_ACTUAL_BOARD_CASE_START',name,flush=True);r=capture(out/name,kind=kind,source=source,photo=photo,view=1);results[name]=r;write(out/'case_results.json',results)
        for name in ['raw.u32','source800.bgr','common_all.f32','roi_plan.i32','roi_local.f32','final_all.f32','boxes.f32']:
            assert (out/'road0'/name).read_bytes()==(out/'road0_repeat'/name).read_bytes(),('repeat_not_deterministic',name)
        record=dict(status='ABI30_RAW_ROI_ACTUAL_ENGINEERING_VERIFIED',physical_readback=True,evidence=str(out),cases=results,repeat_deterministic=True,elf_sha256=sha(APP/'road_detail.elf'),bit_sha256=sha(APP/'display.bit'),roi_weights_sha256=sha(APP/'runtime/roi_weights.f32'),full_joint_model_superiority_study_accepted=False,baseline_contrast_only_confirmed=True,enhanced_input_detection_advantage_claimed=False,sd_written=False)
        write(BOARD/'board_verified.json',record);write(BOARD/'board_running.json',dict(status='ACTUAL_ENGINEERING_VERIFIED',evidence=str(out),sd_written=False));print('ROI_ACTUAL_BOARD_ALL_CASES_VERIFIED',out,flush=True)
    except Exception as e:
        failure=dict(status='ABI30_ENGINEERING_FAILED',evidence=str(out),error=str(e),traceback=traceback.format_exc(),restore_attempted=True,sd_written=False)
        try:failure['restoration']=restore(out)
        except Exception as restore_error:failure['restoration']=dict(status='RESTORE_FAILED_LINK_OR_APP_UNAVAILABLE',error=str(restore_error))
        write(BOARD/'board_failed.json',failure);write(BOARD/'board_running.json',failure);print('ROI_BOARD_ENGINEERING_FAILED',failure,flush=True);raise
if __name__=='__main__':main()
