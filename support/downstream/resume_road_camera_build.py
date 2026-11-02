"""Resume only renderer/ARM compilation after a portable uint32 printf correction."""
import os,subprocess,shutil,time
from build_road_camera import ROOT,HERE,GCC,NN,LCD,OLD,PLATFORM,TOOLS,read,write,sha
import struct

def main():
    assert (ROOT/'host_complete.json').exists() and not (ROOT/'offline_complete.json').exists()
    source=ROOT/'source';p=source/'road_camera_draw.c';old=p.read_text();new=old[:old.index('int road_camera_draw(')]+(HERE/'road_camera_draw_body.inc').read_text()
    if not (ROOT/'build_attempt1.log').exists():shutil.copy2(ROOT/'build.log',ROOT/'build_attempt1.log')
    p.write_text(new,encoding='ascii');host=ROOT/'host';env=os.environ.copy();env['PATH']=str(GCC.parent)+os.pathsep+env.get('PATH','')
    cmd=[str(GCC),'-O3','-std=c99','-Wall','-Wextra','-Werror','-I'+str(source),str(p),str(source/'road_camera_draw_host.c'),'-o',str(host/'render.exe'),'-lm']
    run=subprocess.run(cmd,env=env,capture_output=True,text=True);assert run.returncode==0,run.stderr
    run=subprocess.run([str(host/'render.exe'),str(host/'live_control.u32'),str(host/'result_control.u32'),str(host/'control_boxes.f32'),str(host/'control_ui.u32'),str(host/'control_frame_after_cast.bgr')],capture_output=True,text=True,check=True)
    assert (host/'control_frame_after_cast.bgr').read_bytes()==(host/'control_frame.bgr').read_bytes()
    write(ROOT/'renderer_cast_fix.json',dict(status='PORTABLE_UNSIGNED_PRINTF_CASTS_RENDER_BYTES_UNCHANGED',compiler_command=cmd,first_compile_log='build_attempt1.log'))
    builder=(HERE/'build_road_camera.py').read_text();tail=builder[builder.index("    for name in ['display.bit','display.xsa'"):builder.index("if __name__=='__main__':main()")]
    tail=tail.replace('obj.mkdir();','obj.mkdir(exist_ok=True);')
    code="def resume():\n    source=ROOT/'source'\n    commands=read(ROOT/'host_complete.json')['commands']\n    start=time.monotonic()\n"+tail
    namespace=globals();exec(compile(code,str(HERE/'build_road_camera.py'),'exec'),namespace);namespace['resume']()
if __name__=='__main__':main()
