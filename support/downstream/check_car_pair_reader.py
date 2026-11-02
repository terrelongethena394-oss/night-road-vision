"""Exercise packet checker offline, including corruption rejection; NO board data."""
import os,shutil,struct,subprocess,sys
import numpy as np
from car_pair_common import *
sys.path.insert(0,str(ROOT/'tools'))
from car_pair_tools import validate
from _capture_io import words,fnv
from road_accuracy_common import sensor400

def main():
 out=ROOT/'offline_packet_checker';out.mkdir();fixture=ROOT/'fixtures/road';shutil.copy2(fixture/'source800.bgr',out/'source800.bgr');src=np.fromfile(out/'source800.bgr',np.uint8).reshape(480,800,3)[:,:,::-1].copy();raw=((src.astype(np.uint16).reshape(240,2,400,2,3).sum(axis=(1,3))+2)//4).astype(np.uint8);views=[raw]+[src[120:360,x:x+400] for x in [0,200,400]]
 for i,v in enumerate(views):words(v).tofile(out/('raw.u32' if not i else f'tile{i-1}.u32'))
 for name in ['enhanced.u32','ui.u32','frame.bgr']:shutil.copy2(fixture/name,out/name)
 shutil.copy2(fixture/'stable.f32',out/'baseline.f32');shutil.copy2(fixture/'candidate.f32',out/'boxes.f32');env=dict(os.environ);env['PATH']='E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin;'+env['PATH']
 for model,weight,prefix in [('stable','weights.f32','stable_decoded'),('candidate','new_weights.f32','decoded')]:
  for i in range(4):
   dest=out/'reference_generation'/model/str(i);dest.mkdir(parents=True);ip=out/('raw.u32' if i==0 else f'tile{i-1}.u32');p=subprocess.run([str(APP/'host/road_ap.exe'),str(APP/'runtime'/weight),str(ip),str(dest)],capture_output=True,text=True,env=env);assert p.returncode==0 and 'ROAD_FP32_HOST_DONE' in p.stdout;shutil.copy2(dest/'decoded.f32',out/(prefix+str(i)+'.f32'))
 proof=read(APP/'arm_complete.json');meta=read(fixture/'fixture.json');m=[0]*176
 for k,v in {0:0x524f4144,1:26,2:3,8:0x1B000000,16:fnv((out/'raw.u32').read_bytes()),17:proof['weight_fnv']['candidate'],18:1000000,30:0x7084,40:0x5640,52:meta['candidate_cars'],56:1,57:1,72:2,93:2,99:2,104:408,132:2,142:meta['stable_cars'],144:0x1A300000,145:fnv((out/'source800.bgr').read_bytes()),148:fnv((out/'source800.bgr').read_bytes()),149:1152000,150:800,151:480,155:5,156:1,158:1,159:0x46524f5a,160:0x1B000000,161:proof['weight_fnv']['stable'],162:proof['weight_fnv']['candidate'],163:2,164:0x1B800000,169:204,170:204,171:meta['stable_cars'],172:meta['candidate_cars']}.items():m[k]=v
 for i in range(3):m[133+i]=fnv((out/f'tile{i}.u32').read_bytes())
 (out/'mail.bin').write_bytes(struct.pack('<176I',*m));validate(out,5,True)
 failures=[]
 for label,file,offset in [('raw_corruption','raw.u32',0),('weight_metadata','mail.bin',162*4),('car_output_corruption','boxes.f32',0)]:
  dest=ROOT/('checker_reject_'+label);dest.mkdir()
  for p in out.iterdir():
   if p.is_file():shutil.copy2(p,dest/p.name)
  path=dest/file;data=bytearray(path.read_bytes());data[offset]^=1;path.write_bytes(data)
  try:validate(dest,5,False)
  except AssertionError:failures.append(label)
  else:raise AssertionError('Corrupt packet accepted: '+label)
 assert len(failures)==3
 write(ROOT/'reader_complete.json',dict(status='OFFLINE_PACKET_CHECKER_VALID_AND_CORRUPTED_CASES_PASS',no_board_access=True,synthetic_mailbox=True,reference='All8 neural decoded arrays from actual portable C, artificial metadata/timing for checker only',valid_packet_passed=True,rejected=failures,not_board_verification=True));print('CAR_PAIR_OFFLINE_READER_PROVED',failures,flush=True)

if __name__=='__main__':main()
