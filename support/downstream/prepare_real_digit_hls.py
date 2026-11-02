"""Prepare isolated 64-hidden-unit HLS candidate; never touch old board files."""
from pathlib import Path
import json,shutil
import numpy as np
from PIL import Image
import torch
from digit_model import IntegerDigit
from prepare_digit_hls import sample

ROOT=Path('E:/FPGA_Enhance_Work/real_digit_training_20261025')
REAL=Path('E:/FPGA_Enhance_Work/real_scene_test_scaled_20261025')
HERE=Path(__file__).resolve().parent

def main():
    report=json.loads((ROOT/'training_report.json').read_text(encoding='utf-8'))
    assert report['official_svhn_test']['integer_float_agreement']>=.99
    q=IntegerDigit(torch.load(ROOT/'real_digit_model.pth',map_location='cpu',weights_only=True))
    assert q.w1.shape==(64,784) and q.w2.shape==(11,64)
    dest=ROOT/'hls';dest.mkdir(exist_ok=True)
    def init(a):return '{'+', '.join(init(x) if np.ndim(x) else str(int(x)) for x in a)+'}'
    header=['// Frozen SVHN train-split real-photo candidate; shared RAW/ENH weights.','#pragma once']
    for name,a,kind in [('W1',q.w1,'short'),('B1',q.b1,'int'),('W2',q.w2,'short'),('B2',q.b2,'int')]:
        header.append(f'static const {kind} DIGIT_{name}'+''.join(f'[{d}]' for d in a.shape)+' = '+init(a)+';')
    (dest/'digit_weights.h').write_text('\n'.join(header)+'\n',encoding='ascii')
    source=(HERE/'digit_monitor.cpp').read_text(encoding='utf-8')
    start=source.index('    ap_int<40> hidden_acc[32];')
    stop=source.index('    for(int i=0;i<784;++i)',start)
    source=source[:start]+'''    ap_uint<20> hidden[64];
// Four reused lanes: avoid duplicating 64 multipliers in each video instance.
#pragma HLS ARRAY_PARTITION variable=DIGIT_W1 cyclic factor=4 dim=1
'''+source[stop:]
    start=source.index('    for(int j=0;j<32;++j)')
    stop=source.index('    ap_int<40> best=',start)
    source=source[:start]+'''    hidden_groups:for(int base=0;base<64;base+=4) {
        ap_int<40> acc[4];
#pragma HLS ARRAY_PARTITION variable=acc complete
        for(int lane=0;lane<4;++lane) {
#pragma HLS UNROLL
            acc[lane]=DIGIT_B1[base+lane];
        }
        infer_input:for(int i=0;i<784;++i) {
#pragma HLS PIPELINE II=1
            ap_uint<8> value=(ap_uint<15>(sums[i])+32)>>6;
            for(int lane=0;lane<4;++lane) {
#pragma HLS UNROLL
                // Explicitly signed positive input and widened product.
                ap_int<17> weight=DIGIT_W1[base+lane][i];
                ap_int<9> input_value=value;
                ap_int<26> product=weight*input_value;
#pragma HLS BIND_OP variable=product op=mul impl=fabric
                acc[lane]+=ap_int<40>(product);
            }
        }
        for(int lane=0;lane<4;++lane) {
#pragma HLS UNROLL
            ap_int<40> value=round12(acc[lane]);
            if(value<0)value=0;
            if(value>1048575)value=1048575;
            hidden[base+lane]=value;
        }
    }
'''+source[stop:]
    source=source.replace('j<32','j<64').replace('            score+=hidden[j]*ap_int<16>(DIGIT_W2[k][j]);',
'''            ap_int<21> positive_hidden=hidden[j];
            ap_int<17> weight=DIGIT_W2[k][j];
            ap_int<38> product=positive_hidden*weight;
#pragma HLS BIND_OP variable=product op=mul impl=fabric
            score+=ap_int<40>(product);''')
    assert 'hidden_acc' not in source and 'j<32' not in source
    (dest/'digit_monitor.cpp').write_text(source,encoding='ascii')
    shutil.copy2(HERE/'digit_monitor.h',dest/'digit_monitor.h')
    manifest=json.loads((REAL/'case_manifest.json').read_text(encoding='utf-8'))
    cases=[(np.zeros((9,17,3),np.uint8),0,0,0,0xaa),
        (np.full((224,224,3),255,np.uint8),0,0,0,0xaa)]
    for index,key,which in [(0,'raw',0),(10,'raw',1),(20,'enh',0),(32,'raw',1)]:
        c=manifest['cases'][index]
        path=(REAL/'inputs'/(c['id']+'.png')) if key=='raw' else (REAL/'pc_reference_previews'/(c['id']+'_PC_REFERENCE.png'))
        cases.append((np.array(Image.open(path).convert('RGB')),480,112,which,0xaa))
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
    tcl='''set root [file dirname [file normalize [info script]]]
cd $root
open_project real_digit_project
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
puts "REAL_DIGIT_CSIM_SYNTH_PASS"
exit
'''
    (dest/'build.tcl').write_text(tcl,encoding='ascii')
    for name,command in [('cosim.tcl','cosim_design -rtl verilog -tool xsim -trace_level none'),('export.tcl','export_design -format ip_catalog -rtl verilog')]:
        (dest/name).write_text('set root [file dirname [file normalize [info script]]]\ncd $root\nopen_project real_digit_project\nopen_solution solution_100mhz\n'+command+'\nexit\n',encoding='ascii')
    print('REAL_DIGIT_HLS_PREPARED',len(cases),flush=True)

if __name__=='__main__':main()
