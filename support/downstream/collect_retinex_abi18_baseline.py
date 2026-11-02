"""Correct comparator: actual verified ABI18 on identical RGB888 inputs."""
from pathlib import Path
import json,datetime,subprocess,hashlib,struct
import numpy as np
ROOT=Path('E:/FPGA_Enhance_Work/road_retinex_arm_20261029_r1')
APP=ROOT/'firmware'
STABLE=Path('E:/FPGA_Enhance_Work/road_conv13_p16_runtime_20261028_r1/firmware')
COMPARE_PREVIOUS=True
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):Path(p).write_text(json.dumps(v,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    cases=read(APP/'cases.json');out=ROOT/('baseline18_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'));out.mkdir()
    protocol=dict(reason='Initial candidate compared ARM/PL FP32 bit patterns with x86/SSE2 nativeC, not actual verified ARM/PL. Preserve that failed attempt and require exact detector equality with fresh real ABI18 on identical inputs; do not loosen a float tolerance.',baseline_elf_sha256=sha(STABLE/'road_detail.elf'),baseline_bit_sha256=sha(STABLE/'display.bit'),candidate_elf_sha256=sha(APP/'road_detail.elf'),gate='All decoded and NMS bytes must match actual ABI18, both before and after the Retinex change; enhancement gate remains max1LSB/MAE.01/SSIM.99999.',sd_written=False)
    write(out/'protocol.json',protocol)
    d=out.as_posix();a=APP.as_posix();s=STABLE.as_posix();items=' '.join('{'+c['name']+' '+str(c['photo'])+' '+str(c['input_fnv'])+'}' for c in cases)
    tcl=f'''source {s}/camera_common.tcl
set root {a}
connect -url tcp:127.0.0.1:3121
targets -set -filter {{name =~ "ARM*#0"}} -timeout 10
if {{[catch {{
 foreach item {{{items}}} {{
  lassign $item id photo expected
  rc_check
  mwr 0x1380000c 0
  set idle 0
  for {{set i 0}} {{$i<600}} {{incr i}} {{
   after 100
   rc_check
   if {{[word 0x13800008] in {{1 5}}}} {{set idle 1;break}}
  }}
  if {{!$idle}} {{error "Not idle"}}
  mwr 0x13800120 2
  mwr 0x13800140 2
  mwr 0x13800144 32
  mwr 0x13800178 0
  rc_test $id $photo $expected 0
  set folder {d}/$id
  file mkdir $folder
  mrd -bin -file $folder/mail.bin 0x13800000 144
  mrd -bin -file $folder/raw.u32 0x16700000 96000
  mrd -bin -file $folder/decoded.f32 0x16300000 56700
  set n [word 0x138000d0]
  if {{$n>300}} {{error "Invalid boxes"}}
  if {{$n>0}} {{mrd -bin -file $folder/boxes.f32 0x16200000 [expr {{$n*6}}]}} else {{close [open $folder/boxes.f32 w]}}
  puts "ACTUAL_ABI18_FIXED_BASELINE $id"
 }}
 disconnect
 puts "ACTUAL_ABI18_ALL_BASELINES_COMPLETE"
}} why opts]}} {{
 puts stderr "BASELINE_FAILED $why"
 catch {{disconnect}}
 exit 1
}}
exit 0
'''
    p=out/'collect.tcl';p.write_text(tcl,encoding='ascii')
    with (out/'collect.log').open('w',encoding='utf-8') as log:
        run=subprocess.run(['E:/Xilinx/Vitis/2020.2/bin/xsct.bat',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=240)
    text=(out/'collect.log').read_text(encoding='utf-8');print(text,flush=True)
    assert run.returncode==0 and 'ACTUAL_ABI18_ALL_BASELINES_COMPLETE' in text
    results=[]
    previous=Path(read(ROOT/'board_session.json')['evidence']) if COMPARE_PREVIOUS else None
    for i,c in enumerate(cases):
        f=out/c['name'];m=struct.unpack('<144I',(f/'mail.bin').read_bytes())
        assert m[1]==18 and m[6]==m[35]==m[41]==m[74]==0 and m[93]==2 and m[72]==2 and m[104]==51
        assert sha(f/'raw.u32')==c['input_sha256']
        if previous is not None:
            assert (f/'decoded.f32').read_bytes()==(previous/str(i)/'decoded.f32').read_bytes(),c['name']
            assert (f/'boxes.f32').read_bytes()==(previous/str(i)/'boxes.f32').read_bytes(),c['name']
        native=APP/'runtime/cases'/c['name']/'native_raw/decoded.f32'
        ar=np.fromfile(f/'decoded.f32','<f4');pc=np.fromfile(native,'<f4')
        results.append(dict(name=c['name'],candidate_previous_decode_bytes_identical=True if previous else None,candidate_previous_box_bytes_identical=True if previous else None,original_arm_vs_host_max_abs=float(np.abs(ar-pc).max()),decode_sha256=sha(f/'decoded.f32'),boxes_sha256=sha(f/'boxes.f32')))
    result=dict(status='ACTUAL_ABI18_SAME_INPUT_BASELINE_FROZEN_CANDIDATE_DETECTOR_IDENTICAL' if previous else 'ACTUAL_ABI18_SAME_INPUT_BASELINE_FROZEN',evidence=str(out),results=results,protocol=protocol,previous_candidate_evidence=str(previous),sd_written=False)
    write(out/'verified.json',result);write(ROOT/'actual_abi18_baseline.json',result);print('ACTUAL_ABI18_BASELINE_BYTE_EXACT',flush=True)
if __name__=='__main__':main()
