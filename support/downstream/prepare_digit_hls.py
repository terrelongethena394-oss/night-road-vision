"""Export trained integer weights and independent pixel/classification vectors."""
from pathlib import Path
import json
import shutil
import numpy as np
from PIL import Image
import torch
from digit_model import ROOT,IntegerDigit

HERE=Path(__file__).resolve().parent


def sample(rgb,x,y):
    if x<0 or y<0 or x+224>rgb.shape[1] or y+224>rgb.shape[0]:return np.zeros((28,28),np.uint8)
    roi=rgb[y:y+224,x:x+224].astype(np.int64)
    gray=(77*roi[:,:,0]+150*roi[:,:,1]+29*roi[:,:,2]+128)>>8
    return ((gray.reshape(28,8,28,8).sum((1,3))+32)>>6).astype(np.uint8)


def main():
    report=json.loads((ROOT/'training_validation.json').read_text())
    assert report['status']=='PASS'
    q=IntegerDigit(torch.load(ROOT/'digit_model.pth',map_location='cpu',weights_only=True))
    dest=ROOT/'hls';dest.mkdir(exist_ok=True)
    def init(a):return '{'+', '.join(init(x) if np.ndim(x) else str(int(x)) for x in a)+'}'
    header=['// Independently trained digit MLP, fixed weights shared by both instances.','#pragma once']
    for name,a,kind in [('W1',q.w1,'short'),('B1',q.b1,'int'),('W2',q.w2,'short'),('B2',q.b2,'int')]:
        header.append(f'static const {kind} DIGIT_{name}'+''.join(f'[{d}]' for d in a.shape)+' = '+init(a)+';')
    (dest/'digit_weights.h').write_text('\n'.join(header)+'\n',encoding='ascii')
    for name in ('digit_monitor.cpp','digit_monitor.h','tb_digit.cpp'):
        shutil.copy2(HERE/name,dest/name)
    rng=np.random.default_rng(2026102303)
    cases=[]
    cases.append((rng.integers(0,256,(9,17,3),dtype=np.uint8),0,0,0,0xaa))
    cases.append((np.array([[[201,51,11]]],np.uint8),0,0,0,0xaa))
    for label,h,w,x,y,which,ui,alpha in [(8,224,224,0,0,0,0x88,1.0),(3,240,256,16,8,1,0x23,0.15),(5,480,800,480,112,1,0xa5,0.6)]:
        im=Image.open(ROOT/f'demo_targets/digit_{label}.png').convert('L').resize((224,224),Image.Resampling.LANCZOS)
        roi=np.floor(np.array(im)*alpha+0.5).astype(np.uint8)
        rgb=np.full((h,w,3),16,np.uint8);rgb[y:y+224,x:x+224]=roi[:,:,None]
        cases.append((rgb,x,y,which,ui))
    cases.append((rng.integers(0,256,(224,224,3),dtype=np.uint8),0,0,0,0xaa))
    meta=[]
    with (dest/'cases.txt').open('w',encoding='ascii') as f:
        f.write(str(len(cases))+'\n')
        for i,(rgb,x,y,which,ui) in enumerate(cases):
            p,logit=q.infer(sample(rgb,x,y));ordered=np.sort(logit[0]);margin=min(int(ordered[-1]-ordered[-2]),2147483647)
            f.write(f'{rgb.shape[0]} {rgb.shape[1]} {x} {y} {which} {ui} {int(p[0])} {margin}\n')
            np.savetxt(f,rgb.reshape(-1,3),fmt='%d')
            meta.append(dict(index=i,height=rgb.shape[0],width=rgb.shape[1],prediction=int(p[0]),margin=margin,which=which))
    (dest/'cases.json').write_text(json.dumps(meta,indent=2))
    tcl='''set root [file dirname [file normalize [info script]]]
cd $root
open_project digit_project
set_top digit_monitor
add_files digit_monitor.cpp -cflags "-std=c++14"
add_files digit_monitor.h
add_files digit_weights.h
add_files -tb tb_digit.cpp -cflags "-std=c++14"
open_solution solution_100mhz -flow_target vivado
set_part {xc7z020clg400-2}
create_clock -period 10 -name default
csim_design
csynth_design
puts "DIGIT_CSIM_AND_SYNTH_PASS"
exit
'''
    (dest/'build.tcl').write_text(tcl,encoding='ascii')
    for name,command,marker in [('cosim.tcl','cosim_design -rtl verilog -tool xsim -trace_level none','DIGIT_RTL_COSIM_PASS'),('export.tcl','export_design -format ip_catalog -rtl verilog','DIGIT_IP_EXPORT_PASS')]:
        text=f'set root [file dirname [file normalize [info script]]]\ncd $root\nopen_project digit_project\nopen_solution solution_100mhz\n{command}\nputs "{marker}"\nexit\n'
        (dest/name).write_text(text,encoding='ascii')
    print('DIGIT_HLS_INPUTS_READY',sum(c[0].shape[0]*c[0].shape[1] for c in cases),flush=True)


if __name__=='__main__':main()
