"""Repair host-only quoted-include precedence; recheck existing immutable board data."""
from pathlib import Path
import json,os,shutil,subprocess,sys
from road_enhance_common import ROOT,sha,write
HERE=Path(__file__).resolve().parent
def main():
 app=ROOT/'firmware';src=app/'source';host=ROOT/'host';evidence=ROOT/'attempts/renderer_ui_header';evidence.mkdir(exist_ok=False)
 for p in [host/'render.exe',app/'build_render.log',app/'validation.log']:shutil.copy2(p,evidence/p.name)
 gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=os.environ.copy();env['PATH']=str(gcc.parent)+';'+env['PATH']
 # Compile harness in the same source directory as the new 15-word header.
 cmd=[str(gcc),'-O2','-std=c99','-Wall','-Wextra','-Werror','-I'+str(src),str(src/'road_camera_draw.c'),str(src/'road_camera_draw_host.c'),'-lm','-o',str(host/'render.exe')]
 p=subprocess.run(cmd,capture_output=True,text=True,env=env);(app/'build_render_repaired.log').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stderr
 p=subprocess.run([sys.executable,str(HERE/'validate_road_enhance.py')],capture_output=True,text=True,env=env);(app/'validation_repaired.log').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stderr
 write(ROOT/'renderer_repair.json',dict(status='HOST_ONLY_INCLUDE_PATH_REPAIRED_EXISTING_PHYSICAL_DATA_ALL_CHECKS_PASS',cause='Quoted include in harness from workspace picked the old11word road_camera.h before -I candidate path. Readback is15words; executable returned3 before drawing.',repair='Use unchanged cloned harness colocated with candidate header. No tolerances or physical bytes changed.',old_renderer_sha256=sha(evidence/'render.exe'),new_renderer_sha256=sha(host/'render.exe'),candidate_header_sha256=sha(src/'road_camera.h'),elf_unchanged_sha256=sha(app/'road_enhance.elf'),validation_sha256=sha(app/'board_fixed_r1/validated.json'),command=cmd,hardware_access=False));print('ROAD_ENHANCE_HOST_RENDERER_REPAIRED_ALL_PHYSICAL_CHECKS_PASS',flush=True)
if __name__=='__main__':main()
