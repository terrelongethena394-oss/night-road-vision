"""Exercise generated RTL under auto-restart, stalls, SOF gating and reset."""
from pathlib import Path
import shutil
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=Path('E:/FPGA_Enhance_Work/digit_recognition_20261023')

def main():
    dest=ROOT/'rtl_stream';dest.mkdir(exist_ok=True)
    tokens=np.fromstring((ROOT/'hls/cases.txt').read_text(encoding='ascii'),sep=' ',dtype=np.int64)
    at=1;cases=[]
    for _ in range(int(tokens[0])):
        h,w,x,y,which,ui,pred,margin=tokens[at:at+8];at+=8
        rgb=tokens[at:at+h*w*3].reshape(h,w,3);at+=h*w*3
        cases.append((rgb,int(pred)))
    for phase,(case,frames) in enumerate([(0,3),(3,2)]):
        rgb,pred=cases[case]
        natural=(rgb[:,:,0]<<16)|(rgb[:,:,1]<<8)|rgb[:,:,2]
        values=np.tile(natural.ravel(),frames)
        for kind in ('input','expected'):
            np.savetxt(dest/f'phase{phase}_{kind}.mem',values,fmt='%06x')
    tb=(HERE.parent/'sim/tb_nn_stream.sv').read_text(encoding='ascii')
    tb=tb.replace('tb_nn_stream','tb_digit_stream').replace('nanodce_full core','digit_monitor core')
    tb=tb.replace('[5:0]','[6:0]').replace("6'b0","7'b0").replace('[0:32767]','[0:262143]')
    tb=tb.replace('wire awready,wready,bvalid;','wire awready,wready,bvalid;\n    reg arvalid=0; reg [6:0] araddr=0; wire arready,rvalid; wire [31:0] rdata; wire [1:0] rresp;')
    tb=tb.replace('.s_axi_control_ARVALID(1\'b0),.s_axi_control_ARREADY(),.s_axi_control_ARADDR(7\'b0)',
                  '.s_axi_control_ARVALID(arvalid),.s_axi_control_ARREADY(arready),.s_axi_control_ARADDR(araddr)')
    tb=tb.replace('.s_axi_control_RVALID(),.s_axi_control_RREADY(1\'b1),.s_axi_control_RDATA(),.s_axi_control_RRESP()',
                  '.s_axi_control_RVALID(rvalid),.s_axi_control_RREADY(1\'b1),.s_axi_control_RDATA(rdata),.s_axi_control_RRESP(rresp)')
    read='''
    reg [31:0] result_word;
    integer polls;
    task automatic axi_read(input [6:0] address, output [31:0] value);
        begin
            @(negedge clk); araddr=address; arvalid=1;
            do @(posedge clk); while (!arready);
            @(negedge clk); arvalid=0;
            do @(posedge clk); while (!rvalid);
            if(rresp!=0) $fatal(1,"AXI read error");
            value=rdata;
            @(negedge clk);
        end
    endtask
'''
    tb=tb.replace('    always @(negedge clk) begin',read+'    always @(negedge clk) begin',1)
    tb=tb.replace('phase<3','phase<2')
    tb=tb.replace('1: begin h=32; w=64; frames=3; mode=1; end','1: begin h=240; w=256; frames=2; mode=3; end')
    tb=tb.replace('                2: begin h=8; w=800; frames=2; mode=2; end\n','')
    tb=tb.replace("axi_write(6'h10,h); axi_write(6'h18,w); axi_write(6'h20,mode); axi_write(6'h00,32'h81);",
       "axi_read(7'h70,result_word); if(result_word!=0) $fatal(1,\"Result not reset\");\n"
       "            axi_write(7'h10,h); axi_write(7'h18,w); axi_write(7'h20,phase==0?0:16); axi_write(7'h28,phase==0?0:8);\n"
       "            axi_write(7'h30,0); axi_write(7'h38,32'haa); axi_write(7'h00,32'h81);")
    tb=tb.replace('            grand_total=grand_total+received;', '''            result_word=0; polls=0;
            while((result_word>>4)!=frames && polls<4000) begin
                axi_read(7'h70,result_word); polls=polls+1;
            end
            if(result_word!=((frames<<4)|mode)) $fatal(1,"Atomic classification/frame mismatch: %h",result_word);
            grand_total=grand_total+received;''')
    # phase 0 is an out-of-bounds ROI, hence all-zero input/background class 10.
    tb=tb.replace('frames=3; mode=0','frames=3; mode=10')
    tb=tb.replace('NN_STREAM_AUTORESTART_BACKPRESSURE_PASS frames=8','DIGIT_STREAM_AUTORESTART_BACKPRESSURE_RESET_PASS frames=5')
    tb=tb.replace('NN_STREAM_PHASE_PASS','DIGIT_STREAM_PHASE_PASS')
    (dest/'tb_digit_stream.sv').write_text(tb,encoding='ascii')
    shutil.copy2('E:/FPGA_Enhance_Work/camera_nn8_20261023/rtl/axis_rgb_bridge.v',dest/'axis_rgb_bridge.v')
    rtl=ROOT/'hls/digit_project/solution_100mhz/syn/verilog'
    files=list(rtl.glob('*.v'))
    (dest/'digit_stream.prj').write_text('\n'.join('verilog xil_defaultlib "'+p.as_posix()+'"' for p in files)+
        '\nverilog xil_defaultlib "axis_rgb_bridge.v"\nsv xil_defaultlib "tb_digit_stream.sv"\n',encoding='ascii')
    for p in rtl.glob('*.dat'):shutil.copy2(p,dest/p.name)
    run=(HERE.parent/'diagnostics/run_nn_stream_test.ps1').read_text(encoding='utf-8-sig')
    run=run.replace('E:\\FPGA_Enhance_Work\\camera_nn_20261018\\sim\\nn_full_stream',str(dest).replace('/','\\'))
    run=run.replace('nn_stream','digit_stream').replace('tb_nn_stream','tb_digit_stream')
    run=run.replace('NN_STREAM_AUTORESTART_BACKPRESSURE_PASS','DIGIT_STREAM_AUTORESTART_BACKPRESSURE_RESET_PASS')
    (dest/'run.ps1').write_text(run,encoding='ascii')
    print('DIGIT_NATIVE_RTL_INPUTS_READY')

if __name__=='__main__':main()
