"""JTAG-only ABI19 fixed-photo acceptance; restore ABI18 on real failures."""
from pathlib import Path
import datetime,json,hashlib,subprocess,struct
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity

ROOT=Path('E:/FPGA_Enhance_Work/road_retinex_arm_20261029_r1')
APP=ROOT/'firmware'
STABLE=Path('E:/FPGA_Enhance_Work/road_conv13_p16_runtime_20261028_r1/firmware')
XSCT='E:/Xilinx/Vitis/2020.2/bin/xsct.bat'
PY='E:/FPGA_Enhance_Work/nn_env312/Scripts/python.exe'
VERSION=19
DEFAULT_CAP=48
ENHANCEMENT_LABEL='C frozen project_strong'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    checks=read(APP/'runtime_checksums.json')
    assert all(sha(APP/n)==h for n,h in checks.items())
    arm=read(APP/'arm_complete.json');assert arm['version']==VERSION and arm['bit_sha256']==sha(STABLE/'display.bit') and arm['weights_sha256']==sha(STABLE/'runtime/weights.f32')
    baseline=read(ROOT/'actual_abi18_baseline.json')
    assert baseline['status'] in ['ACTUAL_ABI18_SAME_INPUT_BASELINE_FROZEN_CANDIDATE_DETECTOR_IDENTICAL','ACTUAL_ABI18_SAME_INPUT_BASELINE_FROZEN']
    assert baseline['protocol']['baseline_elf_sha256']==sha(STABLE/'road_detail.elf')
    assert baseline['protocol']['candidate_elf_sha256']==sha(APP/'road_detail.elf')
    for n in ['road_fp32.c','road_pl.c','road_conv3_pack.c','road_graph.h','road_camera_average.c']:
        assert sha(APP/'source'/n)==sha(STABLE/'source'/n)
    reference_root=Path(baseline['evidence'])
    out=ROOT/('board_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'));out.mkdir()
    write(out/'protocol.json',dict(version=VERSION,enhancement=ENHANCEMENT_LABEL,blend_strength=DEFAULT_CAP/48,detector_input='raw',pl_mode=2,enhancement_max_abs=1,enhancement_mean_abs_max=.01,enhancement_ssim_min=.99999,detector_decode_and_boxes='byte-exact to actual verified ABI18 on same inputs; not x86 floating bit patterns',actual_baseline_sha256=sha(ROOT/'actual_abi18_baseline.json'),render='byte-exact from actual packet',pixel_format='RGB888 fixed public photos',sd_written=False))
    write(ROOT/'board_session.json',dict(status=f'STARTING_ABI{VERSION}_JTAG_RAM_ACCEPTANCE',directory=str(out),sd_written=False))
    print('RETINEX_BOARD_LOADING',out,flush=True)
    try:
        with (out/'start.log').open('w',encoding='utf-8') as log:
            start=subprocess.run([XSCT,str(APP/'start_idle.tcl'),'2'],stdout=log,stderr=subprocess.STDOUT,timeout=300)
        text=(out/'start.log').read_text(encoding='utf-8')
        assert start.returncode==0 and 'ROAD_RETINEX_IDLE_READY' in text,text[-4000:]
        print('RETINEX_BOARD_IDLE_READY',flush=True)
        cases=read(APP/'cases.json');case_lines=[]
        # Revisit first photo after others, and leave its valid result displayed.
        for visit,c in enumerate(cases+[cases[0]]):
            case_lines.append('{'+c['name']+' '+str(c['photo'])+' '+str(c['input_fnv'])+' '+str(visit)+'}')
        a=APP.as_posix();d=out.as_posix();case_list=' '.join(case_lines)
        tcl=f'''source {a}/camera_common.tcl
connect -url tcp:127.0.0.1:3121
targets -set -filter {{name =~ "ARM*#0"}} -timeout 10
if {{[catch {{
 foreach item {{{case_list}}} {{
  lassign $item id photo expected visit
  rc_check
  mwr 0x1380000c 0
  set idle 0
  for {{set i 0}} {{$i<600}} {{incr i}} {{
   after 100
   rc_check
   if {{[word 0x13800008] in {{1 5}}}} {{set idle 1;break}}
  }}
  if {{!$idle}} {{error "No safe idle boundary"}}
  mwr 0x13800140 2
  mwr 0x13800144 {DEFAULT_CAP}
  mwr 0x13800178 0
  mwr 0x13800070 0
  rc_test $id $photo $expected 0
  set folder {d}/$visit
  file mkdir $folder
  mrd -bin -file $folder/mail.bin 0x13800000 144
  mrd -bin -file $folder/ui.u32 0x16500000 16
  mrd -bin -file $folder/raw.u32 0x16700000 96000
  mrd -bin -file $folder/enhanced.u32 0x16100000 96000
  mrd -bin -file $folder/decoded.f32 0x16300000 56700
  set count [word 0x138000d0]
  if {{$count>300}} {{error "Invalid box count"}}
  if {{$count>0}} {{mrd -bin -file $folder/boxes.f32 0x16200000 [expr {{$count*6}}]}} else {{close [open $folder/boxes.f32 w]}}
  set frame [word 0x13800080]
  if {{$frame!=0x02000000 && $frame!=0x02119400}} {{error "Invalid frame address"}}
  mrd -bin -file $folder/frame.bgr $frame 288000
  puts "RETINEX_FIXED_PACKET $visit $id"
 }}
 disconnect
 puts "RETINEX_ALL_FIXED_PACKETS_COMPLETE"
}} why opts]}} {{
 puts stderr "RETINEX_FIXED_FAILED $why"
 catch {{disconnect}}
 exit 1
}}
exit 0
'''
        script=out/'fixed.tcl';script.write_text(tcl,encoding='ascii')
        with (out/'fixed.log').open('w',encoding='utf-8') as log:
            run=subprocess.run([XSCT,str(script)],stdout=log,stderr=subprocess.STDOUT,timeout=360)
        text=(out/'fixed.log').read_text(encoding='utf-8')
        assert run.returncode==0 and 'RETINEX_ALL_FIXED_PACKETS_COMPLETE' in text,text[-4000:]
        results=[]
        for i,c in enumerate(cases+[cases[0]]):
            folder=out/str(i);case=APP/'runtime/cases'/c['name'];m=struct.unpack('<144I',(folder/'mail.bin').read_bytes())
            assert m[0]==0x524f4144 and m[1]==VERSION and m[2]==3 and m[57]==1 and m[56]==1
            assert m[6]==m[35]==m[41]==m[74]==0 and m[72]==m[132]==2 and m[93]==2 and m[99]==0 and m[104]==51
            assert m[30]==0x7084 and m[40]==0x5640 and m[17]==1483844061
            assert (folder/'raw.u32').read_bytes()==(case/'input400.u32').read_bytes()
            actual_reference=reference_root/c['name']
            ref_identity=next(v for v in baseline['results'] if v['name']==c['name'])
            assert sha(actual_reference/'decoded.f32')==ref_identity['decode_sha256'] and sha(actual_reference/'boxes.f32')==ref_identity['boxes_sha256']
            assert (folder/'decoded.f32').read_bytes()==(actual_reference/'decoded.f32').read_bytes()
            assert (folder/'boxes.f32').read_bytes()==(actual_reference/'boxes.f32').read_bytes()
            def rgb(p):
                x=np.fromfile(p,'<u4').reshape(240,400);return np.stack([x&255,x>>8&255,x>>16&255],2).astype(np.uint8)
            reference=rgb(case/'enhanced400.u32');actual=rgb(folder/'enhanced.u32');diff=np.abs(reference.astype(np.int16)-actual.astype(np.int16));sim=float(structural_similarity(reference,actual,channel_axis=2,data_range=255))
            assert diff.max()<=1 and diff.mean()<=.01 and sim>=.99999,(c['name'],diff.max(),diff.mean(),sim)
            render=subprocess.run([str(APP/'host/render.exe'),str(folder/'raw.u32'),str(folder/'enhanced.u32'),str(folder/'boxes.f32'),str(folder/'ui.u32'),str(folder/'expected.bgr')],capture_output=True,text=True,timeout=30)
            (folder/'render.log').write_text(render.stdout+render.stderr,encoding='utf-8')
            assert render.returncode==0 and 'GUARDS_PASS' in render.stdout and (folder/'expected.bgr').read_bytes()==(folder/'frame.bgr').read_bytes()
            Image.fromarray(np.fromfile(folder/'frame.bgr',np.uint8).reshape(480,800,3)[:,:,::-1]).save(folder/'lcd_readback.png')
            row=dict(name=c['name'],visit=i,pixel_max_abs=int(diff.max()),pixel_mean_abs=float(diff.mean()),pixel_ssim=sim,decode_byte_exact=True,boxes_byte_exact=True,frame_byte_exact=True,processing_seconds=(m[19]+(m[20]<<32))/m[18],enhancement_stage_seconds=(m[87]+(m[88]<<32))/m[18],predicted_boxes=m[52],mean_in=m[82],mean_out=m[83])
            results.append(row);print('RETINEX_PHYSICAL_CASE_PASS',row,flush=True)
        assert (out/'0/enhanced.u32').read_bytes()==(out/'4/enhanced.u32').read_bytes()
        result=dict(status=f'ABI{VERSION}_CUSTOM_RETINEX_FIXED_IMAGES_BOARD_VERIFIED_MANUAL_DISPLAY_PENDING',blend_strength=DEFAULT_CAP/48,results=results,evidence=str(out),actual_abi18_baseline_sha256=sha(ROOT/'actual_abi18_baseline.json'),elf_sha256=sha(APP/'road_detail.elf'),bit_sha256=sha(APP/'display.bit'),weights_sha256=sha(APP/'runtime/weights.f32'),final_photo=cases[0]['name'],mode='static raw detection plus custom Retinex display',hardware_access=True,sd_written=False)
        write(out/'verified.json',result);write(ROOT/'board_verified.json',result);write(ROOT/'board_session.json',result)
        print('RETINEX_ARM_BOARD_ACCEPTANCE_COMPLETE',flush=True)
    except Exception as e:
        write(out/'failure.json',dict(error=str(e),restoring='Verified ABI18 public startup',sd_written=False))
        print('RETINEX_FAILED_RESTORING_ABI18',str(e),flush=True)
        with (out/'restore.log').open('w',encoding='utf-8') as log:restore=subprocess.run([PY,str(STABLE/'user_start.py')],stdout=log,stderr=subprocess.STDOUT,timeout=520)
        restored=restore.returncode==0 and 'ROAD_CONV13_LIVE_READY' in (out/'restore.log').read_text(encoding='utf-8')
        write(ROOT/'board_session.json',dict(status=f'ABI{VERSION}_REJECTED_ABI18_RESTORED' if restored else f'ABI{VERSION}_FAILED_RESTORE_NEEDS_CONNECTION',error=str(e),evidence=str(out),sd_written=False))
        raise
if __name__=='__main__':main()
