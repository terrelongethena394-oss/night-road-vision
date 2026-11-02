"""Independent long-enough camera/VDMA progress check and coherent LCD render."""
from pathlib import Path
import datetime,json,struct,subprocess,hashlib
import numpy as np
from PIL import Image

ROOT=Path('E:/FPGA_Enhance_Work/road_conv13_p16_runtime_20261028_r1')
APP=ROOT/'firmware'

def main():
    out=ROOT/('display_soak_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
    out.mkdir()
    d=out.as_posix();app=APP.as_posix()
    tcl=f'''source {app}/camera_common.tcl
connect -url tcp:127.0.0.1:3121
targets -set -filter {{name =~ "ARM*#0"}} -timeout 10
loadhw -hw {app}/display.xsa
if {{[catch {{
 for {{set i 0}} {{$i<7}} {{incr i}} {{
  if {{$i>0}} {{after 10000}}
  rc_check
  mrd -bin -file {d}/mail_$i.bin 0x13800000 144
  mrd -bin -file {d}/vdma_$i.bin 0x43000000 48
  puts "SOAK_SAMPLE $i preview=[word 0x1380009c] detections=[word 0x138000cc]"
 }}
 rc_pause
 set frame [word 0x13800080]
 if {{$frame ni {{0x02000000 0x02119400}} && $frame!=0x02000000 && $frame!=0x02119400}} {{error "Invalid frame address"}}
 set n [word 0x138000d0]
 if {{$n>300}} {{error "Invalid box count"}}
 mrd -bin -file {d}/paused_mail.bin 0x13800000 144
 mrd -bin -file {d}/ui.u32 0x16500000 16
 mrd -bin -file {d}/live.u32 0x16000000 96000
 mrd -bin -file {d}/enhanced.u32 0x16100000 96000
 if {{$n>0}} {{mrd -bin -file {d}/boxes.f32 0x16200000 [expr {{$n*6}}]}} else {{close [open {d}/boxes.f32 w]}}
 mrd -bin -file {d}/frame.bgr $frame 288000
 mwr 0x1380000c 3
 catch {{con}}
 after 12000
 rc_check
 mrd -bin -file {d}/resumed_mail.bin 0x13800000 144
}} why opts]}} {{
 catch {{mwr 0x1380000c 3}}
 catch {{con}}
 puts stderr "DISPLAY_SOAK_FAILED $why"
 catch {{disconnect}}
 exit 1
}}
disconnect
puts "DISPLAY_SOAK_CAPTURE_RESUME_COMPLETE"
exit 0
'''
    p=out/'soak.tcl';p.write_text(tcl,encoding='ascii')
    run=subprocess.run(['E:/Xilinx/Vitis/2020.2/bin/xsct.bat',str(p)],capture_output=True,text=True,timeout=240)
    (out/'soak.log').write_text(run.stdout+run.stderr,encoding='utf-8')
    print(run.stdout+run.stderr,flush=True)
    assert run.returncode==0 and 'DISPLAY_SOAK_CAPTURE_RESUME_COMPLETE' in run.stdout
    def mail(name):return struct.unpack('<144I',(out/name).read_bytes())
    ms=[mail(f'mail_{i}.bin') for i in range(7)]
    deltas=[]
    for i,m in enumerate(ms):
        assert m[0]==0x524f4144 and m[1]==18 and m[2] in (1,2)
        assert m[6]==m[35]==m[41]==m[74]==0
        assert m[72]==m[132]==2 and m[80]==m[93]==2 and m[94]==m[99]==0 and m[56]==0
        assert m[30]==0x7084 and m[40]==0x5640 and m[104]==51
        if i:
            delta={'preview':m[39]-ms[i-1][39],'detections':m[51]-ms[i-1][51]}
            assert delta['preview']>=20 and delta['detections']>=2
            deltas.append(delta)
    paused=mail('paused_mail.bin');resumed=mail('resumed_mail.bin')
    assert paused[2]==3 and paused[57]==1
    assert resumed[2] in (1,2) and resumed[57]==0 and resumed[6]==resumed[35]==resumed[41]==resumed[74]==0
    assert resumed[39]-paused[39]>=20 and resumed[51]-paused[51]>=2
    cmd=[str(APP/'host/render.exe'),str(out/'live.u32'),str(out/'enhanced.u32'),str(out/'boxes.f32'),str(out/'ui.u32'),str(out/'expected.bgr')]
    render=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
    (out/'render.log').write_text(render.stdout+render.stderr,encoding='utf-8')
    assert render.returncode==0 and 'GUARDS_PASS' in render.stdout
    assert (out/'expected.bgr').read_bytes()==(out/'frame.bgr').read_bytes()
    image=out/'lcd_readback.png'
    Image.fromarray(np.fromfile(out/'frame.bgr',dtype=np.uint8).reshape(480,800,3)[:,:,::-1]).save(image)
    result=dict(status='P16_MODE2_60S_COUNTERS_RENDER_AND_RESUME_PASS_MANUAL_FEEDBACK_PENDING',window_seconds_requested=60,interval_deltas=deltas,preview_delta=ms[-1][39]-ms[0][39],detection_delta=ms[-1][51]-ms[0][51],frame_byte_exact=True,resumed_preview_delta=resumed[39]-paused[39],resumed_detection_delta=resumed[51]-paused[51],image=str(image),sd_written=False)
    (out/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (ROOT/'latest_display_soak.json').write_text(json.dumps(result|{'evidence_dir':str(out)},indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':main()
