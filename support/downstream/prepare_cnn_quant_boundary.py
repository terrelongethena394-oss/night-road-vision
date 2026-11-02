"""Preserve explicit 40-bit quantization module boundary, no trace output."""
from pathlib import Path
import shutil
from train_real_digit_cnn import OUT

def main():
    src=OUT/'layer_trace';dst=OUT/'quant_boundary';dst.mkdir(exist_ok=True)
    for name in ('cnn_weights.h','vectors.txt','tb_trace.cpp','cnn_trace.cpp','build.tcl'):
        shutil.copy2(src/name,dst/name)
    kernel=(src/'trace_kernel.h').read_text(encoding='ascii')
    kernel=kernel.replace('#pragma HLS INLINE\n','#pragma HLS INLINE off\n',1)
    (dst/'trace_kernel.h').write_text(kernel,encoding='ascii')
    p=dst/'tb_trace.cpp';p.write_text(p.read_text().replace(src.as_posix(),dst.as_posix()),encoding='ascii')
    print('QUANTIZATION_BOUNDARY_READY',flush=True)

if __name__=='__main__':main()
