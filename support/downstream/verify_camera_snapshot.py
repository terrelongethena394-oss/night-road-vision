"""Protected camera capture acceptance; restore ABI23 on failure after loading."""
import datetime,shutil,subprocess
from camera_snapshot_tools import *
PY='E:/FPGA_Enhance_Work/nn_env312/Scripts/python.exe'
def main():
 assert all(sha(APP/n)==h for n,h in read(APP/'runtime_checksums.json').items())
 out=ROOT/('board_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'));out.mkdir()
 write(out/'protocol.json',dict(cases=['babf991d-b4102dd2','b484aa24-d70cf6e5','control_black'],native_neural_max_abs=.001,native_neural_mean_abs=.00002,same_photos_vs_actual_ABI23='All4 decoded and point-box bytes must be identical',camera='3 separate VDMA captures; protected bank equals private source exactly; input construction and outputs validated',sd_written=False))
 scan=out/'scan.tcl';scan.write_text('connect -url tcp:127.0.0.1:3121\nputs [targets]\ntargets -set -filter {name =~ "ARM*#0"} -timeout 10\nputs "SNAPSHOT_ARM_FOUND"\ndisconnect\nexit 0\n',encoding='ascii')
 try:run(scan,out/'scan.log','SNAPSHOT_ARM_FOUND',45)
 except Exception as e:
  write(ROOT/'board_session.json',dict(status='ABI24_NOT_DOWNLOADED_NO_TARGET',error=str(e),evidence=str(out),hardware_mutation=False,sd_written=False));print('CAMERA_SNAPSHOT_NEEDS_CONNECTION',str(e),flush=True);return
 try:
  print('CAMERA_SNAPSHOT_LOADING',out,flush=True);start(out)
  reference=read(OLD/'board_verified.json');results=[]
  for i,name in enumerate(['babf991d-b4102dd2','b484aa24-d70cf6e5','control_black']):
   image=np.array(Image.open(OLD/'firmware/runtime/cases'/name/'sensor800.png').convert('RGB'));source=out/(name+'.bgr');source.write_bytes(image[:,:,::-1].tobytes())
   packet=out/('photo_'+str(i));r=capture(packet,5,source,i+1)
   oldrow=next(v for v in reference['results'] if v['name']==name);gold=Path(reference['evidence'])/'candidate23'/str(oldrow['visit'])
   assert (packet/'raw.u32').read_bytes()==(gold/'raw.u32').read_bytes()
   for j in range(4):assert (packet/('decoded'+str(j)+'.f32')).read_bytes()==(gold/('decoded'+str(j)+'.f32')).read_bytes()
   assert (packet/'boxes.f32').read_bytes()==(gold/'boxes.f32').read_bytes() and (packet/'baseline.f32').read_bytes()==(gold/'baseline_boxes.f32').read_bytes()
   r['actual_abi23_all4_decodes_and_boxes_byte_exact']=True;write(packet/'verified.json',r);results.append(r)
   print('CAMERA_SNAPSHOT_PHOTO_GOLD_PASS',name,flush=True)
  cameras=[]
  for i in range(3):cameras.append(capture(out/('camera_'+str(i+1)),4))
  assert [r['capture_id'] for r in cameras]==[1,2,3]
  assert all(cameras[i]['source_bank']!=cameras[i+1]['source_bank'] for i in range(2))
  result=dict(status='ABI24_CAMERA_ONESHOT_ALL_INPUTS_AND_OUTPUTS_BOARD_VERIFIED',evidence=str(out),photo_results=results,camera_results=cameras,all3_camera_banks_byte_exact=True,all_inputs_and_frozen_sources_verified=True,camera_source_hashes_differ=len({r['source_sha256'] for r in cameras})>1,elf_sha256=sha(APP/'road_detail.elf'),bit_sha256=sha(APP/'display.bit'),weights_sha256=sha(APP/'runtime/weights.f32'),final_packet=str(out/'camera_3'),physical_panel_check='Not repeated; actual camera DMA, framebuffer and VDMA verified',sd_written=False)
  write(ROOT/'board_verified.json',result);write(ROOT/'board_session.json',result);write(out/'complete.json',result)
  print('CAMERA_SNAPSHOT_BOARD_ACCEPTANCE_COMPLETE',result,flush=True)
 except Exception as e:
  write(out/'failure.json',dict(error=str(e),restore='Verified ABI23 fixed-photo demo',sd_written=False));print('CAMERA_SNAPSHOT_FAILED_RESTORING_ABI23',str(e),flush=True)
  with (out/'restore.log').open('w',encoding='utf-8') as log:p=subprocess.run([PY,str(OLD/'road_accuracy_entry.py'),'start','5'],stdout=log,stderr=subprocess.STDOUT,timeout=400)
  restored=p.returncode==0 and 'ACCURACY_PHOTO_READY' in (out/'restore.log').read_text(encoding='utf-8')
  write(ROOT/'board_session.json',dict(status='ABI24_REJECTED_ABI23_RESTORED' if restored else 'ABI24_FAILED_RESTORE_NEEDS_CONNECTION',error=str(e),evidence=str(out),sd_written=False));raise
if __name__=='__main__':main()
