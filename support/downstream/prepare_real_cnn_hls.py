"""Isolated CNN HLS build and independent Python reference test vectors."""
from pathlib import Path
import json,shutil
import numpy as np
from PIL import Image
import torch
from train_real_digit_cnn import IntegerCNN,OUT,REAL
from prepare_digit_hls import sample

HERE=Path(__file__).resolve().parent

def main():
    report=json.loads((OUT/'training_report.json').read_text(encoding='utf-8'))
    assert report['official_svhn_test']['float_integer_agreement']>=.99
    q=IntegerCNN(torch.load(OUT/'real_digit_cnn.pth',map_location='cpu',weights_only=True))
    dest=OUT/'hls_corrected';dest.mkdir(exist_ok=True)
    def init(a):return '{'+', '.join(init(x) if np.ndim(x) else str(int(x)) for x in a)+'}'
    header=['// Frozen real-photo CNN candidate; same weights for RAW and ENH.','#pragma once']
    for key,a in q.s.items():
        kind='int' if key.endswith('bias') else 'short'
        header.append(f'static const {kind} CNN_{key.replace(".","_").upper()}'+''.join(f'[{d}]' for d in a.shape)+' = '+init(a)+';')
    (dest/'cnn_weights.h').write_text('\n'.join(header)+'\n',encoding='ascii')
    source=(HERE/'digit_monitor.cpp').read_text(encoding='utf-8').replace('#include "digit_weights.h"','#include "real_cnn_kernel.h"')
    start=source.index('    ap_int<40> hidden_acc[32];');end=source.index('    for(int i=0;i<784;++i)',start)
    source=source[:start]+source[end:]
    start=source.index('    for(int j=0;j<32;++j)');end=source.index('    frame_count=',start)
    source=source[:start]+'    real_cnn_infer(sums,prediction,margin);\n'+source[end:]
    # The old result expression referred to a local MLP label.
    source=source.replace('ap_uint<32>(label)','ap_uint<32>(prediction)')
    assert 'DIGIT_' not in source and 'hidden_acc' not in source
    (dest/'digit_monitor.cpp').write_text(source,encoding='ascii')
    for name in ('digit_monitor.h','real_cnn_kernel.h'):shutil.copy2(HERE/name,dest/name)
    manifest=json.loads((REAL/'case_manifest.json').read_text(encoding='utf-8'))
    cases=[(np.zeros((9,17,3),np.uint8),0,0,0,0xaa),
        (np.full((224,224,3),255,np.uint8),0,0,0,0xaa)]
    for index,key,which,gain in [(0,'raw',0,1),(10,'raw',1,.125),(20,'enh',0,1),(32,'raw',1,1)]:
        c=manifest['cases'][index]
        path=REAL/'inputs'/(c['id']+'.png') if key=='raw' else REAL/'pc_reference_previews'/(c['id']+'_PC_REFERENCE.png')
        rgb=np.array(Image.open(path).convert('RGB'))
        if gain!=1:rgb=np.floor(rgb.astype(np.float64)*gain+.5).astype(np.uint8)
        cases.append((rgb,480,112,which,0xaa))
    records=[]
    with (dest/'cases.txt').open('w',encoding='ascii') as f:
        f.write(str(len(cases))+'\n')
        for i,(rgb,x,y,which,ui) in enumerate(cases):
            p,logits=q.infer(sample(rgb,x,y));order=np.sort(logits[0]);margin=min(int(order[-1]-order[-2]),2147483647)
            f.write(f'{rgb.shape[0]} {rgb.shape[1]} {x} {y} {which} {ui} {int(p[0])} {margin}\n')
            np.savetxt(f,rgb.reshape(-1,3),fmt='%d')
            records.append(dict(index=i,height=rgb.shape[0],width=rgb.shape[1],prediction=int(p[0]),margin=margin))
    (dest/'cases.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    tb=(HERE/'tb_digit.cpp').read_text(encoding='utf-8').replace('E:/FPGA_Enhance_Work/digit_recognition_20261023/hls/cases.txt',(dest/'cases.txt').as_posix())
    (dest/'tb_digit.cpp').write_text(tb,encoding='ascii')
    (dest/'build.tcl').write_text('''set root [file dirname [file normalize [info script]]]
cd $root
open_project real_cnn_project
set_top digit_monitor
add_files digit_monitor.cpp -cflags "-std=c++14"
add_files digit_monitor.h
add_files real_cnn_kernel.h
add_files cnn_weights.h
add_files -tb tb_digit.cpp -cflags "-std=c++14"
open_solution solution_100mhz -flow_target vivado
set_part {xc7z020clg400-2}
create_clock -period 10 -name default
csim_design
csynth_design
puts "REAL_CNN_CSIM_SYNTH_PASS"
exit
''',encoding='ascii')
    build=(dest/'build.tcl').read_text(encoding='ascii')
    (dest/'verify.tcl').write_text(build.replace('puts "REAL_CNN_CSIM_SYNTH_PASS"',
        'cosim_design -rtl verilog -tool xsim -trace_level none\nputs "REAL_CNN_CORRECTED_FULL_VERIFY_PASS"'),encoding='ascii')
    for name,command in [('cosim.tcl','cosim_design -rtl verilog -tool xsim -trace_level none'),
        ('export.tcl','export_design -format ip_catalog -rtl verilog -vendor fpga.user -library hls -version 1.0 -ipname real_digit_monitor')]:
        (dest/name).write_text('set root [file dirname [file normalize [info script]]]\ncd $root\nopen_project real_cnn_project\nopen_solution solution_100mhz\n'+command+'\nexit\n',encoding='ascii')
    print('REAL_CNN_HLS_PREPARED',len(cases),flush=True)

if __name__=='__main__':main()
