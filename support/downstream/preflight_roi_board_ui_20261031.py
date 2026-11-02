"""Host layout and Tcl syntax tests. Never counts as physical board evidence."""
import os,subprocess,struct
from pathlib import Path
import numpy as np
from car_roi_delivery_common import ROOT,read,write,sha
from roi_delivery_board_tools import BOARD,APP,run
from prove_student_fusion_20261031 import Engine
from camera_snapshot_tools import words
def main():
    out=BOARD/'host_preflight';assert not out.exists();out.mkdir();raw=np.full((240,400,3),16,np.uint8);enh=Engine().run(raw);assert not np.array_equal(raw,enh);words(raw).tofile(out/'raw.u32');words(enh).tofile(out/'enhanced.u32');(out/'boxes.f32').write_bytes(b'');(out/'baseline.f32').write_bytes(b'')
    env=dict(os.environ);env['PATH']='E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin;'+env['PATH'];tests=[]
    for view in [0,1]:
        ui=[1,1,1,99999,0,0,0,1,1,1,0,16,0,0,2|(view<<8),2,0];(out/'ui.u32').write_bytes(struct.pack('<17I',*ui));target=out/f'host_layout_mode{view}.bgr';p=subprocess.run([str(APP/'host/render.exe'),str(out/'raw.u32'),str(out/'enhanced.u32'),str(out/'boxes.f32'),str(out/'baseline.f32'),str(out/'ui.u32'),str(target)],capture_output=True,text=True,env=env);assert p.returncode==0 and 'GUARDS_PASS' in p.stdout;image=np.fromfile(target,np.uint8).reshape(480,800,3)
        assert image[100:340,:400].tobytes()==raw[:,:,::-1].tobytes();assert image[100:340,400:].tobytes()==(raw if view else enh)[:,:,::-1].tobytes();tests.append(dict(view=view,raw_left_exact=True,right_expected_exact=True,guards=True))
    script=out/'parse_tcl.tcl';script.write_text(f'''source {APP.as_posix()}/camera_common.tcl
set f [open {APP.as_posix()}/start_idle.tcl r]
set body [read $f];close $f
if {{![info complete $body]}} {{error "Incomplete start Tcl"}}
puts "ROI_TCL_PARSE_OK"
exit 0
''',encoding='ascii');run(script,out/'parse_tcl.log','ROI_TCL_PARSE_OK',timeout=60)
    write(out/'complete.json',dict(status='HOST_UI_AND_TCL_PREFLIGHT_ONLY_NOT_BOARD_PROOF',tests=tests,tcl_complete=True,physical_readback=False,source_implementation_sha256=sha(APP/'source/road_camera_draw.c'),hardware_programmed=False,sd_written=False));print('ROI_HOST_PREFLIGHT_PASS_NOT_BOARD_EVIDENCE',flush=True)
if __name__=='__main__':main()
