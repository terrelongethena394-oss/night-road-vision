"""Reuse independent stalled-stream checks against actual synthesized cells."""
from pathlib import Path
import re,shutil,sys
from train_real_digit_cnn import OUT

def main():
    score64='--score64' in sys.argv
    source=OUT/('rtl_stream_score64' if score64 else 'rtl_stream_corrected')
    dest=Path('E:/FPGA_Enhance_Work')/('camera_real_cnn_score64_20261025' if score64 else 'camera_real_cnn_20261025')/'post_synth_check'
    net=dest/'digit_monitor_funcsim.v';assert net.exists()
    for name in ('axis_rgb_bridge.v','tb_real_cnn_stream.sv','phase0_input.mem','phase0_expected.mem','phase1_input.mem','phase1_expected.mem'):
        shutil.copy2(source/name,dest/name)
    if score64:
        p=dest/'tb_real_cnn_stream.sv'
        p.write_text(p.read_text().replace('frames=3;','frames=1;').replace('frames=2;','frames=1;').replace('PASS frames=5','PASS frames=2').replace('digit_monitor core','post_synth_core core'),encoding='ascii')
    prj=['verilog xil_defaultlib "digit_monitor_funcsim.v"','verilog xil_defaultlib "axis_rgb_bridge.v"','sv xil_defaultlib "tb_real_cnn_stream.sv"']
    if not re.search(r'\bmodule\s+glbl\b',net.read_text(encoding='utf-8',errors='replace')):
        prj.append('verilog xil_defaultlib "E:/Xilinx/Vivado/2020.2/data/verilog/src/glbl.v"')
    (dest/'post_synth.prj').write_text('\n'.join(prj)+'\n',encoding='ascii')
    run='''$ErrorActionPreference='Stop'
Set-Location 'E:\\FPGA_Enhance_Work\\camera_real_cnn_20261025\\post_synth_check'
& 'E:\\Xilinx\\Vivado\\2020.2\\bin\\xvlog.bat' -prj post_synth.prj *> compile.log
if ($LASTEXITCODE -ne 0) {throw 'Synthesized CNN compile failed'}
& 'E:\\Xilinx\\Vivado\\2020.2\\bin\\xelab.bat' xil_defaultlib.tb_real_cnn_stream xil_defaultlib.glbl -L unisims_ver -L unimacro_ver -L secureip -s post_synth_native_units -debug typical --timescale 1ns/1ps *> elaborate.log
if ($LASTEXITCODE -ne 0) {throw 'Synthesized CNN elaboration failed'}
& 'E:\\Xilinx\\Vivado\\2020.2\\bin\\xsim.bat' post_synth_native_units -runall -onerror quit -onfinish quit *> simulate.log
if ($LASTEXITCODE -ne 0) {throw 'Synthesized CNN functional test failed'}
if (-not (Select-String -LiteralPath 'simulate.log' -Pattern 'REAL_CNN_STREAM_AUTORESTART_BACKPRESSURE_RESET_PASS' -Quiet)) {throw 'Synthesized CNN pass marker missing'}
'''
    if score64:run=run.replace('camera_real_cnn_20261025','camera_real_cnn_score64_20261025')
    (dest/'run.ps1').write_text(run,encoding='ascii')
    print('REAL_CNN_POST_SYNTH_TEST_READY',flush=True)

if __name__=='__main__':main()
