"""Simulated reader tests ONLY;explicitly never counted as new board evidence."""
from pathlib import Path
import sys,shutil,struct,os,subprocess,json
import numpy as np
BASE=Path('E:/FPGA_Enhance_Work');ROOT=BASE/'road_student_fusion_20261031_r1/board_candidate'
sys.path.insert(0,str(ROOT/'tools'))
from validate_balanced_board import validate
from student_display_runtime import Engine
from camera_snapshot_tools import words,rgb
from car_box_refine_common import read,write

def main():
    assert not (ROOT/'simulated_reader_tests').exists();out=ROOT/'simulated_reader_tests';out.mkdir()
    prior=Path(read(BASE/'road_car_balanced_20261030_r1/board_candidate/board_verified.json')['evidence']);proof=read(ROOT/'firmware/arm_complete.json');engine=Engine();results=[]
    for name in ['photo_0','photo_2']:
        dst=out/name;dst.mkdir()
        for p in (prior/name).iterdir():
            if p.is_file():shutil.copy2(p,dst/p.name)
        (dst/'packet_origin.txt').write_text('SIMULATED_HOST_PACKET_NOT_BOARD_PROOF',encoding='ascii');(dst/'request.log').write_text('SIMULATED_READER_ONLY_NOT_ACTUAL_NEW_HARDWARE',encoding='ascii')
        m=list(struct.unpack('<208I',(dst/'mail.bin').read_bytes()));m[1]=29;m[200:208]=[0x53544631,411,proof['student_weight_fnv'],32*96000+65536,0x19000000,0x3f000000,9,1];(dst/'mail.bin').write_bytes(struct.pack('<208I',*m))
        words(engine.run(rgb(dst/'raw.u32'))).tofile(dst/'enhanced.u32')
        env=dict(os.environ);env['PATH']='E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin;'+env['PATH']
        cmd=[str(ROOT/'firmware/host/render.exe'),*[str(dst/n) for n in ['raw.u32','enhanced.u32','boxes.f32','baseline.f32','ui.u32','frame.bgr']]]
        p=subprocess.run(cmd,capture_output=True,text=True,env=env);assert p.returncode==0 and 'GUARDS_PASS' in p.stdout
        result=validate(dst,5,physical=False);assert result['physical_readback'] is False;results.append(result)
    write(ROOT/'reader_smoke.json',dict(status='ABI29_READER_SIMULATED_SMOKES_PASS_NOT_BOARD_PROOF',physical_readback=False,tests=results,
      timing_scope='Reused old packet timestamps are not new inference measurements.',hardware_programmed=False,sd_written=False))
    print('ABI29_SIMULATED_READER_SMOKE_PASS',flush=True)
if __name__=='__main__':main()
