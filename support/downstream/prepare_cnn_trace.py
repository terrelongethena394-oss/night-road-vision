"""Observe every CNN activation and score; compare C/RTL to Python arrays."""
from pathlib import Path
import json,shutil,sys
import numpy as np
import torch
from train_real_digit_cnn import OUT,IntegerCNN

RAW='--raw' in sys.argv
SIZE=12587 if RAW else 3179
DEST=OUT/('layer_trace_raw' if RAW else 'layer_trace')
HERE=Path(__file__).resolve().parent

def main():
    DEST.mkdir(exist_ok=True)
    shutil.copy2(OUT/'hls/cnn_weights.h',DEST/'cnn_weights.h')
    text=(HERE/'real_cnn_kernel.h').read_text(encoding='utf-8')
    text=text.replace('int &prediction,int &margin)', 'int &prediction,int &margin,long long trace[3179])')
    text=text.replace('    for(int base=0;base<8;base+=4)', '''    for(int i=0;i<784;++i)trace[i]=pixels[i/28][i%28];
    for(int base=0;base<8;base+=4)''',1)
    text=text.replace('    for(int base=0;base<16;base+=4)', '''    for(int c=0;c<8;++c)for(int y=0;y<14;++y)for(int x=0;x<14;++x)
        trace[784+(c*14+y)*14+x]=pool1[c][y][x];
    for(int base=0;base<16;base+=4)''',1)
    text=text.replace('    for(int base=0;base<32;base+=4)', '''    for(int c=0;c<16;++c)for(int y=0;y<7;++y)for(int x=0;x<7;++x)
        trace[2352+(c*7+y)*7+x]=pool2[c][y][x];
    for(int base=0;base<32;base+=4)''',1)
    text=text.replace('    ap_int<40> best=', '''    for(int j=0;j<32;++j)trace[3136+j]=hidden[j];
    ap_int<40> best=''',1)
    text=text.replace('        if(score>best)', '        trace[3168+k]=score.to_int64();\n        if(score>best)',1)
    if RAW:
        token='                ap_uint<20> z=cnn_activate(acc[l]);'
        parts=text.split(token);assert len(parts)==3
        text=parts[0]+'                trace[3179+((base+l)*28+py*2+dy)*28+px*2+dx]=acc[l].to_int64();\n'+token+parts[1]+'                trace[9451+((base+l)*14+py*2+dy)*14+px*2+dx]=acc[l].to_int64();\n'+token+parts[2]
        text=text.replace('trace[3179])','trace[12587])')
    (DEST/'trace_kernel.h').write_text(text,encoding='ascii')
    (DEST/'cnn_trace.cpp').write_text('''#include "trace_kernel.h"
void cnn_trace(unsigned char input[784],long long trace[3179],int &p,int &m) {
    ap_uint<14> sums[784];
    for(int i=0;i<784;++i)sums[i]=ap_uint<14>(input[i])*64;
    real_cnn_infer(sums,p,m,trace);
}
'''.replace('trace[3179]',f'trace[{SIZE}]'),encoding='ascii')
    q=IntegerCNN(torch.load(OUT/'real_digit_cnn.pth',map_location='cpu',weights_only=True))
    arrays=[np.zeros((28,28),np.int64),np.full((28,28),255,np.int64),np.random.default_rng(2026102601).integers(0,256,(28,28),dtype=np.int64)]
    with (DEST/'vectors.txt').open('w',encoding='ascii') as f:
        f.write(str(len(arrays))+'\n')
        for a in arrays:
            z1=q.conv(a.reshape(1,1,28,28),'conv1');z2=q.conv(z1,'conv2')
            h=q.activate(z2.reshape(1,-1)@q.s['fc1.weight'].T+q.s['fc1.bias'],'fc1')
            logits=h@q.s['fc2.weight'].T+q.s['fc2.bias']
            trace=np.concatenate([a.ravel(),z1.ravel(),z2.ravel(),h.ravel(),logits.ravel()])
            if RAW:
                def raw_acc(x,name):
                    windows=np.lib.stride_tricks.sliding_window_view(np.pad(x,((0,0),(0,0),(1,1),(1,1))),(3,3),axis=(2,3))
                    return np.einsum('nchwkl,ockl->nohw',windows,q.s[name+'.weight'],optimize=True)+q.s[name+'.bias'][None,:,None,None]
                trace=np.concatenate([trace,raw_acc(a.reshape(1,1,28,28),'conv1').ravel(),raw_acc(z1,'conv2').ravel()])
            assert len(trace)==SIZE
            pred=int(logits.argmax(1)[0]);order=np.sort(logits[0]);margin=min(int(order[-1]-order[-2]),2147483647)
            f.write(f'{pred} {margin}\n');np.savetxt(f,a.ravel(),fmt='%d');np.savetxt(f,trace,fmt='%d')
    tb='''#include <fstream>
#include <iostream>
void cnn_trace(unsigned char input[784],long long trace[3179],int &p,int &m);
int main() {
    std::ifstream f("VECTORS");std::ofstream output("trace_actual.txt");
    int n;f>>n;int errors=0;
    int edges[6]={0,784,2352,3136,3168,3179};
    const char* names[5]={"pixels","pool1","pool2","hidden","logits"};
    for(int t=0;t<n;++t) {
        unsigned char input[784];long long actual[3179],expected[3179];
        int ep,em;f>>ep>>em;
        for(int i=0;i<784;++i){int v;f>>v;input[i]=v;}
        for(int i=0;i<3179;++i)f>>expected[i];
        int p=-1,m=-1;cnn_trace(input,actual,p,m);
        output<<t<<" "<<p<<" "<<m<<std::endl;
        for(int i=0;i<3179;++i)output<<actual[i]<<std::endl;
        std::cout<<"TRACE_RESULT case="<<t<<" pred="<<p<<" margin="<<m<<" expected="<<ep<<","<<em<<std::endl;
        for(int s=0;s<5;++s) {
            int bad=0;
            for(int i=edges[s];i<edges[s+1];++i)if(actual[i]!=expected[i]) {
                if(bad<4)std::cout<<"TRACE_DIFFERENCE case="<<t<<" stage="<<names[s]<<" index="<<i-edges[s]<<" actual="<<actual[i]<<" expected="<<expected[i]<<std::endl;
                ++bad;
            }
            std::cout<<"TRACE_STAGE case="<<t<<" stage="<<names[s]<<" bad="<<bad<<std::endl;
            errors+=bad;
        }
        if(p!=ep||m!=em)++errors;
    }
    std::cout<<"TRACE_DONE errors="<<errors<<std::endl;return errors?2:0;
}
'''.replace('VECTORS',(DEST/'vectors.txt').as_posix())
    if RAW:
        tb=tb.replace('[3179]',f'[{SIZE}]').replace('i<3179',f'i<{SIZE}')
        tb=tb.replace('edges[6]={0,784,2352,3136,3168,3179}', 'edges[8]={0,784,2352,3136,3168,3179,9451,12587}')
        tb=tb.replace('names[5]={"pixels","pool1","pool2","hidden","logits"}', 'names[7]={"pixels","pool1","pool2","hidden","logits","conv1_acc","conv2_acc"}').replace('s<5','s<7')
    (DEST/'tb_trace.cpp').write_text(tb,encoding='ascii')
    (DEST/'build.tcl').write_text('''set root [file dirname [file normalize [info script]]]
cd $root
open_project trace_project
set_top cnn_trace
add_files cnn_trace.cpp -cflags "-std=c++14"
add_files trace_kernel.h
add_files cnn_weights.h
add_files -tb tb_trace.cpp -cflags "-std=c++14"
open_solution solution -flow_target vivado
set_part {xc7z020clg400-2}
create_clock -period 10 -name default
csim_design
csynth_design
cosim_design -rtl verilog -tool xsim -trace_level none
exit
''',encoding='ascii')
    print('ALL_LAYER_TRACE_READY',len(arrays),SIZE,flush=True)

if __name__=='__main__':main()
