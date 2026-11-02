"""Known validation fixtures and explicitly simulated reader tests, not hardware proof."""
from pathlib import Path
import os,struct,subprocess
import numpy as np
from PIL import Image
from balanced_board_tools import ROOT,APP,STUDY,fnv
from car_box_refine_common import BASE,read,write,sha
from road_accuracy_common import sensor400
from road_numpy_eval import correct
from camera_snapshot_tools import words
from validate_balanced_board import validate,decode_boxes
from prove_balanced_car_c import RefinerC
from prove_car_zoom_c import ZoomC
from confirm_car_zoom_native import BaseFusion
from study_car_zoom_20261030 import map_zoom,XS
from evaluate_car_boxrefine import eligible
from audit_bright_detector_20261030 import Enhancer

def op(row):
 p=np.asarray(row['detections'],np.float32).reshape(-1,6);p=p[p[:,4]>=.25];g=np.asarray(row['ground_truth'],np.float32).reshape(-1,5)
 t=int(correct(p,g,np.array([.5],np.float32))[0].sum());return t,len(p)-t

def produce(out,sensor):
 out.mkdir(parents=True);proof=read(APP/'arm_complete.json');sensor=np.ascontiguousarray(sensor,np.uint8);source=np.ascontiguousarray(sensor[:,:,::-1]).tobytes();(out/'source800.bgr').write_bytes(source)
 full=((sensor.astype(np.uint16).reshape(240,2,400,2,3).sum(axis=(1,3))+2)//4).astype(np.uint8);z=full.astype(np.uint64)
 dark=int((54*z[:,:,0]+183*z[:,:,1]+19*z[:,:,2]).sum())<=48*256*96000
 images=[full]+[sensor[120:360,x:x+400] for x in [0,200,400]];files=['raw.u32']+[f'raw_tile{i}.u32' for i in range(3)];pix=ZoomC()
 if dark:images.extend(pix.image(sensor,x,152) for x in XS);files.extend(f'zoom{i}.u32' for i in range(3))
 env=dict(os.environ);env['PATH']='E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin;'+env['PATH'];exe=BASE/'road_local_enhance_20261029_r2/host/road_ap.exe';boxes=[]
 for i,(im,name) in enumerate(zip(images,files)):
  words(im).tofile(out/name);folder=out/'producer_native'/str(i);folder.mkdir(parents=True)
  p=subprocess.run([str(exe),str(APP/'runtime/weights.f32'),str(out/name),str(folder)],capture_output=True,text=True,env=env);assert p.returncode==0 and 'ROAD_FP32_HOST_DONE' in p.stdout
  decode=np.fromfile(folder/'decoded.f32','<f4');decode.tofile(out/(f'decoded_base{i}.f32' if i<4 else f'decoded_zoom{i-4}.f32'));boxes.append(decode_boxes(decode))
 base=BaseFusion().run(boxes[0],boxes[1:4],.75);base=base[(base[:,5]==1)&(base[:,4]>=.25)];pred=np.zeros((900,5),np.float32);count=0;refiner=RefinerC();refiner.begin(sensor)
 if dark:
  mapped=[]
  for j,local in enumerate(boxes[4:]):
   pp=[]
   for i,b in enumerate(local):
    mappedbox=map_zoom(np.asarray([b]),XS[j],152)
    if not len(mappedbox):continue
    b=mappedbox[0]
    if eligible(b,base):
     image,meta=refiner.crop(b);pred[j*300+i]=refiner.predict(image,meta);count+=1
    pp.append(pred[j*300+i])
   mapped.append(np.asarray(pp,np.float32).reshape(-1,5))
  p=read(STUDY/'selected.json')['chosen']['source'];candidate=refiner.fuse(base,boxes[4:],mapped,p);candidate=candidate[candidate[:,4]>=.25]
 else:candidate=base.copy()
 refiner.end();base.tofile(out/'baseline.f32');candidate.tofile(out/'boxes.f32');pred.tofile(out/'refiner_outputs.f32');words(Enhancer().run(full)).tofile(out/'enhanced.u32')
 m=np.zeros(208,np.uint32);m[0]=0x524f4144;m[1]=28;m[2]=3;m[4]=1;m[17]=m[161]=proof['weight_fnv']['detector'];m[162]=m[192]=m[193]=proof['weight_fnv']['refiner']
 m[18]=333333333;m[19]=123456789;m[30]=0x7084;m[32]=0x02000000;m[40]=0x5640;m[52]=m[172]=len(candidate);m[56]=1;m[57]=1;m[72]=m[132]=2;m[93]=m[99]=2
 m[104]=357 if dark else 204;m[142]=m[171]=len(base);m[144]=0x1A300000;m[145]=m[148]=fnv(source);m[146]=0xffffffff;m[149:152]=[1152000,800,480];m[155]=5;m[156]=m[158]=1;m[159]=0x46524f5a;m[163]=1;m[169]=204;m[170]=153 if dark else 0
 m[176:179]=[0x1C000000,0x1C120000,152];m[179]=0x3f266666;m[186:189]=[0x1C200000,0x1C240000,0x1C250000];m[189]=int(dark);m[190]=3 if dark else 0;m[191]=17549;m[194]=count;m[195]=5;m[196:200]=[0x3f000000,0x3dcccccd,0,0x42414c32]
 for i,name in enumerate(files[:4]):m[16 if i==0 else 132+i]=fnv((out/name).read_bytes())
 if dark:
  for i in range(3):m[180+i]=fnv((out/f'zoom{i}.u32').read_bytes());m[183+i]=len(boxes[4+i])
 m.tofile(out/'mail.bin');ui=np.array([1,1,1,12345,0,0,len(candidate),1,1,1,0,int(full.mean()),0,48,258,2,len(base)],'<u4');ui.tofile(out/'ui.u32')
 p=subprocess.run([str(APP/'host/render.exe'),str(out/'raw.u32'),str(out/'enhanced.u32'),str(out/'boxes.f32'),str(out/'baseline.f32'),str(out/'ui.u32'),str(out/'frame.bgr')],capture_output=True,text=True,env=env);assert p.returncode==0 and 'GUARDS_PASS' in p.stdout
 (out/'packet_origin.txt').write_text('SIMULATED_HOST_PACKET_NOT_BOARD_PROOF\n',encoding='ascii')
 result=validate(out,5,physical=False);assert result['physical_readback'] is False
 try:validate(out,5,physical=True)
 except AssertionError:pass
 else:raise AssertionError('Simulated packet incorrectly accepted as board proof')
 return result

def main():
 fixtures=ROOT/'fixtures';fixtures.mkdir();study=STUDY/'confirmation';manifest=read(study/'fresh/manifest.json');names={r['name'] for r in manifest if r['cohort']=='low'}
 before={r['name']:r for r in read(study/'baseline_predictions.json')};after={r['name']:r for r in read(study/'candidate_predictions.json')};diff=[]
 for name in names:
  a=op(before[name]);b=op(after[name]);diff.append(dict(name=name,baseline=a,candidate=b,delta_tp=b[0]-a[0],delta_fp=b[1]-a[1]))
 chosen=[max(diff,key=lambda r:(r['delta_tp'],-r['delta_fp'])),max(diff,key=lambda r:r['delta_fp'])];records=[]
 for i,r in enumerate(chosen):
  sensor,_=sensor400(study/'fresh/images'/r['name']);p=fixtures/('road'+str(i)+'.bgr');np.ascontiguousarray(sensor[:,:,::-1]).tofile(p)
  Image.fromarray(sensor).save(fixtures/('road'+str(i)+'.png'));records.append(dict(file=p.name,source=r,source_sha256=sha(study/'fresh/images'/r['name']),fixture_sha256=sha(p)))
 for name,v in [('gray96',96),('black',0)]:np.full((480,800,3),v,np.uint8).tofile(fixtures/(name+'.bgr'))
 write(fixtures/'manifest.json',dict(selected_after_frozen_test=True,examples_not_accuracy_estimate=True,roads=records))
 out=ROOT/'simulated_reader_tests';out.mkdir();sensor,_=sensor400(study/'fresh/images'/chosen[0]['name'])
 a=produce(out/'dark',sensor);b=produce(out/'bright',np.full((480,800,3),96,np.uint8))
 write(ROOT/'reader_smoke.json',dict(status='SIMULATED_READER_TESTS_PASS_NOT_BOARD_PROOF',packets=[a,b],physical_readback=False,
  provenance_guard_rejects_simulation=True,hardware_access=False,sd_written=False))
 print('BALANCED_READER_SMOKE_COMPLETE_NOT_BOARD_PROOF',len(a['detector_native_comparisons']),len(b['detector_native_comparisons']),flush=True)

if __name__=='__main__':main()
