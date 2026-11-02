"""Isolate channel-bank unrolling from the failing DSP CNN, one zero case."""
from pathlib import Path
import shutil
src=Path('E:/FPGA_Enhance_Work/real_digit_training_20261025/cnn_candidate/hls')
dst=src.parent/'hls_serial_diagnostic';dst.mkdir(exist_ok=True)
for name in ['cnn_weights.h','digit_monitor.h','digit_monitor.cpp','real_cnn_kernel.h','tb_digit.cpp','build.tcl','cosim.tcl']:
    shutil.copy2(src/name,dst/name)
p=dst/'real_cnn_kernel.h'
text=p.read_text().replace('base+=4','++base').replace('l<4','l<1').replace('maximum[4]','maximum[1]').replace('acc[4]','acc[1]')
text='\n'.join(line for line in text.splitlines() if 'cyclic factor=4' not in line)+'\n'
p.write_text(text,encoding='ascii')
p=dst/'tb_digit.cpp';p.write_text(p.read_text().replace(src.as_posix(),dst.as_posix()).replace('n!=6','n!=1'),encoding='ascii')
lines=(src/'cases.txt').read_text().splitlines()
(dst/'cases.txt').write_text('1\n'+'\n'.join(lines[1:155])+'\n',encoding='ascii')
p=dst/'build.tcl';p.write_text(p.read_text().replace('puts "REAL_CNN_CSIM_SYNTH_PASS"',
    'cosim_design -rtl verilog -tool xsim -trace_level none\nputs "REAL_CNN_SERIAL_DIAGNOSTIC_PASS"'),encoding='ascii')
print('SERIAL_ISOLATED_ZERO_CASE_READY',flush=True)
