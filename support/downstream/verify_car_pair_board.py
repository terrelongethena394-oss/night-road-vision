"""Three injected scenes + three actual camera captures; restore ABI24 on failure."""
import datetime,subprocess
from car_pair_tools import *
PY='E:/FPGA_Enhance_Work/nn_env312/Scripts/python.exe'

def main():
 assert all(sha(APP/n)==h for n,h in read(APP/'runtime_checksums.json').items());out=ROOT/('board_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'));out.mkdir()
 write(out/'protocol.json',dict(status='FROZEN_BEFORE_BOARD_DOWNLOAD',fixed=['real_road','gray96','black'],camera_captures=3,each_packet='8 decoded outputs vs actual C max.001/mean.00002; same frozen source and4views; car post+LCD byte exact;408PL calls',no_accuracy_claim_for_camera_without_labels=True,restore='ABI24 original camera one-shot',sd_written=False))
 scan=out/'scan.tcl';scan.write_text('connect -url tcp:127.0.0.1:3121\nputs [targets]\ntargets -set -filter {name =~ "ARM*#0"} -timeout 10\nputs "CAR_PAIR_ARM_FOUND"\ndisconnect\nexit 0\n',encoding='ascii')
 try:run(scan,out/'scan.log','CAR_PAIR_ARM_FOUND',45)
 except Exception as e:write(ROOT/'board_session.json',dict(status='CAR_PAIR_NOT_DOWNLOADED_NO_TARGET',error=str(e),evidence=str(out),hardware_mutation=False,sd_written=False));raise
 try:
  start(out);results=[]
  for i,name in enumerate(['real_road','gray96','black']):
   source=ROOT/'fixtures/road/source800.bgr' if i==0 else out/(name+'.bgr')
   if i:source.write_bytes(np.full((480,800,3),96 if i==1 else 0,np.uint8).tobytes())
   r=capture(out/('photo_'+str(i)),5,source,i+1)
   if i==0:
    packet=out/'photo_0';fixture=ROOT/'fixtures/road'
    assert (packet/'raw.u32').read_bytes()==(fixture/'raw.u32').read_bytes()
    # ARM/PL probabilities may differ slightly from x86; post is tested exactly
    # against the actual readback logits above, not against another model.
   results.append(r)
  cameras=[capture(out/('camera_'+str(i+1)),4) for i in range(3)];assert [r['capture_id'] for r in cameras]==[1,2,3]
  assert all(cameras[i]['source_bank']!=cameras[i+1]['source_bank'] for i in range(2))
  final=capture(out/'road_revisit',5,ROOT/'fixtures/road/source800.bgr',1)
  for prefix in ['stable_decoded','decoded']:
   for i in range(4):assert (out/'road_revisit'/(prefix+str(i)+'.f32')).read_bytes()==(out/'photo_0'/(prefix+str(i)+'.f32')).read_bytes()
  for name in ['raw.u32','enhanced.u32','baseline.f32','boxes.f32']:assert (out/'road_revisit'/name).read_bytes()==(out/'photo_0'/name).read_bytes()
  receipt=dict(status='ABI26_CAR_PAIR_ALL_INPUTS_AND_OUTPUTS_BOARD_VERIFIED',evidence=str(out),photo_results=results,camera_results=cameras,road_revisit=final,revisited_all8_decodes_pixels_boxes_byte_exact=True,elf_sha256=sha(APP/'road_detail.elf'),bit_sha256=sha(APP/'display.bit'),weights_sha256=read(APP/'arm_complete.json')['weights_sha256'],last_packet=str(out/'road_revisit'),physical_screen_check='Pending user observation',sd_written=False)
  write(ROOT/'board_verified.json',receipt);write(ROOT/'board_session.json',receipt);write(out/'complete.json',receipt);print('CAR_PAIR_BOARD_ACCEPTANCE_COMPLETE',receipt,flush=True)
 except Exception as e:
  write(out/'failure.json',dict(error=str(e),restore='ABI24 camera one-shot',sd_written=False));print('CAR_PAIR_FAILED_RESTORING_ABI24',str(e),flush=True)
  with (out/'restore.log').open('w',encoding='utf-8') as log:p=subprocess.run([PY,str(BASE/'road_camera_snapshot_20261030_r1/tools/camera_snapshot_entry.py'),'start'],stdout=log,stderr=subprocess.STDOUT,timeout=500)
  restored=p.returncode==0 and 'CAMERA_SHOT_READY' in (out/'restore.log').read_text(encoding='utf-8');write(ROOT/'board_session.json',dict(status='CAR_PAIR_FAILED_ABI24_RESTORED' if restored else 'CAR_PAIR_FAILED_RESTORE_NEEDS_CONNECTION',evidence=str(out),error=str(e),sd_written=False));raise

if __name__=='__main__':main()
