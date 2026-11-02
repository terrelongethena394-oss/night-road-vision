"""Fast synthesized final-layer check using the exact whole-network score code."""
from pathlib import Path
import shutil
import numpy as np
from train_real_digit_cnn import OUT

ROOT=Path('E:/FPGA_Enhance_Work/cnn_score_probe_20261025')
HERE=Path(__file__).resolve().parent

def main():
    ROOT.mkdir(exist_ok=True)
    shutil.copy2(OUT/'hls_score64/cnn_weights.h',ROOT/'cnn_weights.h')
    source=(HERE/'real_cnn_kernel.h').read_text(encoding='ascii')
    block=source[source.index('    long long best='):source.rindex('}')]
    block=block.replace('ap_int<21> value=hidden[j];','ap_int<21> value=ap_uint<20>(hidden[j]);')
    top='#include <ap_int.h>\n#include "cnn_weights.h"\nvoid score_probe(unsigned int hidden[32],int &prediction,int &margin) {\n'+block+'}\n'
    (ROOT/'score_probe.cpp').write_text(top,encoding='ascii')
    tokens=(OUT/'layer_trace/trace_project/solution/csim/build/trace_actual.txt').read_text().split();at=0;mem=[];expected=[]
    for case in range(3):
        assert int(tokens[at])==case
        expected.append([int(tokens[at+1]),int(tokens[at+2])]);a=np.array(tokens[at+3:at+3182],np.int64);at+=3182
        mem.extend(a[3136:3168].tolist())
    np.savetxt(ROOT/'hidden.mem',np.array(mem),fmt='%08x')
    tb='''`timescale 1ns/1ps
module tb_score_probe;
reg clk=0;always #5 clk=~clk;
reg rst=1,start=0;wire done,idle,ready;
wire [4:0] address;wire ce;reg [31:0] data=0;
wire [31:0] prediction,margin;wire pv,mv;
reg [31:0] mem[0:95];integer phase=0,cycles=0;
score_probe dut(.ap_clk(clk),.ap_rst(rst),.ap_start(start),.ap_done(done),.ap_idle(idle),.ap_ready(ready),
.hidden_address0(address),.hidden_ce0(ce),.hidden_q0(data),.prediction(prediction),.prediction_ap_vld(pv),.margin(margin),.margin_ap_vld(mv));
always @(posedge clk)begin if(ce)data<=mem[phase*32+address];cycles<=cycles+1;if(cycles>100000)$fatal(1,"probe timeout");end
initial begin
$readmemh("hidden.mem",mem);repeat(30)@(negedge clk);rst=0;
for(phase=0;phase<3;phase=phase+1)begin
@(negedge clk);start=1;
wait(done);@(negedge clk);start=0;
if(prediction!=EXPECTED_P || margin!=EXPECTED_M)$fatal(1,"SCORE_PROBE_MISMATCH phase=%d p=%d margin=%d",phase,prediction,margin);
$display("SCORE_PROBE_CASE_PASS phase=%d p=%d margin=%d",phase,prediction,margin);
repeat(5)@(negedge clk);
end
$display("SCORE_PROBE_POST_SYNTH_PASS cases=3");$finish;
end
endmodule
'''
    ep='(phase==0?'+str(expected[0][0])+':(phase==1?'+str(expected[1][0])+':'+str(expected[2][0])+'))'
    em='(phase==0?'+str(expected[0][1])+':(phase==1?'+str(expected[1][1])+':'+str(expected[2][1])+'))'
    (ROOT/'tb_score_probe.sv').write_text(tb.replace('EXPECTED_P',ep).replace('EXPECTED_M',em),encoding='ascii')
    (ROOT/'build.tcl').write_text('''set root [file dirname [file normalize [info script]]]
cd $root
open_project probe_project
set_top score_probe
add_files score_probe.cpp -cflags "-std=c++14"
add_files cnn_weights.h
open_solution solution -flow_target vivado
set_part {xc7z020clg400-2}
create_clock -period 10 -name default
csynth_design
exit
''',encoding='ascii')
    (ROOT/'synth.tcl').write_text('''set root [file dirname [file normalize [info script]]]
set rtl $root/probe_project/solution/syn/verilog
cd $rtl
read_verilog [glob *.v]
synth_design -top score_probe -part xc7z020clg400-2 -mode out_of_context
write_verilog -force -mode funcsim $root/score_probe_netlist.v
close_design
exit
''',encoding='ascii')
    (ROOT/'probe.prj').write_text('verilog xil_defaultlib "score_probe_netlist.v"\nsv xil_defaultlib "tb_score_probe.sv"\nverilog xil_defaultlib "E:/Xilinx/Vivado/2020.2/data/verilog/src/glbl.v"\n',encoding='ascii')
    (ROOT/'run.ps1').write_text('''$ErrorActionPreference='Stop'
Set-Location 'E:\\FPGA_Enhance_Work\\cnn_score_probe_20261025'
& 'E:\\Xilinx\\Vitis_HLS\\2020.2\\bin\\vitis_hls.bat' -f build.tcl *> hls.log
if($LASTEXITCODE -ne 0){throw 'probe HLS failed'}
& 'E:\\Xilinx\\Vivado\\2020.2\\bin\\vivado.bat' -mode batch -source synth.tcl -notrace *> synth.log
if($LASTEXITCODE -ne 0){throw 'probe synthesis failed'}
& 'E:\\Xilinx\\Vivado\\2020.2\\bin\\xvlog.bat' -prj probe.prj *> compile.log
if($LASTEXITCODE -ne 0){throw 'probe compile failed'}
& 'E:\\Xilinx\\Vivado\\2020.2\\bin\\xelab.bat' xil_defaultlib.tb_score_probe xil_defaultlib.glbl -L unisims_ver -L unimacro_ver -L secureip -s score_probe_sim -debug typical *> elaborate.log
if($LASTEXITCODE -ne 0){throw 'probe elaboration failed'}
& 'E:\\Xilinx\\Vivado\\2020.2\\bin\\xsim.bat' score_probe_sim -runall -onerror quit -onfinish quit *> simulate.log
if(-not(Select-String -LiteralPath 'simulate.log' -Pattern 'SCORE_PROBE_POST_SYNTH_PASS' -Quiet)){throw 'probe numerical check failed'}
''',encoding='ascii')
    print('ISOLATED_FINAL_SCORE_PROBE_READY',flush=True)

if __name__=='__main__':main()
