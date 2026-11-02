"""RAM-only ABI22 neural comparator -> ABI23 four-pass verification."""
import ctypes as ct,datetime,subprocess,struct
from PIL import Image
from road_accuracy_common import *
APP=ROOT/'firmware'
OLD=BASE/'road_retinex_noiseguard_arm_20261029_r1/firmware'
XSCT='E:/Xilinx/Vitis/2020.2/bin/xsct.bat'
PY='E:/FPGA_Enhance_Work/nn_env312/Scripts/python.exe'

def run(script,log,marker,timeout=600):
    with log.open('w',encoding='utf-8') as f:p=subprocess.run([XSCT,str(script)],stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
    text=log.read_text(encoding='utf-8');assert p.returncode==0 and marker in text,text[-4000:]

def main():
    assert read(ROOT/'fresh_result.json')['quality_accepted']
    assert read(BASE/'road_accuracy_lowlight_20261030_r1/result.json')['accepted'],'Independent low-brightness confirmation required after time-label audit'
    assert all(sha(APP/n)==h for n,h in read(APP/'runtime_checksums.json').items())
    out=ROOT/('board_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'));out.mkdir()
    scan=out/'scan.tcl';scan.write_text('connect -url tcp:127.0.0.1:3121\nputs [targets]\ntargets -set -filter {name =~ "ARM*#0"} -timeout 10\nputs "ACCURACY_ARM_FOUND"\ndisconnect\nexit 0\n',encoding='ascii')
    try:run(scan,out/'scan.log','ACCURACY_ARM_FOUND',45)
    except Exception as e:
        write(ROOT/'board_session.json',dict(status='ABI23_COMPILED_NOT_DOWNLOADED_NO_TARGET',evidence=str(out),error=str(e),hardware_mutation=False,sd_written=False));print('ACCURACY_BOARD_NEEDS_CONNECTION',str(e),flush=True);return
    cases=read(APP/'cases.json');default=read(ROOT/'board_fixture_protocol.json')['default_case'];ordered=cases+[next(c for c in cases if c['name']==default)]
    write(out/'protocol.json',dict(elf_sha256=sha(APP/'road_detail.elf'),old_elf_sha256=sha(OLD/'road_detail.elf'),cases=cases,gates=read(ROOT/'board_numerical_gates.json'),sd_written=False))
    print('ACCURACY_ARM_BASELINE_LOADING',out,flush=True)
    try:
        run(OLD/'start_idle.tcl',out/'start22.log','ROAD_RETINEX_IDLE_READY',300)
        items=' '.join('{'+v['id']+' '+str(c['photo']*10+v['view'])+' '+str(v['expected_fnv'])+' '+c['name']+' '+str(v['view'])+'}' for c in cases for v in c['views'])
        script=out/'baseline22.tcl';script.write_text(f'''source {OLD.as_posix()}/camera_common.tcl
set root {APP.as_posix()}
connect -url tcp:127.0.0.1:3121
targets -set -filter {{name =~ "ARM*#0"}} -timeout 10
if {{[catch {{
 foreach item {{{items}}} {{
  lassign $item id photo expected name view
  mwr 0x1380000c 0
  after 350
  rc_check
  mwr 0x13800120 2
  mwr 0x13800140 0
  mwr 0x13800178 0
  rc_test $id $photo $expected 0
  set folder {out.as_posix()}/baseline22/$name/$view
  file mkdir $folder
  mrd -bin -file $folder/mail.bin 0x13800000 144
  mrd -bin -file $folder/raw.u32 0x16700000 96000
  mrd -bin -file $folder/decoded.f32 0x16300000 56700
  puts "ACCURACY_GOLD22 $name $view"
 }}
 disconnect
 puts "ACCURACY_BASELINE22_COMPLETE"
}} why opts]}} {{puts stderr "ACCURACY_BASELINE_FAILED $why";catch {{disconnect}};exit 1}}
exit 0
''',encoding='ascii')
        run(script,out/'baseline22.log','ACCURACY_BASELINE22_COMPLETE',600)
        for c in cases:
            for v in c['views']:
                folder=out/'baseline22'/c['name']/str(v['view']);m=struct.unpack('<144I',(folder/'mail.bin').read_bytes())
                assert m[1]==22 and m[2]==3 and m[93]==0 and m[99]==0 and m[104]==51 and m[6]==m[35]==m[41]==m[74]==0
                assert sha(folder/'raw.u32')==v['input_sha256']
        print('ACCURACY_ACTUAL22_ALL_VIEWS_FROZEN',flush=True)
        run(APP/'start_idle.tcl',out/'start23.log','ROAD_RETINEX_IDLE_READY',300)
        items=' '.join('{'+c['name']+' '+str(c['photo'])+' '+str(c['views'][0]['expected_fnv'])+' '+' '.join(str(v['expected_fnv']) for v in c['views'][1:])+' '+str(i)+'}' for i,c in enumerate(ordered))
        script=out/'candidate23.tcl';script.write_text(f'''source {APP.as_posix()}/camera_common.tcl
connect -url tcp:127.0.0.1:3121
targets -set -filter {{name =~ "ARM*#0"}} -timeout 10
if {{[catch {{
 foreach item {{{items}}} {{
  lassign $item id photo expected h0 h1 h2 visit
  mwr 0x1380000c 0
  after 350
  rc_check
  if {{[word 0x13800008] ni {{1 5}}}} {{error "Not safe injected idle"}}
  for {{set j 0}} {{$j<3}} {{incr j}} {{dow -data $root/runtime/cases/$id/tile$j/input400.u32 [expr {{0x1A000000+$j*0x60000}}]}}
  catch {{con}}
  mwr 0x13800220 $h0
  mwr 0x13800224 $h1
  mwr 0x13800228 $h2
  mwr 0x13800140 2
  mwr 0x13800144 48
  mwr 0x13800178 2
  rc_test $id $photo $expected 0
  set folder {out.as_posix()}/candidate23/$visit
  file mkdir $folder
  mrd -bin -file $folder/mail.bin 0x13800000 144
  mrd -bin -file $folder/ui.u32 0x16500000 17
  mrd -bin -file $folder/raw.u32 0x16700000 96000
  mrd -bin -file $folder/enhanced.u32 0x16100000 96000
  mrd -bin -file $folder/decoded0.f32 0x17100000 56700
  for {{set j 0}} {{$j<3}} {{incr j}} {{mrd -bin -file $folder/decoded[expr {{$j+1}}].f32 [expr {{0x1A120000+$j*0x40000}}] 56700}}
  set n [word 0x138000d0]
  set bn [word 0x13800238]
  if {{$n>300 || $bn>300}} {{error "Invalid box count"}}
  if {{$n>0}} {{mrd -bin -file $folder/boxes.f32 0x16200000 [expr {{$n*6}}]}} else {{close [open $folder/boxes.f32 w]}}
  if {{$bn>0}} {{mrd -bin -file $folder/baseline_boxes.f32 0x1A200000 [expr {{$bn*6}}]}} else {{close [open $folder/baseline_boxes.f32 w]}}
  set frame [word 0x13800080]
  if {{$frame!=0x02000000 && $frame!=0x02119400}} {{error "Invalid frame"}}
  mrd -bin -file $folder/frame.bgr $frame 288000
  puts "ACCURACY_ABI23_PACKET $id $visit"
 }}
 disconnect
 puts "ACCURACY_ABI23_ALL_PACKETS_COMPLETE"
}} why opts]}} {{puts stderr "ACCURACY_ABI23_FAILED $why";catch {{disconnect}};exit 1}}
exit 0
''',encoding='ascii')
        run(script,out/'candidate23.log','ACCURACY_ABI23_ALL_PACKETS_COMPLETE',600)
        results=validate(out,ordered)
        result=dict(status='ABI23_FOUR_PASS_QUALITY_AND_BOARD_NUMERICS_VERIFIED',results=results,evidence=str(out),elf_sha256=sha(APP/'road_detail.elf'),bit_sha256=sha(APP/'display.bit'),weights_sha256=sha(APP/'runtime/weights.f32'),final_photo=default,quality_sha256=sha(ROOT/'fresh_result.json'),physical_panel_check='Not repeated; actual framebuffer and VDMA verified',sd_written=False)
        write(ROOT/'board_verified.json',result);write(ROOT/'board_session.json',result);write(out/'verified.json',result)
        print('ACCURACY_ABI23_BOARD_ACCEPTANCE_COMPLETE',result,flush=True)
    except Exception as e:
        write(out/'failure.json',dict(error=str(e),restore='ABI22 first fixed photo',sd_written=False));print('ACCURACY_FAILED_RESTORING_ABI22',str(e),flush=True)
        with (out/'restore.log').open('w',encoding='utf-8') as log:p=subprocess.run([PY,str(OLD.parent/'retinex_fixed_entry.py'),'start','1','full'],stdout=log,stderr=subprocess.STDOUT,timeout=400)
        restored=p.returncode==0 and 'FIXED_PHOTO_READY' in (out/'restore.log').read_text(encoding='utf-8')
        write(ROOT/'board_session.json',dict(status='ABI23_REJECTED_ABI22_RESTORED' if restored else 'ABI23_FAILED_RESTORE_NEEDS_CONNECTION',error=str(e),evidence=str(out),sd_written=False));raise

