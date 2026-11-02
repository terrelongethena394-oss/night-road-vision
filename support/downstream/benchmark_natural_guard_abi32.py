"""Actual ARM guarded pixels vs fixed baseline board pixels and detector output."""
from pathlib import Path
import shutil,threading,time
import numpy as np
from PIL import Image
from natural_guard_lab import ROOT,CASES,PROFILES,table,apply
from photo_station_core import STAGING,RESULT_ROOT,device_lock,capture_return,verify_return,export_results
from camera_station_core import new_job
from camera_preview_stream import stream
from roi_delivery_board_tools import run
from car_roi_delivery_common import read,write,sha
from camera_snapshot_tools import words,fnv,rgb

def main():
    assert not (ROOT/'board_verified.json').exists()
    proof=read(ROOT/'build_verified.json');assert sha(ROOT/'firmware/road_detail.elf')==proof['elf_sha256']
    work=new_job('natural32_acceptance_');results=[];started=False
    with device_lock(work):
        try:
            started=True;run(ROOT/'start_camera.tcl',work/'start32.log','CAMERA_STATION_ABI32_PREVIEW_READY',timeout=240)
            for number in [1,2,4,3]:
                case=next(r for r in read(CASES/'complete.json')['cases'] if r['case']==number);old=Path(case['source_result']['packet_evidence'])
                job=new_job(f'natural32_case{number}_');shutil.copytree(old.parent/'prepared',job/'prepared')
                print('NATURAL32_CASE_BEGIN',number,flush=True)
                begin=time.monotonic()
                packet=capture_return(job,job/'prepared/source800.bgr',notify=lambda s:print('NATURAL32',number,s,flush=True))
                receipt=verify_return(packet,job/'prepared');assert receipt['firmware_abi']==32 and receipt['natural_exposure_bounds_checked']
                same={name:(old/name).read_bytes()==(packet/name).read_bytes() for name in ['source800.bgr','raw.u32','boxes.f32','baseline.f32']}
                assert all(same.values()),same
                expected=words(apply(rgb(old/'raw.u32'),rgb(old/'enhanced.u32'),table(PROFILES['natural55']))).tobytes()
                assert expected==(packet/'enhanced.u32').read_bytes(),'ARM guarded pixels differ from portable integer reference'
                receipt.update(guard_pixels_byte_exact_to_reference=True,detector_payload_byte_exact_to_ABI31=True,firmware_load_mode='natural32_candidate_RAM',wall_seconds=time.monotonic()-begin)
                result=export_results(job,packet,case['source_result']['input'],receipt,RESULT_ROOT/job.name)
                result.update(case=number,title=case['title'],baseline_output=case['output'],unchanged_payloads=same)
                write(ROOT/f'case{number:02d}_board_verified.json',result);results.append(result)
                print('NATURAL32_CASE_PASS',number,'CARS',result['car_count'],'BOARD_SECONDS',round(result['board_processing_seconds'],2),flush=True)
            preview_job=new_job('preview_natural32_');frames=[]
            stream(preview_job,threading.Event(),lambda f:frames.append(f),max_frames=8)
            assert len(frames)==8;print('NATURAL32_CAMERA_PREVIEW_PASS',flush=True)
            job=new_job('camera_natural32_');begin=time.monotonic()
            packet=capture_return(job,notify=lambda s:print('NATURAL32_CAMERA',s,flush=True),kind=4);receipt=verify_return(packet,kind=4)
            assert receipt['firmware_abi']==32 and receipt['camera_bank_byte_exact']
            prepared=job/'prepared';prepared.mkdir();shutil.copyfile(packet/'source800.bgr',prepared/'source800.bgr')
            bgr=np.fromfile(packet/'source800.bgr',np.uint8).reshape(480,800,3);Image.fromarray(bgr[:,:,::-1]).save(prepared/'input800.png')
            meta=dict(source_kind='camera',original_path=str(prepared/'input800.png'),original_sha256=sha(prepared/'input800.png'),oriented_original_size=[800,480],board_size=[800,480],
                resized_size=[800,480],padding_xy=[0,0],scale_xy=[1,1],fit='native_OV5640_frozen_frame',input_bgr_sha256=sha(packet/'source800.bgr'),
                input_bgr_fnv=fnv((packet/'source800.bgr').read_bytes()),enhancement_output_size=[400,240])
            write(prepared/'input.json',meta);receipt.update(wall_seconds=time.monotonic()-begin,firmware_load_mode='natural32_candidate_RAM')
            camera=export_results(job,packet,meta,receipt,RESULT_ROOT/job.name)
            record=dict(status='NATURAL32_ACTUAL_ARM_PHOTO_AND_CAMERA_PASS',photos=results,camera=camera,preview_job=str(preview_job),
                enhancement_pixels_byte_exact_to_reference=True,detector_bytes_unchanged_on_all_four=True,
                full_readback_verification_retained=True,models_changed=False,detector_changed=False,sd_written=False)
            write(ROOT/'board_verified.json',record);print('NATURAL32_ACTUAL_ARM_PASS',flush=True)
        except Exception as e:
            failure=dict(status='NATURAL32_CANDIDATE_FAILED_NOT_RELEASED',error=str(e),passed_cases=[r['case'] for r in results],sd_written=False)
            if started:
                try:run(Path('E:/FPGA_Enhance_Work/camera_station_abi31_20261031/start_camera.tcl'),work/'restore31.log','CAMERA_STATION_ABI31_PREVIEW_READY',timeout=240);failure['restored']='ABI31_RAM'
                except Exception as restore_error:failure['restored']=str(restore_error)
            write(ROOT/'board_failed.json',failure);raise

if __name__=='__main__':main()
