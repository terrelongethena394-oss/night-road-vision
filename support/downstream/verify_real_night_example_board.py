"""Inject a genuine night example into both actual board inference paths."""
from pathlib import Path
import json,struct,subprocess,datetime,hashlib
import numpy as np
from PIL import Image

BASE=Path('E:/FPGA_Enhance_Work')
ROOT=BASE/'road_real_night_examples_20261029'
APP=BASE/'road_conv13_p16_runtime_20261028_r1/firmware'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    meta=json.loads((ROOT/'来源与验证.json').read_text(encoding='utf-8'))
    example=meta['examples'][0];case=Path(example['directory'])
    assert sha(case/'input400.u32')==example['input_sha256']
    expected=2166136261
    for b in (case/'input400.u32').read_bytes():expected=((expected^b)*16777619)&0xffffffff
    out=ROOT/('board_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'));out.mkdir()
    a=APP.as_posix();c=case.as_posix();o=out.as_posix()
    tcl=f'''source {a}/camera_common.tcl
connect -url tcp:127.0.0.1:3121
targets -set -filter {{name =~ "ARM*#0"}} -timeout 10
if {{[catch {{
 rc_check
 if {{[word 0x13800120]!=2}} {{error "Expected verified PL mode2"}}
 foreach pipe {{0 1}} {{
  mwr 0x1380000c 0
  set idle 0
  for {{set i 0}} {{$i<400}} {{incr i}} {{
   after 100
   rc_check
   if {{[word 0x13800008] in {{1 5}}}} {{set idle 1;break}}
  }}
  if {{!$idle}} {{error "No safe idle boundary"}}
  mwr 0x13800178 0
  mwr 0x13800140 $pipe
  mwr 0x13800144 32
  mwr 0x13800070 0
  mwr 0x1380006c {expected}
  set wanted [expr {{[word 0x13800010]+1}}]
  dow -data {c}/input400.u32 0x10000000
  catch {{con}}
  mwr 0x1380000c 2
  set ready 0
  for {{set i 0}} {{$i<600}} {{incr i}} {{
   after 100
   rc_check
   if {{[word 0x13800008]==5 && [word 0x13800010]==$wanted}} {{set ready 1;break}}
  }}
  if {{!$ready}} {{error "Inference timeout"}}
  rc_pause
  set folder {o}/pipe$pipe
  file mkdir $folder
  mrd -bin -file $folder/mail.bin 0x13800000 144
  mrd -bin -file $folder/ui.u32 0x16500000 16
  mrd -bin -file $folder/raw.u32 0x16700000 96000
  mrd -bin -file $folder/enhanced.u32 0x16100000 96000
  mrd -bin -file $folder/decoded.f32 0x16300000 56700
  set n [word 0x138000d0]
  if {{$n>300}} {{error "Invalid boxes"}}
  if {{$n>0}} {{mrd -bin -file $folder/boxes.f32 0x16200000 [expr {{$n*6}}]}} else {{close [open $folder/boxes.f32 w]}}
  set frame [word 0x13800080]
  if {{$frame!=0x02000000 && $frame!=0x02119400}} {{error "Invalid frame"}}
  mrd -bin -file $folder/frame.bgr $frame 288000
  puts "REAL_NIGHT_BOARD_PIPE_COMPLETE $pipe"
 }}
 disconnect
 puts "REAL_NIGHT_BOARD_BOTH_PATHS_COMPLETE"
}} why opts]}} {{
 puts stderr "REAL_NIGHT_BOARD_FAILED $why"
 catch {{disconnect}}
 exit 1
}}
exit 0
'''
    script=out/'verify.tcl';script.write_text(tcl,encoding='ascii')
    run=subprocess.run(['E:/Xilinx/Vitis/2020.2/bin/xsct.bat',str(script)],capture_output=True,text=True,timeout=240)
    (out/'run.log').write_text(run.stdout+run.stderr,encoding='utf-8');print(run.stdout+run.stderr,flush=True)
    assert run.returncode==0 and 'REAL_NIGHT_BOARD_BOTH_PATHS_COMPLETE' in run.stdout
    results=[]
    for pipe,name in [(0,'raw'),(1,'enhanced')]:
        folder=out/f'pipe{pipe}';native=case/('native_'+name)
        m=struct.unpack('<144I',(folder/'mail.bin').read_bytes())
        assert m[0]==0x524f4144 and m[1]==18 and m[2]==3 and m[57]==1 and m[56]==1
        assert m[6]==m[35]==m[41]==m[74]==0 and m[72]==m[132]==2 and m[93]==pipe and m[99]==0 and m[104]==51
        assert (folder/'raw.u32').read_bytes()==(case/'input400.u32').read_bytes()
        expected_pixels=case/('input400.u32' if pipe==0 else 'enhanced400.u32')
        assert (folder/'enhanced.u32').read_bytes()==expected_pixels.read_bytes()
        assert (folder/'decoded.f32').read_bytes()==(native/'decoded.f32').read_bytes()
        assert (folder/'boxes.f32').read_bytes()==(native/'boxes400.f32').read_bytes()
        render=subprocess.run([str(APP/'host/render.exe'),str(folder/'raw.u32'),str(folder/'enhanced.u32'),str(folder/'boxes.f32'),str(folder/'ui.u32'),str(folder/'expected.bgr')],capture_output=True,text=True,timeout=30)
        (folder/'render.log').write_text(render.stdout+render.stderr,encoding='utf-8')
        assert render.returncode==0 and 'GUARDS_PASS' in render.stdout and (folder/'expected.bgr').read_bytes()==(folder/'frame.bgr').read_bytes()
        Image.fromarray(np.fromfile(folder/'frame.bgr',np.uint8).reshape(480,800,3)[:,:,::-1]).save(folder/'lcd_readback.png')
        results.append(dict(pipe_mode=pipe,decoded_byte_exact=True,boxes_byte_exact=True,pixels_byte_exact=True,frame_byte_exact=True,processing_seconds=(m[19]+(m[20]<<32))/m[18],native_ground_truth_evaluation=example['native_results'][pipe]))
    result=dict(status='REAL_NIGHT_RAW_AND_ENHANCED_INPUT_BOARD_BYTE_EXACT',fixture=example['name'],evidence=str(out),results=results,final_state='Fixed public road photograph, enhanced-input experimental mode1, paused for viewing; camera pixels not used as inference input',sd_written=False,warning='Selected positive illustration, not overall accuracy improvement; public stable camera startup still defaults mode2 raw-input detection.')
    (out/'verified.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'board_verified.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