def validate(out,ordered):
    class Box(ct.Structure):_fields_=[(k,ct.c_float) for k in ['x1','y1','x2','y2','score']]+[('cls',ct.c_int),('order',ct.c_int)]
    post=ct.CDLL(str(APP/'host/post.dll'));fusion=ct.CDLL(str(ROOT/'native/fusion.dll'))
    post.road_nms.argtypes=[ct.POINTER(ct.c_float),ct.POINTER(Box),ct.POINTER(Box),ct.c_int,ct.c_float,ct.c_float];post.road_nms.restype=ct.c_int
    post.road_boxes_to400.argtypes=[ct.POINTER(Box),ct.c_int]
    f=fusion.road_vehicle_multiview;f.argtypes=[ct.POINTER(Box),ct.c_int,ct.POINTER(Box),ct.POINTER(ct.c_int),ct.c_float,ct.POINTER(Box),ct.c_int];f.restype=ct.c_int
    def asarray(buf,n):return np.array([[buf[i].x1,buf[i].y1,buf[i].x2,buf[i].y2,buf[i].score,buf[i].cls] for i in range(n)],'<f4').reshape(-1,6)
    results=[]
    for visit,c in enumerate(ordered):
        folder=out/'candidate23'/str(visit);m=struct.unpack('<144I',(folder/'mail.bin').read_bytes())
        assert m[1]==23 and m[2]==3 and m[56]==m[57]==1 and m[72]==m[132]==2 and m[93]==m[99]==2 and m[104]==204
        assert m[6]==m[35]==m[41]==m[74]==0 and m[17]==1483844061 and m[30]==0x7084 and m[40]==0x5640
        assert sha(folder/'raw.u32')==c['views'][0]['input_sha256']
        assert (folder/'enhanced.u32').read_bytes()==(APP/'runtime/cases'/c['name']/'enhanced400.u32').read_bytes()
        buffers=[];counts=[]
        for vi,v in enumerate(c['views']):
            gold=out/'baseline22'/c['name']/str(vi)/'decoded.f32'
            assert (folder/('decoded'+str(vi)+'.f32')).read_bytes()==gold.read_bytes(),(c['name'],vi,'Neural output changed')
            decoded=np.fromfile(gold,'<f4');cand=(Box*6300)();keep=(Box*300)();n=post.road_nms(decoded.ctypes.data_as(ct.POINTER(ct.c_float)),cand,keep,300,.001,.6);assert 0<=n<=300;post.road_boxes_to400(keep,n);buffers.append(keep);counts.append(n)
        tiles=(Box*900)()
        for vi in range(3):
            for j in range(counts[vi+1]):tiles[vi*300+j]=buffers[vi+1][j]
        dest=(Box*300)();n=f(buffers[0],counts[0],tiles,(ct.c_int*3)(*counts[1:]),.75,dest,300);assert 0<=n<=300
        predicted=asarray(dest,n);predicted=predicted[predicted[:,4]>=.25]
        baseline=asarray(buffers[0],counts[0]);baseline=baseline[baseline[:,4]>=.25]
        assert predicted.tobytes()==(folder/'boxes.f32').read_bytes(),(c['name'],'Fusion output changed')
        assert baseline.tobytes()==(folder/'baseline_boxes.f32').read_bytes()
        p=subprocess.run([str(APP/'host/render.exe'),str(folder/'raw.u32'),str(folder/'enhanced.u32'),str(folder/'boxes.f32'),str(folder/'baseline_boxes.f32'),str(folder/'ui.u32'),str(folder/'expected.bgr')],capture_output=True,text=True,timeout=30)
        assert p.returncode==0 and 'GUARDS_PASS' in p.stdout and (folder/'expected.bgr').read_bytes()==(folder/'frame.bgr').read_bytes()
        Image.fromarray(np.fromfile(folder/'frame.bgr',np.uint8).reshape(480,800,3)[:,:,::-1]).save(folder/'lcd_readback.png')
        row=dict(name=c['name'],visit=visit,all4_neural_outputs_byte_exact=True,fused_boxes_byte_exact=True,baseline_boxes_byte_exact=True,enhanced_pixels_byte_exact=True,frame_byte_exact=True,pl_calls=204,baseline_boxes=len(baseline),new_boxes=len(predicted),processing_seconds=(m[19]+(m[20]<<32))/m[18])
        results.append(row);print('ACCURACY_ABI23_CASE_PASS',row,flush=True)
    return results

if __name__=='__main__':main()
