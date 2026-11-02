from pathlib import Path
import subprocess,sys,time
from build_road_camera import ROOT,read,write,sha
HERE=Path(__file__).resolve().parent
XSCT=Path('E:/Xilinx/Vitis/2020.2/bin/xsct.bat')

def run(script,args,log,marker):
    path=ROOT/log;assert not path.exists()
    with path.open('w') as f:p=subprocess.run([str(XSCT),str(ROOT/script),*map(str,args)],stdout=f,stderr=subprocess.STDOUT)
    text=path.read_text(errors='replace');assert marker in text and 'ROAD_CAMERA_FAILED' not in text,(path,p.returncode,text[-3000:]);print(marker,flush=True)
def validate(out):
    p=subprocess.run([sys.executable,str(HERE/'validate_road_camera.py'),str(out)],capture_output=True,text=True);(out/'validator.log').write_text(p.stdout+p.stderr,encoding='utf-8')
    assert p.returncode==0 and 'ROAD_CAMERA_PHYSICAL_PACKET_PASS' in p.stdout,(p.stdout,p.stderr);print(p.stdout.strip(),flush=True)

def main():
    start=time.monotonic()
    while True:
        text=(ROOT/'install_camera_r2.log').read_text(errors='replace')
        if 'ROAD_CAMERA_FAILED' in text:raise RuntimeError(text[-3000:])
        if 'ROAD_CAMERA_FIRST_FIXED_READBACK_COMPLETE' in text:break
        if time.monotonic()-start>1200:raise TimeoutError('R2 installer did not finish')
        time.sleep(2)
    validate(ROOT/'board_r2_fixed')
    run('start_existing_live.tcl',[],'start_r2_live.log','ROAD_CAMERA_EXISTING_LIVE_STARTED')
    run('measure_live.tcl',[ROOT/'cadence_before_snapshots.csv'],'cadence_before.log','ROAD_CAMERA_CADENCE_READ_COMPLETE')
    for index in [1,2]:
        out=ROOT/f'live_snapshot_{index:02d}';run('snapshot_live.tcl',[out],f'live_snapshot_{index:02d}.log','ROAD_CAMERA_LIVE_READBACK_COMPLETE_AND_RESUMED');validate(out)
        run('start_existing_live.tcl',[],f'resume_after_snapshot_{index:02d}.log','ROAD_CAMERA_EXISTING_LIVE_STARTED')
    run('measure_live.tcl',[ROOT/'cadence_final.csv'],'cadence_final.log','ROAD_CAMERA_CADENCE_READ_COMPLETE')
    write(ROOT/'physical_complete.json',dict(status='CAMERA_PREVIEW_FROZEN_RESULT_INTEGRATION_PHYSICALLY_VERIFIED_AND_LIVE_RESUMED',elf_sha256=sha(ROOT/'road_camera.elf'),
        weights_sha256=sha(ROOT/'runtime/weights.f32'),fixed_r2=str(ROOT/'board_r2_fixed/validated.json'),live_snapshots=[str(ROOT/f'live_snapshot_{i:02d}/validated.json') for i in [1,2]],
        r1_all86_fixed_numerics=str(ROOT/'board_fixed_first/validated.json'),detector_kernel_object_identical_across_r1_r2=True,
        current_mode='Live rawcamera preview + latest completed frozen-frame FP32 road detections',sd_written=False,enhancement_enabled=False,physical_panel_confirmation='Await user visual check',seconds=time.monotonic()-start))
    print('ROAD_CAMERA_INTEGRATION_WORKFLOW_COMPLETE_LIVE_RUNNING',flush=True)
if __name__=='__main__':main()
